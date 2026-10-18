import asyncio
import httpx
import jukebox.app as app_module
import base64
import io
import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient
from jukebox.app import create_app
from test_app import FixtureServices

class DJFixtures(FixtureServices):
    async def dj(self,song,personality,reference=None):
        self.reference=reference
        return b'unit speech',song['title']+' is next.'


def test_default_and_reference_dj_never_persist_voice(tmp_path):
    service=DJFixtures()
    app=create_app(tmp_path,services=service,samples=None)
    song=app.state.store.create({'title':'Rain','topic':'cafe','style':'jazz','mood':'warm'})
    with TestClient(app) as c:
        h={'X-Jukebox':'1'}
        r=c.post('/api/dj/'+song['id'],headers=h,json={'personality':'Warm & Laid-back'})
        assert r.status_code==200, 'DJ endpoint missing'
        assert r.json()['intro']=='Rain is next.' and service.reference is None
        out=io.BytesIO(); sf.write(out,np.zeros(24000),24000,format='WAV')
        data=out.getvalue()
        r=c.post('/api/dj/'+song['id'],headers=h,json={'personality':'Upbeat & Playful','reference':base64.b64encode(data).decode()})
        assert r.status_code==200 and service.reference==data
        assert list(tmp_path.iterdir())==[tmp_path/'library.sqlite3']
        r=c.post('/api/dj/'+song['id'],headers=h,json={'personality':'Warm & Laid-back','reference':base64.b64encode(b'not audio').decode()})
        assert r.status_code==422


def test_dj_deadline_cancels_stalled_service_and_returns_safe_504(tmp_path, monkeypatch):
    # Shorten only the DJ budget, not the global service timeout. The outer
    # watchdog makes the pre-fix regression fail fast instead of hanging.
    monkeypatch.setattr(app_module, 'DJ_TIMEOUT_SECONDS', 0.01, raising=False)
    cancelled = []

    class StalledDJ(DJFixtures):
        async def dj(self, song, personality, reference=None):
            try:
                await asyncio.Future()
            finally:
                cancelled.append(True)

    app = create_app(tmp_path, services=StalledDJ(), samples=None)
    song = app.state.store.create({'title':'Rain','topic':'cafe','style':'jazz','mood':'warm'})

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://testserver') as client:
            try:
                response = await asyncio.wait_for(client.post('/api/dj/'+song['id'], headers={'X-Jukebox':'1'}, json={}), 0.2)
            except TimeoutError:
                assert False, 'DJ request stayed pending beyond its total deadline'
            assert response.status_code == 504
            assert response.json() == {'detail':'DJ preparation timed out. Continue with music or retry playback.'}
    asyncio.run(run())
    assert cancelled == [True]
    assert list(tmp_path.iterdir()) == [tmp_path/'library.sqlite3']
