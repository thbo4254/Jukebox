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
