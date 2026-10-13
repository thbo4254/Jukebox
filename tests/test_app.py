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
