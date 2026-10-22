import pytest
from fastapi.testclient import TestClient
from jukebox.app import create_app
from test_app import FixtureServices

@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path,services=FixtureServices(),samples=None)) as c:
        yield c

@pytest.mark.parametrize('headers', [{},{'X-Jukebox':'1','Origin':'https://evil.example'},{'X-Jukebox':'1','Host':'evil.example'},{'X-Jukebox':'1','Sec-Fetch-Site':'cross-site'}])
def test_cross_origin_side_effects_rejected(client,headers):
    r=client.post('/api/lyrics',headers=headers,json={'title':'x','topic':'x','style':'x','mood':'x'})
    assert r.status_code==403


def test_large_body_rejected_before_parsing(client):
    r=client.post('/api/lyrics',headers={'X-Jukebox':'1','Content-Type':'application/json'},content=b'x'*(9*1024*1024+1))
    assert r.status_code==413

@pytest.mark.parametrize('duration',[0,9,121,9999])
def test_duration_rejected(client,duration):
    r=client.post('/api/songs',headers={'X-Jukebox':'1'},json={'title':'x','topic':'x','style':'x','mood':'x','duration':duration})
    assert r.status_code==422


def test_vocal_requires_reviewed_lyrics(client):
    r=client.post('/api/songs',headers={'X-Jukebox':'1'},json={'title':'x','topic':'x','style':'x','mood':'x','instrumental':False})
    assert r.status_code==422 and 'review' in r.json()['detail']


def test_no_arbitrary_file_reads(client):
    assert client.get('/static/class-endpoints.txt').status_code==404
    assert client.get('/api/songs/unknown/audio').status_code==404
