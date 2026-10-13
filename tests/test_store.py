import importlib.util
import pytest


def test_persistent_library_survives_restart_and_serves_only_known_media(tmp_path):
    assert importlib.util.find_spec('jukebox.store'), 'Persistent library missing'
    from jukebox.store import Store
    s=Store(tmp_path)
    song=s.create({'title':'Rain','topic':'cafe','style':'jazz','mood':'warm','duration':30,'instrumental':True,'lyrics':''})
    s.save_audio(song['id'],b'fixture',{'model':'test'},30.0)
    again=Store(tmp_path)
    assert again.get(song['id'])['title']=='Rain'
    assert again.media(song['id'],'audio').read_bytes()==b'fixture'
    assert again.list()[0]['status']=='ready'
    with pytest.raises(KeyError):
        again.media('../../etc/passwd','audio')
    with pytest.raises(KeyError):
        again.media(song['id'],'../../etc/passwd')
