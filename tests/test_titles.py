"""Offline contextual title regressions; no class services or user library."""
import asyncio
import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient
from jukebox.services import Services, ServiceError
from test_services import config
from test_app import FixtureServices


@pytest.mark.parametrize('instrumental', [True, False])
def test_qwen_title_uses_context_and_only_approved_vocal_lyrics(instrumental):
    spec = dict(topic='Rain over empty streets', style='Jazz trio', mood='Reflective',
                instrumental=instrumental, lyrics='  [Verse]\nMy edited words stay here  ')
    def handler(req):
        assert req.url.path == '/v1/chat/completions'
        payload = json.loads(req.content)
        assert payload['model'] == 'qwen'
        assert payload['max_tokens'] <= 100
        instruction = payload['messages'][0]['content'].lower()
        assert 'original' in instruction and 'clarification' in instruction
        data = json.loads(payload['messages'][1]['content'])
        assert all(data[k] == spec[k] for k in ('topic', 'style', 'mood', 'instrumental'))
        assert data.get('lyrics', '') == ('' if instrumental else spec['lyrics'])
        return httpx.Response(200, json={'choices': [{'message': {'content': 'After the Rain'}}]})
    async def run():
        service = Services(config(), httpx.MockTransport(handler))
        assert hasattr(service, 'title'), 'Contextual title adapter missing'
        assert await service.title(spec) == 'After the Rain'
    asyncio.run(run())


@pytest.mark.parametrize('instrumental', [True, False])
@pytest.mark.parametrize('title', ['', '   ', 'My chosen name'])
def test_job_prepares_blank_title_preserves_explicit_and_lyrics(tmp_path, instrumental, title):
    from jukebox.app import create_app
    seen = []
    class TitleServices(FixtureServices):
        async def title(self, spec):
            seen.append(spec.copy())
            return 'After the Rain'
        async def music(self, spec):
            assert spec['title'] == (title if title.strip() else 'After the Rain')
            assert spec['lyrics'] == '  [Verse]\nApproved words  '
            return await super().music(spec)
    app = create_app(tmp_path, services=TitleServices(), samples=None)
    with TestClient(app) as client:
        existing = app.state.store.create(dict(title='Old title', topic='Old description'))
        app.state.store.update(existing['id'], status='ready', cover_status='ready')
        before = app.state.store.get(existing['id'])
        response = client.post('/api/songs', headers={'X-Jukebox':'1'}, json=dict(
            title=title, topic='Rain over empty streets', style='Jazz', mood='Reflective',
            instrumental=instrumental, lyrics='  [Verse]\nApproved words  '))
        assert response.status_code == 202
        for _ in range(100):
            song = client.get('/api/songs/'+response.json()['id']).json()
            if song['cover_status'] == 'failed': break
            time.sleep(.01)
        assert song['status'] == 'ready'
        assert song['title'] == (title if title.strip() else 'After the Rain')
        assert len(seen) == (0 if title.strip() else 1)
        assert app.state.store.get(existing['id']) == before
        assert 'lyrics_model' not in song
        if not title.strip():
            assert song['title_status'] == 'generated'
            assert song['title_source'] == 'Qwen class endpoint'



@pytest.mark.parametrize('failure', ['timeout', 'exception'])
def test_title_failure_is_bounded_safe_and_audio_still_ready(tmp_path, monkeypatch, failure):
    import jukebox.app as module
    assert getattr(module, 'TITLE_TIMEOUT_SECONDS', None) == 15
    monkeypatch.setattr(module, 'TITLE_TIMEOUT_SECONDS', .02)
    cancelled = []
    class FailingTitle(FixtureServices):
        async def title(self, spec):
            if failure == 'exception':
                raise RuntimeError('<script>private upstream body</script>')
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.append(True)
    app = module.create_app(tmp_path, services=FailingTitle(), samples=None)
    with TestClient(app) as client:
        start = time.monotonic()
        response = client.post('/api/songs', headers={'X-Jukebox':'1'}, json=dict(
            topic='Rain', style='Jazz', mood='Warm'))
        assert response.status_code == 202
        for _ in range(100):
            song = client.get('/api/songs/'+response.json()['id']).json()
            if song['cover_status'] == 'failed': break
            time.sleep(.01)
        assert time.monotonic()-start < 1
        assert song['status'] == 'ready'
        assert song['title'] == 'Untitled track'
        assert song['title_status'] == 'fallback'
        assert 'title_source' not in song
        assert 'private' not in song['title_error']
        assert 'Untitled track' in song['title_error']
        assert bool(cancelled) == (failure == 'timeout')


@pytest.mark.parametrize('output', [' ', 'x'*101, '<img src=x onerror=alert(1)>',
                                     '**A Title**', 'First\nSecond', 'Bad\x00Title'])
def test_title_rejects_unusable_or_markup_output(output):
    def handler(req):
        return httpx.Response(200, json={'choices':[{'message':{'content':output}}]})
    async def run():
        service = Services(config(), httpx.MockTransport(handler))
        with pytest.raises(ServiceError):
            await service.title(dict(topic='Rain', style='Jazz', mood='Warm', instrumental=True))
    asyncio.run(run())


def test_pending_titles_reserve_admission_without_blocking_create(tmp_path):
    from jukebox.app import create_app
    class BlockedTitle(FixtureServices):
        async def title(self, spec):
            await asyncio.Event().wait()
    async def run():
        app = create_app(tmp_path, services=BlockedTitle(), samples=None)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://localhost', headers={'X-Jukebox':'1'}) as client:
                spec = dict(title='', topic='Rain', style='Jazz', mood='Warm')
                responses = await asyncio.wait_for(asyncio.gather(*(client.post('/api/songs', json=spec) for _ in range(4))), .5)
                assert [r.status_code for r in responses] == [202,202,202,429]
                await asyncio.sleep(0)
                songs = (await client.get('/api/songs')).json()
                assert len(songs) == 3
                assert sum(s['title_status']=='generating' for s in songs) == 1
                assert sum(s['title_status']=='pending' for s in songs) == 2
    asyncio.run(run())


@pytest.mark.parametrize('override', [dict(title='x'*101), dict(topic=''), dict(style=''), dict(mood=''), dict(duration=9), dict(duration=121), dict(instrumental=False, lyrics='')])
def test_optional_title_preserves_other_api_validation(tmp_path, override):
    from jukebox.app import create_app
    with TestClient(create_app(tmp_path, services=FixtureServices(), samples=None)) as client:
        spec = dict(title='', topic='Rain', style='Jazz', mood='Warm')
        spec.update(override)
        response = client.post('/api/songs', headers={'X-Jukebox':'1'}, json=spec)
        assert response.status_code == 422
        assert client.get('/api/songs').json() == []


def test_music_retry_does_not_rename_generated_title(tmp_path):
    from jukebox.app import create_app
    calls = []
    class RetryServices(FixtureServices):
        async def title(self, spec):
            calls.append('title')
            return 'Rainlight'
        async def music(self, spec):
            calls.append('music')
            if calls.count('music') == 1:
                raise ServiceError('Fixture music failure')
            return await super().music(spec)
    app = create_app(tmp_path, services=RetryServices(), samples=None)
    with TestClient(app) as client:
        response = client.post('/api/songs', headers={'X-Jukebox':'1'}, json=dict(topic='Rain', style='Jazz', mood='Warm'))
        song_id = response.json()['id']
        for _ in range(100):
            song = client.get('/api/songs/'+song_id).json()
            if song['status'] == 'failed': break
            time.sleep(.01)
        assert song['title'] == 'Rainlight'
        assert client.post('/api/songs/'+song_id+'/retry', headers={'X-Jukebox':'1'}).status_code == 202
        for _ in range(100):
            song = client.get('/api/songs/'+song_id).json()
            if song['status'] == 'ready': break
            time.sleep(.01)
        assert song['status'] == 'ready' and song['title'] == 'Rainlight'
        assert calls == ['title','music','music']
