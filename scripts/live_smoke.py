"""Live smoke evidence. No fixtures; synthetic voice reference exists only in memory."""
import base64
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import httpx
from PIL import Image
import soundfile as sf


def main():
    results={'tested_at':datetime.now(timezone.utc).isoformat(),'samples':[]}
    for folder in sorted(Path('samples').iterdir()):
        if not folder.is_dir(): continue
        data,rate=sf.read(folder/'audio.mp3',always_2d=True)
        meta=json.loads((folder/'metadata.json').read_text())
        with Image.open(folder/'cover.png') as image:
            image.load();size=list(image.size)
        assert data.shape[0]/rate==30 and abs(data).max()>0
        results['samples'].append({'title':meta['title'],'frames':data.shape[0],'sample_rate':rate,'channels':data.shape[1],'decoded_seconds':data.shape[0]/rate,'peak':float(abs(data).max()),'cover_size':size,'audio_sha256':hashlib.sha256((folder/'audio.mp3').read_bytes()).hexdigest(),'cover_sha256':hashlib.sha256((folder/'cover.png').read_bytes()).hexdigest()})
    with httpx.Client(base_url='http://127.0.0.1:8765',timeout=300,headers={'X-Jukebox':'1'}) as c:
        r=c.post('/api/dj/sample-the-long-way-home',json={'personality':'Music Enthusiast'})
        r.raise_for_status();d=r.json();speech=base64.b64decode(d['audio']);audio,rate=sf.read(io.BytesIO(speech))
        assert len(audio)/rate>1
        results['default_dj']={'status':r.status_code,'intro':d['intro'],'decoded_seconds':len(audio)/rate,'sample_rate':rate,'model':'chatterbox-v3','personality':'Music Enthusiast'}
        r=c.post('/api/dj/sample-saturday-neon',json={'personality':'Upbeat & Playful','reference':base64.b64encode(speech).decode()})
        r.raise_for_status();d=r.json();audio,rate=sf.read(io.BytesIO(base64.b64decode(d['audio'])))
        results['synthetic_reference_dj']={'status':r.status_code,'intro':d['intro'],'decoded_seconds':len(audio)/rate,'reference_origin':'App-generated default Chatterbox speech held only in memory; synthetic smoke test, NOT a human voice-clone quality test'}
        r=c.post('/api/dj/sample-saturday-neon',json={'personality':'Warm & Laid-back','reference':base64.b64encode(b'invalid audio').decode()})
        assert r.status_code==422
        results['invalid_reference']={'status':r.status_code,'detail':r.json()['detail']}
        r=c.post('/api/songs',json={'title':'Invalid duration','topic':'test','style':'jazz','mood':'warm','duration':999})
        assert r.status_code==422
        results['invalid_duration']={'status':r.status_code,'detail':r.json()['detail']}
    path=Path('docs/evidence/live-services.json');path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(results,indent=2))
    print(json.dumps(results,indent=2))

if __name__=='__main__':main()
