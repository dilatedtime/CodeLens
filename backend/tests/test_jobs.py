from datetime import timedelta
import pytest
from sqlalchemy import select
from app.db import Session, Finding, AnalysisJob, now
from app.jobs import process_job
from app.provider import ProviderError
from app.schemas import ReviewOutput, ArtifactOutput


class FakeProvider:
    def generate(self, model, prompt, schema):
        if schema is ReviewOutput:
            parsed = schema(findings=[dict(path='main.py', start_line=1, end_line=1, category='bug', severity='low', title='Test-only diagnostic', explanation='Mock output, not actual inference.', evidence='import os')])
        else:
            parsed = ArtifactOutput(markdown='Test-only explanation', proposed_code='x = 2\n')
        return parsed, parsed.model_dump_json(), {'schema_failures':0, 'digest':'mock-digest'}


class OfflineProvider:
    def generate(self, *args):
        raise ProviderError('Ollama offline')


def setup_job(client, mode='hybrid', task='review', models=None):
    p = client.post('/api/projects',json={'name':'Test project'}).json()
    s = client.post(f"/api/projects/{p['id']}/submissions",json={'path':'main.py','code':'import os\nx = 1\n'}).json()
    j = client.post(f"/api/submissions/{s['id']}/jobs",json={'mode':mode,'models':models or ['qwen2.5-coder:1.5b'],'task':task,'path':'main.py'}).json()
    return p,s,j


def test_submit_review_export_feedback_delete(client):
    p,s,j = setup_job(client)
    process_job(j['id'], FakeProvider())
    result = client.get(f"/api/jobs/{j['id']}").json()
    assert result['status']=='completed'
    assert result['created_at'].endswith('Z') or result['created_at'].endswith('+00:00')
    assert result['runs'][0]['metrics']['latency_seconds']>0
    assert result['runs'][0]['findings']
    f = result['runs'][0]['findings'][0]
    assert client.post(f"/api/findings/{f['id']}/feedback",json={'verdict':'useful'}).status_code==200
    assert client.get(f"/api/jobs/{j['id']}").json()['runs'][0]['findings'][0]['feedback']=='useful'
    assert client.get(f"/api/jobs/{j['id']}/export").json()['id']==j['id']
    assert '# CodeLens review' in client.get(f"/api/jobs/{j['id']}/export?format=markdown").text
    assert 'CodeLens' in client.get(f"/api/jobs/{j['id']}/export?format=html").text
    metrics_res = client.get(f"/api/submissions/{s['id']}/metrics").json()
    assert 'score' in metrics_res
    assert metrics_res['score']['grade'] in ('A', 'B', 'C', 'D', 'F')
    # Idempotency: a completed job does not duplicate its findings.
    process_job(j['id'], FakeProvider())
    assert len(client.get(f"/api/jobs/{j['id']}").json()['runs'])==1
    assert client.delete(f"/api/projects/{p['id']}").status_code==204
    assert client.get(f"/api/submissions/{s['id']}").status_code==404
    with Session() as db:
        assert db.scalar(select(Finding.id)) is None


def test_offline_hybrid_keeps_static_findings(client):
    _,_,j = setup_job(client)
    process_job(j['id'], OfflineProvider())
    result = client.get(f"/api/jobs/{j['id']}").json()
    assert result['status']=='partial'
    assert any('ruff' in f['sources'] for f in result['runs'][0]['findings'])
    assert 'offline' in result['errors'][0]


def test_ai_only_failure(client):
    _,_,j = setup_job(client,mode='ai')
    process_job(j['id'], OfflineProvider())
    assert client.get(f"/api/jobs/{j['id']}").json()['status']=='failed'


def test_patch_is_preview_only(client):
    _,s,j = setup_job(client,mode='ai',task='patch')
    process_job(j['id'], FakeProvider())
    artifact = client.get(f"/api/jobs/{j['id']}").json()['runs'][0]['artifacts'][0]
    assert artifact['syntax_valid']
    assert '+x = 2' in artifact['diff']
    assert client.get(f"/api/submissions/{s['id']}").json()['files'][0]['content']=='import os\nx = 1\n'


def test_sequential_comparison(client):
    _,_,j=setup_job(client,mode='ai',models=['qwen2.5-coder:1.5b','deepseek-coder:1.3b'])
    calls=[]
    class Recorder(FakeProvider):
        def generate(self,model,prompt,schema):
            calls.append((model,prompt))
            return super().generate(model,prompt,schema)
    process_job(j['id'],Recorder())
    assert [x[0] for x in calls]==['qwen2.5-coder:1.5b','deepseek-coder:1.3b']
    assert calls[0][1]==calls[1][1]


def test_stale_jobs_and_active_delete(client):
    p,_,j=setup_job(client)
    assert client.delete(f"/api/projects/{p['id']}").status_code==409
    with Session() as db:
        db.get(AnalysisJob,j['id']).updated_at=now()-timedelta(days=1)
        db.commit()
    assert client.get(f"/api/jobs/{j['id']}").json()['status']=='failed'


def test_unallowed_model(client):
    _,s,_=setup_job(client)
    res=client.post(f"/api/submissions/{s['id']}/jobs",json={'models':['arbitrary-model']})
    assert res.status_code==400


def test_queue_failure_is_persisted(client,monkeypatch):
    import app.main as main
    def fail(_):
        raise ConnectionError()
    monkeypatch.setattr(main,'enqueue',fail)
    _,_,j=setup_job(client)
    assert client.get(f"/api/jobs/{j['id']}").json()['status']=='failed'
