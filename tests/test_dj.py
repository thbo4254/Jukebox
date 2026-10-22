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


def test_reference_near_six_megabytes_reaches_endpoint_validation_not_middleware(tmp_path):
    # Regression for #13: a file just under 6 MiB (per the client rule) encodes to
    # ~8.39 MB of base64 + JSON wrapper, which used to trip the middleware 413
    # before the endpoint's own clean validation could run.
    app=create_app(tmp_path,services=DJFixtures(),samples=None)
    song=app.state.store.create({'title':'Rain','topic':'cafe','style':'jazz','mood':'warm'})
    near=base64.b64encode(b'\x00'*(6*1024*1024-456)).decode()
    assert len(near) < 9*1024*1024
    with TestClient(app) as c:
        h={'X-Jukebox':'1'}
        r=c.post('/api/dj/'+song['id'],headers=h,json={'personality':'Warm & Laid-back','reference':near})
        assert r.status_code==422, 'near-limit body must reach endpoint validation, not the 413 middleware'
        assert 'valid MP3 or WAV' in r.json()['detail']
        # The body bound still exists: anything beyond it is rejected early.
        huge=base64.b64encode(b'\x00'*(10*1024*1024)).decode()
        r2=c.post('/api/dj/'+song['id'],headers=h,json={'personality':'Warm & Laid-back','reference':huge})
        assert r2.status_code==413
