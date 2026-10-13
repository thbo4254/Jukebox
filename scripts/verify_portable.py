"""Agent-only fresh-copy install check. Does not replace teammate ZIP testing."""
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

root=Path.cwd()
destination=Path(tempfile.mkdtemp(prefix='jukebox-clean-'))
paths=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z']).decode().split('\0')
for raw in paths:
    if not raw:continue
    p=Path(raw)
    if not p.is_file():continue
    target=destination/p;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
print('FRESH_COPY',destination,flush=True)
subprocess.run(['uv','venv',str(destination/'.venv'),'--python',sys.executable,'--seed'],check=True)
python=destination/'.venv'/('Scripts/python.exe' if platform.system()=='Windows' else 'bin/python')
subprocess.run([str(python),'-m','pip','install','-r','requirements-dev.txt'],cwd=destination,check=True)
tests=subprocess.run([str(python),'-m','pytest','-q'],cwd=destination,check=True,capture_output=True,text=True)
print(tests.stdout,flush=True)
js=subprocess.run(['node','--test','tests/player.test.mjs'],cwd=destination,check=True,capture_output=True,text=True)
print(js.stdout,flush=True)
# Run the local app with no credentials and verify the bundled originals still work.
probe="""
from fastapi.testclient import TestClient
from jukebox.app import create_app
import soundfile as sf
import io
from PIL import Image
with TestClient(create_app()) as c:
    assert not c.get('/api/status').json()['configured']
    songs=c.get('/api/songs').json()
    assert len(songs)==3
    for song in songs:
        audio=c.get('/api/songs/'+song['id']+'/audio')
        assert audio.status_code==200 and sf.info(io.BytesIO(audio.content)).duration==30
        Image.open(io.BytesIO(c.get('/api/songs/'+song['id']+'/cover').content)).verify()
    assert c.get('/').status_code==200
    print('Fresh installation: three playable samples, three covers, UI, safe missing-config notice verified')
"""
import os
env=dict(os.environ);env.pop('JUKEBOX_ENDPOINTS_FILE',None);env.pop('JUKEBOX_DATA_DIR',None)
verified=subprocess.run([str(python),'-c',probe],cwd=destination,env=env,check=True,capture_output=True,text=True)
print(verified.stdout,flush=True)
report={'kind':'Agent fresh-copy install, not teammate GitHub ZIP test','platform':platform.platform(),'python':platform.python_version(),'pip_install':'passed','pytest':tests.stdout.strip(),'node':js.stdout.strip(),'fresh_install':verified.stdout.strip(),'copied_files':len([p for p in paths if p]),'no_credentials_used':True}
(root/'docs/evidence/portable-install.json').write_text(json.dumps(report,indent=2))
print('FRESH_COPY_RETAINED',destination,flush=True)
