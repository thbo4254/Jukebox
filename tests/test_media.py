import asyncio
import base64
import io
import json
import pytest
import httpx
from PIL import Image
from jukebox.services import Services, ServiceError
from test_services import config


def test_cover_is_validated_png_from_flux():
    assert hasattr(Services,'cover'), 'FLUX adapter missing'
    b=io.BytesIO(); Image.new('RGB',(32,32),'orange').save(b,format='PNG')
    def handler(req):
        p=json.loads(req.content)
        assert p['n']==1 and p['model']=='flux' and p['response_format']=='b64_json'
        assert 'rainy cafe' in p['prompt']
        return httpx.Response(200,json={'data':[{'b64_json':base64.b64encode(b.getvalue()).decode()}]})
    async def run():
        result=await Services(config(),httpx.MockTransport(handler)).cover({'title':'Rain','topic':'rainy cafe','style':'jazz','mood':'warm','cover_prompt':''})
        assert Image.open(io.BytesIO(result)).format=='PNG'
    asyncio.run(run())


def test_dj_uses_song_personality_and_ephemeral_reference():
    assert hasattr(Services,'dj'), 'DJ adapter missing'
    def handler(req):
        p=json.loads(req.content)
        if req.url.port==9001:
            assert 'Rain' in p['messages'][1]['content'] and 'Music Enthusiast' in p['messages'][0]['content']
            return httpx.Response(200,json={'choices':[{'message':{'content':'Here is Rain, a gentle piano trio.'}}]})
        assert p['model']=='chatterbox-v3' and p['voice']=='default' and p['language_id']=='en'
        assert p['ref_audio']==base64.b64encode(b'reference fixture').decode()
        return httpx.Response(200,content=b'speech fixture')
    async def run():
        result,text=await Services(config(),httpx.MockTransport(handler)).dj({'title':'Rain','topic':'cafe','style':'jazz','mood':'warm'},'Music Enthusiast',b'reference fixture')
        assert result==b'speech fixture' and text.startswith('Here is Rain')
    asyncio.run(run())
