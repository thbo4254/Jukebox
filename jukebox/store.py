"""SQLite metadata + durable files; no caller-controlled filesystem paths."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import uuid


class Store:
    def __init__(self, root):
        self.root=Path(root)
        self.root.mkdir(parents=True,exist_ok=True)
        self.db=self.root/'library.sqlite3'
        with self.connect() as c:
            c.execute('CREATE TABLE IF NOT EXISTS songs (id TEXT PRIMARY KEY, doc TEXT NOT NULL)')

    def connect(self):
        return sqlite3.connect(self.db,timeout=20)

    def list(self):
        with self.connect() as c:
            return [json.loads(row[0]) for row in c.execute('SELECT doc FROM songs ORDER BY rowid DESC')]

    def get(self, song_id):
        with self.connect() as c:
            row=c.execute('SELECT doc FROM songs WHERE id=?',(song_id,)).fetchone()
        if not row:
            raise KeyError(song_id)
        return json.loads(row[0])

    def put(self, song):
        with self.connect() as c:
            c.execute('INSERT INTO songs VALUES (?,?) ON CONFLICT(id) DO UPDATE SET doc=excluded.doc', (song['id'],json.dumps(song)))
        return song

    def create(self,spec):
        return self.put(dict(spec,id=uuid.uuid4().hex,status='queued',error='',cover_status='pending',created_at=datetime.now(timezone.utc).isoformat()))

    def update(self,song_id,**fields):
        song=self.get(song_id); song.update(fields)
        return self.put(song)

    def save_audio(self,song_id,audio,provenance,duration):
        self.get(song_id)
        folder=self.root/song_id; folder.mkdir(exist_ok=True)
        temporary=folder/'audio.part'; temporary.write_bytes(audio); temporary.replace(folder/'audio.mp3')
        return self.update(song_id,status='ready',error='',provenance=provenance,actual_duration=duration)

    def media(self,song_id,kind):
        self.get(song_id)
        if kind not in ('audio','cover'):
            raise KeyError(kind)
        path=self.root/song_id/('audio.mp3' if kind=='audio' else 'cover.png')
        if not path.is_file() or not path.resolve().is_relative_to(self.root.resolve()):
            raise KeyError(kind)
        return path
