"""Secrets stay in memory; never log endpoint objects or upstream responses."""
from dataclasses import dataclass, field
from pathlib import Path
import os
from urllib.parse import urlsplit

PORTS = {9001: 'text', 9006: 'image', 9007: 'music', 9008: 'speech'}

@dataclass
class Endpoint:
    base: str
    model: str = ''
    key: str = field(default='', repr=False)

    @property
    def headers(self):
        return {'Authorization': 'Bearer ' + self.key}


def load_config(path=None):
    path = path or os.environ.get('JUKEBOX_ENDPOINTS_FILE')
    if not path:
        raise ValueError('Set JUKEBOX_ENDPOINTS_FILE to your external class-endpoints.txt and restart.')
    try:
        lines = Path(path).read_text(encoding='utf-8-sig').splitlines()
    except OSError:
        raise ValueError('Cannot read endpoint configuration. Check JUKEBOX_ENDPOINTS_FILE and restart.') from None
    config, current = {}, None
    for line in lines:
        label, sep, value = line.partition(':')
        label, value = label.strip().lower(), value.strip()
        if label == 'base url':
            current = None
            u = urlsplit(value)
            if u.hostname == 'dobolyi.com' and u.port in PORTS and u.scheme in ('http','https') and not u.username:
                current = Endpoint(f'{u.scheme}://{u.netloc}')
                config[PORTS[u.port]] = current
        elif current and label == 'api key':
            current.key = value
        elif current and label == 'model':
            current.model = value
    if set(config) != set(PORTS.values()) or any(not e.key for e in config.values()):
        raise ValueError('Endpoint file must contain Base URL, API Key and Model for class ports 9001, 9006, 9007 and 9008.')
    return config
