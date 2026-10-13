from pathlib import Path
from fastapi.testclient import TestClient
from jukebox.app import ROOT, create_app
from test_app import FixtureServices


def test_browser_shell_has_accessible_library_create_dj_and_player(tmp_path):
    assert (ROOT/'jukebox/static/index.html').is_file(), 'Browser interface missing'
    with TestClient(create_app(tmp_path,services=FixtureServices(),samples=None)) as c:
        r=c.get('/')
        assert r.status_code==200
        for label in ('Your collection','Create a song','DJ booth','Review lyrics','Play','Skip'):
            assert label in r.text
        for name in ('app.js','player.js','style.css','placeholder.svg'):
            assert c.get('/static/'+name).status_code==200
        assert "frame-ancestors 'none'" in r.headers['content-security-policy']
