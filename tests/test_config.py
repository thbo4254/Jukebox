from pathlib import Path
import importlib.util
import pytest


def test_external_config_reads_only_required_services(tmp_path):
    assert importlib.util.find_spec('jukebox') is not None, 'External configuration package is missing'
    from jukebox.config import load_config
    p = tmp_path / 'endpoints.txt'
    p.write_text('\n'.join(f'Base URL: http://dobolyi.com:{port}/v1\nAPI Key: unit-test-key\nModel: model-{port}' for port in (9000,9001,9006,9007,9008)))
    config = load_config(p)
    assert set(config) == {'text','image','music','speech'}
    assert config['text'].base == 'http://dobolyi.com:9001'
    assert config['text'].model == 'model-9001'
    assert config['music'].headers == {'Authorization': 'Bearer unit-test-key'}
    assert 'unit-test-key' not in repr(config)
