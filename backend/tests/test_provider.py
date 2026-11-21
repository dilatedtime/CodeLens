import os
import httpx
import pytest
from app.provider import OllamaProvider, ProviderError
from app.schemas import ReviewOutput


def response(data):
    return httpx.Response(200,json=data,request=httpx.Request('POST','http://localhost'))


def test_one_schema_repair(monkeypatch):
    provider=OllamaProvider()
    monkeypatch.setattr(provider,'models',lambda:[{'name':'test','digest':'123'}])
    calls=[]
    def send(*args,**kwargs):
        calls.append(kwargs['json'])
        return response({'message':{'content':'broken' if len(calls)==1 else '{"findings":[]}'}})
    monkeypatch.setattr(httpx,'post',send)
    parsed,_,metrics=provider.generate('test','Review source',ReviewOutput)
    assert parsed.findings==[]
    assert len(calls)==2 and metrics['schema_failures']==1
    assert calls[0]['format']['type']=='object'


def test_repair_is_bounded(monkeypatch):
    provider=OllamaProvider()
    monkeypatch.setattr(provider,'models',lambda:[{'name':'test'}])
    monkeypatch.setattr(httpx,'post',lambda *a,**k:response({'message':{'content':'bad'}}))
    with pytest.raises(ProviderError) as exc:
        provider.generate('test','Review',ReviewOutput)
    assert exc.value.failures==2


def test_missing_model(monkeypatch):
    provider=OllamaProvider()
    monkeypatch.setattr(provider,'models',lambda:[])
    with pytest.raises(ProviderError,match='not installed'):
        provider.generate('test','Review',ReviewOutput)


@pytest.mark.skipif(not os.getenv('CODELENS_REAL_MODEL'),reason='Opt-in real Ollama integration test')
def test_real_ollama():
    parsed,_,_=OllamaProvider().generate(os.environ['CODELENS_REAL_MODEL'],'Review main.py line 1: x = 1. Return findings array.',ReviewOutput)
    assert isinstance(parsed.findings,list)
