"""Offline contracts only: HTTP fixtures below are NOT real-service evidence."""
import asyncio
import base64
import io
import json
import time
import httpx
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from jukebox.app import create_app
from jukebox.services import Services, ServiceError
from test_services import config
from test_app import FixtureServices

@pytest.mark.parametrize('url',['http://evil.example/v1/audio?path=x','http://127.0.0.1:9007/v1/audio?path=x','//evil.example/v1/audio?path=x','/etc/passwd','http://dobolyi.com:9000/v1/audio?path=x'])
def test_returned_music_urls_cannot_send_class_credentials_elsewhere(url):
    calls=[]
    def handler(req):
        calls.append(str(req.url))
        if req.url.path=='/v1/models':return httpx.Response(200,json={'data':[{'id':'xl-turbo'}]})
        if req.url.path=='/release_task':return httpx.Response(200,json={'data':{'task_id':'test'}})
        return httpx.Response(200,json={'data':[{'status':1,'result':json.dumps([{'file':url}])}]})
    async def run():
        s=Services(config(),httpx.MockTransport(handler),poll_interval=0)
        with pytest.raises(ServiceError,match='unsafe'):
            await s.music({'style':'jazz','mood':'warm','topic':'rain','duration':30,'instrumental':True})
        assert len(calls)==3 and all(x.startswith('http://dobolyi.com:9007/') for x in calls)
    asyncio.run(run())

@pytest.mark.parametrize('status',[302,401,429,500])
def test_http_errors_do_not_echo_upstream_secrets_or_follow_redirect(status):
    def handler(req):return httpx.Response(status,headers={'location':'http://evil.example'},text='SECRET_UPSTREAM_DIAGNOSTIC')
    async def run():
        with pytest.raises(ServiceError) as e:
            await Services(config(),httpx.MockTransport(handler)).text('test','test')
        assert 'SECRET_UPSTREAM_DIAGNOSTIC' not in str(e.value)
        assert str(status) in str(e.value)
    asyncio.run(run())


def test_music_failure_is_terminal_not_forever_polling():
    def handler(req):
        if req.url.path=='/v1/models':return httpx.Response(200,json={'data':[{'id':'xl-turbo'}]})
        if req.url.path=='/release_task':return httpx.Response(200,json={'data':{'task_id':'test'}})
        return httpx.Response(200,json={'data':[{'status':2,'result':'private server error'}]})
    async def run():
        with pytest.raises(ServiceError,match='Music generation failed'):
            await Services(config(),httpx.MockTransport(handler),poll_interval=0).music({'style':'jazz','mood':'warm','topic':'rain','duration':30,'instrumental':True})
    asyncio.run(run())


class Recovering(FixtureServices):
    music_calls=0
    cover_calls=0
    async def music(self,spec):
        self.music_calls+=1
        return await super().music(spec)
    async def cover(self,spec):
        self.cover_calls+=1
        if self.cover_calls==1:raise ServiceError('Image unavailable; retry cover.')
        b=io.BytesIO();Image.new('RGB',(32,32)).save(b,format='PNG');return b.getvalue()


def test_cover_retry_recovers_without_generating_audio_again(tmp_path):
    service=Recovering()
    app=create_app(tmp_path,services=service,samples=None)
    with TestClient(app) as c:
        h={'X-Jukebox':'1'}
        song=c.post('/api/songs',headers=h,json={'title':'Retry','topic':'rain','style':'jazz','mood':'warm'}).json()
        url='/api/songs/'+song['id']
        for _ in range(100):
            if c.get(url).json()['cover_status']=='failed':break
            time.sleep(.01)
        audio=c.get(url+'/audio').content
        assert c.post(url+'/retry-cover',headers=h).status_code==202
        for _ in range(100):
            if c.get(url).json()['cover_status']=='ready':break
            time.sleep(.01)
        assert c.get(url).json()['cover_status']=='ready'
        assert c.get(url+'/audio').content==audio
        assert service.music_calls==1 and service.cover_calls==2
        Image.open(io.BytesIO(c.get(url+'/cover').content)).verify()


def test_restart_marks_interrupted_jobs_retryable(tmp_path):
    first=create_app(tmp_path,services=FixtureServices(),samples=None)
    song=first.state.store.create({'title':'Interrupted','topic':'rain','style':'jazz','mood':'warm'})
    with TestClient(create_app(tmp_path,services=FixtureServices(),samples=None)) as c:
        s=c.get('/api/songs/'+song['id']).json()
        assert s['status']=='failed' and 'restart' in s['error']
