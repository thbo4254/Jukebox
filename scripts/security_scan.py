"""Read-only hygiene check of prospective Git files. Never print key values."""
import hashlib
import json
from pathlib import Path
import subprocess
from jukebox.config import load_config


def main():
    config=load_config()
    keys={e.key.encode() for e in config.values()}
    paths=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z']).decode().split('\0')
    paths=[Path(p) for p in paths if p and Path(p).is_file()]
    bad=[]
    for path in paths:
        content=path.read_bytes()
        if any(key in content for key in keys):bad.append(str(path))
    forbidden=[str(p) for p in paths if p.parts[0] in ('data','uploads','voice-references','.venv')]
    print(json.dumps({'prospective_git_files':len(paths),'credential_matches':len(bad),'match_paths':bad,'forbidden_runtime_files':forbidden,'status':'PASS' if not bad and not forbidden else 'FAIL'}))
    if bad or forbidden:raise SystemExit(1)

if __name__=='__main__':main()
