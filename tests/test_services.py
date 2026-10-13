import asyncio
import importlib.util
import json
import httpx
import pytest
from jukebox.config import Endpoint


def config():
    return {name: Endpoint(f'http://dobolyi.com:{port}', model, 'unit-test-key') for name,port,model in [('text',9001,'qwen'),('image',9006,'flux'),('music',9007,'ace'),('speech',9008,'chatterbox-v3')]}


def test_qwen_lyrics_returns_editable_original_text():
    assert importlib.util.find_spec('jukebox.services'), 'Service adapter missing'
    from jukebox.services import Services
    def handler(req):
        p=json.loads(req.content)
        assert req.url.path == '/v1/chat/completions'
        assert p['model']=='qwen'
        assert 'rain' in p['messages'][-1]['content']
        return httpx.Response(200,json={'choices':[{'message':{'content':'[Verse]\nRain is falling'}}]})
    async def run():
        s=Services(config(),httpx.MockTransport(handler))
        assert await s.lyrics({'topic':'rain','style':'jazz','mood':'warm','duration':30})=='[Verse]\nRain is falling'
    asyncio.run(run())


def test_music_polling_preserves_edited_lyrics_and_downloads_only_class_audio():
    from jukebox.services import Services
    assert hasattr(Services, 'music'), 'Music generation missing'
    calls=[]
    def handler(req):
        calls.append(req.url.path)
        if req.url.path=='/v1/models':
            return httpx.Response(200,json={'data':[{'id':'acestep/acestep-v15-xl-turbo'}]})
        if req.url.path=='/release_task':
            p=json.loads(req.content)
            assert p['lyrics']=='  Edited line\n[Chorus]\nStay!  '
            assert p['audio_duration']==30 and p['batch_size']==1
            assert p['use_format'] is False and p['thinking'] is False
            return httpx.Response(200,json={'data':{'task_id':'123'}})
        if req.url.path=='/query_result':
            return httpx.Response(200,json={'data':[{'status':1,'result':json.dumps([{'file':'/v1/audio?path=%2Ftmp%2Fx.mp3','dit_model':'xl-turbo','create_time':123}])}]})
        return httpx.Response(200,content=b'unit fixture audio')
    async def run():
        s=Services(config(),httpx.MockTransport(handler),poll_interval=0)
        audio, meta=await s.music({'topic':'rain','style':'jazz','mood':'warm','duration':30,'instrumental':False,'lyrics':'  Edited line\n[Chorus]\nStay!  '})
        assert audio==b'unit fixture audio' and meta['model']=='xl-turbo'
        assert calls==['/v1/models','/release_task','/query_result','/v1/audio']
    asyncio.run(run())

