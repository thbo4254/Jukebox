import importlib.util
import io
import time
import asyncio
import httpx
import pytest
from fastapi.testclient import TestClient
import soundfile as sf
import numpy as np
from jukebox.services import ServiceError


class FixtureServices:
    async def music(self,spec):
        b=io.BytesIO(); sf.write(b,np.zeros(2400),24000,format='WAV')
        return b.getvalue(),{'model':'offline-test-fixture'}
    async def cover(self,spec):
        raise ServiceError('Image service returned HTTP 503. Wait and retry the cover.')
    async def lyrics(self,spec):
        return '[Verse]\nOriginal fixture lyrics'


def test_generate_persists_audio_despite_cover_failure_and_allows_cover_only_retry(tmp_path):
    assert importlib.util.find_spec('jukebox.app'), 'Local application missing'
    from jukebox.app import create_app
    app=create_app(tmp_path,services=FixtureServices(),samples=None)
    with TestClient(app) as c:
        h={'X-Jukebox':'1'}
        spec={'title':'Rain','topic':'cafe','style':'jazz','mood':'warm','duration':30,'instrumental':True}
        r=c.post('/api/songs',json=spec,headers=h)
        assert r.status_code==202
        song_id=r.json()['id']
        for _ in range(100):
            song=c.get('/api/songs/'+song_id).json()
            if song['cover_status']=='failed': break
            time.sleep(.01)
        assert song['status']=='ready' and song['cover_status']=='failed'
        assert '503' in song['cover_error']
        assert c.get(f'/api/songs/{song_id}/audio').status_code==200
        assert c.post(f'/api/songs/{song_id}/retry-cover',headers=h).status_code==202
    again=create_app(tmp_path,services=FixtureServices(),samples=None)
    with TestClient(again) as c:
        assert c.get('/api/songs').json()[0]['id']==song_id


@pytest.mark.parametrize('occupied',[2,3])
def test_retry_and_new_requests_share_atomic_three_job_admission(tmp_path,occupied):
    from jukebox.app import create_app

    class BlockedServices(FixtureServices):
        async def music(self,spec):
            await asyncio.Event().wait()

    async def run():
        app=create_app(tmp_path,services=BlockedServices(),samples=None)
        spec={'title':'Admission','topic':'rain','style':'jazz','mood':'warm'}
        async with app.router.lifespan_context(app):
            store=app.state.store
            failed=[]
            for _ in range(4):
                song=store.create(spec)
                failed.append(store.update(song['id'],status='failed',error='Keep on rejection'))
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost',headers={'X-Jukebox':'1'}) as client:
                for _ in range(occupied):
                    assert (await client.post('/api/songs',json=spec)).status_code==202
                before=set(asyncio.all_tasks())
                responses=await asyncio.gather(
                    *(client.post(f"/api/songs/{song['id']}/retry") for song in failed),
                    client.post('/api/songs',json=spec),
                )
                assert sorted(r.status_code for r in responses)==[202]*(3-occupied)+[429]*(2+occupied)
                assert sum(s['status'] in ('queued','generating') for s in store.list())==3
                for original,response in zip(failed,responses):
                    if response.status_code==429:
                        assert store.get(original['id'])==original
                # Rejected requests must not schedule background generation either.
                added=[t for t in asyncio.all_tasks()-before if t.get_coro().__qualname__.endswith('generate_job')]
                assert len(added)==3-occupied
    asyncio.run(run())


class ConfiguredServices(FixtureServices):
    """Fixture services with the real endpoint-config shape, so the metadata
    enrichment path (which reads services.config) is exercised."""
    from jukebox.config import Endpoint
    config={
        'text': Endpoint('http://dobolyi.com:9001/v1','cyankiwi/Qwen3.6-35B-A3B-AWQ-4bit','fixture-key'),
        'image': Endpoint('http://dobolyi.com:9006/v1','black-forest-labs/FLUX.2-klein-4B','fixture-key'),
        'music': Endpoint('http://dobolyi.com:9007','acestep-v15-xl-turbo','fixture-key'),
        'speech': Endpoint('http://dobolyi.com:9008','Chatterbox Multilingual V3','fixture-key'),
    }


def test_generated_records_persist_class_model_metadata(tmp_path):
    from jukebox.app import create_app
    app=create_app(tmp_path,services=ConfiguredServices(),samples=None)
    with TestClient(app) as c:
        h={'X-Jukebox':'1'}
        vocal={'title':'Rainy Cafe','topic':'a rainy cafe at dusk','style':'jazz','mood':'warm',
               'duration':30,'instrumental':False,'lyrics':'[Verse]\nRain on glass'}
        r=c.post('/api/songs',json=vocal,headers=h)
        assert r.status_code==202
        doc=r.json()
        assert doc['lyrics_model']=='cyankiwi/Qwen3.6-35B-A3B-AWQ-4bit'
        assert doc['lyrics_source']=='Qwen class endpoint; passed unchanged to ACE-Step'
        assert doc['image_model']=='black-forest-labs/FLUX.2-klein-4B'
        assert 'no text, no lettering' in doc['image_prompt'] and 'rainy cafe' in doc['image_prompt']
        # persisted in the library, not just echoed in the admission response
        stored=c.get('/api/songs/'+doc['id']).json()
        assert stored['lyrics_model']==doc['lyrics_model']
        assert stored['image_prompt']==doc['image_prompt']

        instrumental={'title':'First Snow','topic':'first snow on main street','style':'jazz',
                      'mood':'warm','duration':30,'instrumental':True}
        r2=c.post('/api/songs',json=instrumental,headers=h)
        assert r2.status_code==202
        doc2=r2.json()
        assert doc2['image_model']=='black-forest-labs/FLUX.2-klein-4B'
        assert 'first snow' in doc2['image_prompt']
        assert 'lyrics_model' not in doc2 and 'lyrics_source' not in doc2


def test_cover_prompt_prefers_explicit_idea_over_topic():
    from jukebox.services import Services
    spec={'cover_prompt':'A neon-lit diner','topic':'a rainy street','style':'retro soul-pop','mood':'cheerful'}
    prompt=Services.cover_prompt(spec)
    assert 'A neon-lit diner' in prompt and 'retro soul-pop' in prompt
    assert 'no text, no lettering' in prompt
    # no cover idea -> the topic supplies the concept
    spec2=dict(spec,cover_prompt='')
    assert 'a rainy street' in Services.cover_prompt(spec2)
