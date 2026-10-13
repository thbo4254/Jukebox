"""Generate only original class-service assets; resume without repeating completed work.
Run from repository root: python -m scripts.generate_samples
Requires JUKEBOX_ENDPOINTS_FILE. Never prints upstream responses or configuration.
"""
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import soundfile as sf
from PIL import Image
from jukebox.config import load_config
from jukebox.services import Services, ServiceError

SPECS = [
 {'id':'amber-after-hours','title':'Amber After Hours','topic':'A quiet late-night cafe, watching rain paint the street','style':'warm jazz trio, piano, brushed drums, upright bass','mood':'relaxed and intimate','instrumental':True,'cover_prompt':'An amber-lit cafe window looking out onto a rainy street at night, glowing reflections'},
 {'id':'saturday-neon','title':'Saturday Neon','topic':'Meeting friends at the diner, then dancing together on a cheerful Saturday night','style':'upbeat retro soul-pop, grooving bass, bright rhythm guitar, handclaps','mood':'cheerful and playful','instrumental':False,'cover_prompt':'A coral and turquoise neon diner sign at dusk, friends silhouetted through the window, joyful vintage atmosphere'},
 {'id':'the-long-way-home','title':'The Long Way Home','topic':'Taking the scenic route home, winding country roads and a sunset, remembering the people waiting for you','style':'acoustic folk, fingerpicked acoustic guitar, gentle bass, soft percussion','mood':'cozy and reflective','instrumental':False,'cover_prompt':'A winding country road disappearing into rolling hills at sunset, warm peach sky, quiet rural landscape'},
]

async def main():
    services=Services(load_config())
    root=Path('samples'); root.mkdir(exist_ok=True)
    for initial in SPECS:
        folder=root/initial['id']; folder.mkdir(exist_ok=True)
        metadata=folder/'metadata.json'
        spec=json.loads(metadata.read_text()) if metadata.exists() else dict(initial,duration=30,lyrics='',generated_at=datetime.now(timezone.utc).isoformat())
        if not spec['instrumental'] and not spec['lyrics']:
            spec['lyrics']=await services.lyrics({k:spec[k] for k in ('topic','style','mood','duration')})
            spec['lyrics_model']=services.config['text'].model
            spec['lyrics_source']='Qwen class endpoint; passed unchanged to ACE-Step'
            metadata.write_text(json.dumps(spec,indent=2))
            print(spec['title'], 'Qwen lyrics ready', flush=True)
        if not (folder/'audio.mp3').exists():
            audio,provenance=await services.music(spec)
            (folder/'audio.mp3').write_bytes(audio)
            spec['provenance']=provenance
            metadata.write_text(json.dumps(spec,indent=2))
            print(spec['title'],'music downloaded',flush=True)
        if not (folder/'cover.png').exists():
            (folder/'cover.png').write_bytes(await services.cover(spec))
        spec['image_model']=services.config['image'].model
        spec['image_prompt']=services.cover_prompt(spec)
        info=sf.info(folder/'audio.mp3')
        spec['actual_duration']=info.duration
        spec['sample_rate']=info.samplerate
        spec['audio']='audio.mp3'; spec['cover']='cover.png'
        Image.open(folder/'cover.png').verify()
        metadata.write_text(json.dumps(spec,indent=2))
        print(spec['title'], 'VERIFIED',round(info.duration,3),'seconds',flush=True)

if __name__=='__main__':
    try:
        asyncio.run(main())
    except ServiceError as exc:
        print(str(exc),flush=True)
        raise SystemExit(1)
    except Exception as exc:
        print('Generation stopped:',type(exc).__name__,'(details suppressed for credential safety)',flush=True)
        raise SystemExit(1)
