"""Run with python -m jukebox; bind only to the local computer."""
import os
import uvicorn

if __name__ == '__main__':
    uvicorn.run('jukebox.app:create_app',factory=True,host='127.0.0.1',port=int(os.environ.get('JUKEBOX_PORT','8765')),access_log=False)
