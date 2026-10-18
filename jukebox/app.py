"""Single-process, local-only API with durable jobs and generated media."""
import asyncio
from contextlib import asynccontextmanager
import io
import json
import os
from pathlib import Path
import shutil
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
import soundfile as sf

from .config import load_config
from .services import Services, ServiceError
from .store import Store

ROOT=Path(__file__).resolve().parent.parent
DJ_TIMEOUT_SECONDS=15


class SongSpec(BaseModel):
    title: str = Field(min_length=1,max_length=100)
    topic: str = Field(min_length=1,max_length=1500)
    style: str = Field(min_length=1,max_length=300)
    mood: str = Field(min_length=1,max_length=200)
    duration: int = Field(default=30,ge=10,le=120)
    instrumental: bool = True
    lyrics: str = Field(default='',max_length=6000)
    cover_prompt: str = Field(default='',max_length=1500)


class DJSpec(BaseModel):
    personality: Literal['Warm & Laid-back','Upbeat & Playful','Music Enthusiast'] = 'Warm & Laid-back'
    reference: str | None = Field(default=None,max_length=8*1024*1024)


def safe_error(exc):
    return str(exc) if isinstance(exc,ServiceError) else 'The service response could not be processed. Please retry; your existing library is safe.'


def create_app(data_dir=None, services=None, samples=ROOT/'samples'):
    store=Store(data_dir or os.environ.get('JUKEBOX_DATA_DIR',ROOT/'data'))
    tasks=set()
    lock=asyncio.Lock()
    config_error=''
    if services is None:
        try:
            services=Services(load_config())
        except ValueError as e:
            config_error=str(e)

    @asynccontextmanager
    async def lifespan(app):
        # Interrupted work is explicit rather than a forever-spinning progress label.
        for song in store.list():
            if song['status'] in ('queued','generating'):
                store.update(song['id'],status='failed',error='Generation was interrupted by a restart. Retry when ready.')
            if song.get('cover_status') in ('pending','generating') and song['status']=='ready':
                store.update(song['id'],cover_status='failed',cover_error='Cover was interrupted. Retry cover only.')
        if samples:
            for meta in Path(samples).glob('*/metadata.json'):
                song=json.loads(meta.read_text())
                song_id= 'sample-'+meta.parent.name
                try:
                    store.get(song_id)
                except KeyError:
                    if not (meta.parent/'audio.mp3').is_file() or not (meta.parent/'cover.png').is_file():
                        continue
                    folder=store.root/song_id; folder.mkdir(exist_ok=True)
                    for name in ('audio.mp3','cover.png'):
                        shutil.copyfile(meta.parent/name,folder/name)
                    store.put(dict(song,id=song_id,status='ready',cover_status='ready',error='',sample=True))
        yield
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)

    app=FastAPI(title='Jukebox',lifespan=lifespan,docs_url=None,redoc_url=None)
    from .security import LocalOnly
    app.add_middleware(LocalOnly)
    app.state.store=store

    def require_services():
        if services is None:
            raise HTTPException(503,config_error)
        return services

    def start(coro):
        t=asyncio.create_task(coro); tasks.add(t); t.add_done_callback(tasks.discard)

    def admit_generation(*,spec=None,song_id=None):
        # Single-worker event loop: no await between admission, reservation and
        # task creation, so concurrent new/retry requests cannot claim one slot.
        if song_id is not None and store.get(song_id)['status']!='failed':
            raise HTTPException(409,'Only failed tracks can be retried.')
        if sum(s['status'] in ('queued','generating') for s in store.list())>=3:
            raise HTTPException(429,'Three tracks are already waiting. Let one finish before adding another.')
        song=store.create(spec) if song_id is None else store.update(song_id,status='queued',error='')
        if song_id is None:
            # Record which class models produced this record and the exact cover
            # prompt used, matching the bundled samples' metadata. Values come
            # from the server-side config only, never from the browser.
            cfg=getattr(services,'config',None) if services is not None else None
            if cfg is not None:
                extra={'image_model':cfg['image'].model,'image_prompt':Services.cover_prompt(spec)}
                if not spec['instrumental'] and spec.get('lyrics','').strip():
                    extra['lyrics_model']=cfg['text'].model
                    extra['lyrics_source']='Qwen class endpoint; passed unchanged to ACE-Step'
                store.update(song['id'],**extra)
                song=store.get(song['id'])
        start(generate_job(song['id']))
        return song

    async def cover_job(song_id):
        async with lock:
            store.update(song_id,cover_status='generating',cover_error='')
            try:
                cover=await require_services().cover(store.get(song_id))
                folder=store.root/song_id; folder.mkdir(exist_ok=True)
                p=folder/'cover.part'; p.write_bytes(cover); p.replace(folder/'cover.png')
                store.update(song_id,cover_status='ready',cover_error='')
            except Exception as exc:
                store.update(song_id,cover_status='failed',cover_error=safe_error(exc))

    async def generate_job(song_id):
        async with lock:
            store.update(song_id,status='generating',error='')
            try:
                audio,meta=await require_services().music(store.get(song_id))
                info=sf.info(io.BytesIO(audio))
                if info.duration<=0:
                    raise ValueError('empty audio')
                store.save_audio(song_id,audio,meta,info.duration)
            except Exception as exc:
                store.update(song_id,status='failed',error=safe_error(exc)); return
        await cover_job(song_id)

    @app.exception_handler(RequestValidationError)
    async def invalid(request,exc):
        # Do not echo posted input in an error response.
        return JSONResponse({'detail':'Check the form: title, topic, style and mood are required; duration must be 10–120 seconds and text must fit the displayed limits.'},status_code=422)

    @app.exception_handler(KeyError)
    async def missing(request,exc):
        return JSONResponse({'detail':'Track or media not found.'},status_code=404)

    @app.exception_handler(ServiceError)
    async def upstream_error(request,exc):
        return JSONResponse({'detail':str(exc)},status_code=502)

    @app.get('/api/status')
    async def status():
        return {'configured':services is not None,'message':config_error or 'Class services configured. Requests are made only when you use a feature.'}

    @app.get('/api/songs')
    async def songs():
        return store.list()

    @app.get('/api/songs/{song_id}')
    async def song(song_id:str):
        return store.get(song_id)

    @app.get('/api/songs/{song_id}/{kind}')
    async def media(song_id:str,kind:Literal['audio','cover']):
        return FileResponse(store.media(song_id,kind),media_type='audio/mpeg' if kind=='audio' else 'image/png')

    @app.post('/api/lyrics')
    async def lyrics(spec:SongSpec):
        try:
            return {'lyrics':await require_services().lyrics(spec.model_dump())}
        except ServiceError:
            raise
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(502,'Lyrics could not be generated. Please retry.') from None

    @app.post('/api/songs',status_code=202)
    async def generate(spec:SongSpec):
        require_services()
        if not spec.instrumental and not spec.lyrics.strip():
            raise HTTPException(422,'Generate and review lyrics before creating a vocal track.')
        return admit_generation(spec=spec.model_dump())

    @app.post('/api/songs/{song_id}/retry-cover',status_code=202)
    async def retry_cover(song_id:str):
        require_services(); song=store.get(song_id)
        if song['status']!='ready' or song['cover_status']!='failed':
            raise HTTPException(409,'Cover retry is available only for a playable track with a failed cover.')
        store.update(song_id,cover_status='pending'); start(cover_job(song_id))
        return {'id':song_id}

    @app.post('/api/songs/{song_id}/retry',status_code=202)
    async def retry_song(song_id:str):
        require_services()
        admit_generation(song_id=song_id)
        return {'id':song_id}

    @app.post('/api/dj/{song_id}')
    async def dj(song_id:str,spec:DJSpec):
        import base64
        service=require_services(); song=store.get(song_id)
        reference=None
        if spec.reference:
            try:
                reference=base64.b64decode(spec.reference,validate=True)
                if len(reference)>6*1024*1024:
                    raise ValueError()
                info=sf.info(io.BytesIO(reference))
                if info.format not in ('WAV','MP3') or not 1<=info.duration<=60:
                    raise ValueError()
            except Exception:
                raise HTTPException(422,'Use a valid MP3 or WAV voice reference, 1–60 seconds and under 6 MB. Only upload a voice you have permission to use.') from None
        try:
            # One budget for text plus speech, independent of generation timeouts.
            async with asyncio.timeout(DJ_TIMEOUT_SECONDS):
                audio,intro=await service.dj(song,spec.personality,reference)
            return {'audio':base64.b64encode(audio).decode('ascii'),'intro':intro}
        except TimeoutError:
            raise HTTPException(504,'DJ preparation timed out. Continue with music or retry playback.') from None
        except ServiceError:
            raise
        except Exception:
            raise HTTPException(502,'DJ speech could not be generated. Continue with music or retry playback.') from None

    @app.get('/')
    async def index():
        return FileResponse(ROOT/'jukebox/static/index.html')

    @app.get('/static/{name}')
    async def static(name:str):
        if name not in ('app.js','player.js','style.css','placeholder.svg'):
            raise HTTPException(404)
        return FileResponse(ROOT/'jukebox/static'/name)

    return app
