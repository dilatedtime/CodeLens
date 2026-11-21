import json
from contextlib import asynccontextmanager
from datetime import timezone
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy import select, delete, text
from .config import settings
from .db import Session, Project, Submission, SourceFile, AnalysisJob, ModelRun, Finding, GeneratedArtifact, FindingFeedback, now
from .schemas import ProjectInput, CodeInput, JobInput, FeedbackInput
from .ingestion import ingest, content_hash
from .context import source_index
from .metrics import analyze_file_metrics, compute_project_score
from .provider import OllamaProvider, ProviderError
from .jobs import enqueue


def require(session, cls, key):
    value = session.get(cls, key)
    if value is None:
        raise HTTPException(404, 'Not found')
    return value


def job_dict(job):
    data = {k: getattr(job, k) for k in ('id', 'submission_id', 'status', 'stage', 'request', 'errors')}
    for key in ('created_at', 'updated_at'):
        value = getattr(job, key)
        data[key] = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return data


def expire_stale(session):
    for job in session.scalars(select(AnalysisJob).where(AnalysisJob.status.in_(['queued', 'running']))):
        updated = job.updated_at.replace(tzinfo=timezone.utc) if job.updated_at.tzinfo is None else job.updated_at
        if (now() - updated).total_seconds() > settings.job_stale_seconds:
            job.status = 'failed'
            job.stage = 'Worker timed out'
            job.errors = ['Job expired. Check the worker and create a new analysis.']
    session.commit()


@asynccontextmanager
async def lifespan(app):
    with Session() as session:
        session.execute(text('SELECT 1'))
        if settings.queue_mode == 'local':
            for job in session.scalars(select(AnalysisJob).where(AnalysisJob.status.in_(['queued', 'running']))):
                job.status, job.stage, job.errors = 'failed', 'Interrupted by application restart', ['Start a new analysis to retry.']
            session.commit()
    yield


app = FastAPI(title='CodeLens API', version='1.0.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins.split(','), allow_methods=['GET', 'POST', 'DELETE'], allow_headers=['Content-Type'])


@app.get('/api/health')
def health():
    database, queue = True, settings.queue_mode == 'local'
    try:
        with Session() as session:
            session.execute(text('SELECT 1'))
    except Exception:
        database = False
    if settings.queue_mode == 'rq':
        try:
            from redis import Redis
            from rq import Worker
            conn = Redis.from_url(settings.redis_url, socket_timeout=2)
            queue = bool(conn.ping() and Worker.all(connection=conn))
        except Exception:
            queue = False
    return {'status': 'ready' if database and queue else 'degraded', 'database': database, 'queue': queue, 'queue_mode': settings.queue_mode}


@app.get('/api/models')
def models():
    try:
        installed, error = OllamaProvider().models(), None
    except ProviderError as exc:
        installed, error = [], str(exc)
    names = {m.get('name') for m in installed} | {m.get('model') for m in installed}
    return {'models': [{'name': m, 'installed': m in names} for m in settings.models], 'default': settings.default_model, 'error': error,
            'settings': {'context_chars': settings.context_chars, 'context_tokens': settings.context_tokens, 'output_tokens': settings.output_tokens,
                         'temperature': settings.temperature, 'max_files': settings.max_files, 'max_upload_bytes': settings.max_upload_bytes}}


@app.get('/api/projects')
def projects():
    with Session() as session:
        return [{'id': p.id, 'name': p.name, 'created_at': p.created_at} for p in session.scalars(select(Project).order_by(Project.created_at.desc()))]


@app.post('/api/projects', status_code=201)
def create_project(body: ProjectInput):
    with Session() as session:
        p = Project(name=body.name.strip() or 'Untitled project')
        session.add(p)
        session.commit()
        return {'id': p.id, 'name': p.name}


@app.get('/api/projects/{project_id}')
def project_detail(project_id: str):
    with Session() as session:
        expire_stale(session)
        p = require(session, Project, project_id)
        submissions = list(session.scalars(select(Submission).where(Submission.project_id == project_id).order_by(Submission.created_at.desc())))
        jobs = list(session.scalars(select(AnalysisJob).join(Submission).where(Submission.project_id == project_id).order_by(AnalysisJob.created_at.desc())))
        return {'id': p.id, 'name': p.name, 'submissions': [{'id': s.id, 'content_hash': s.content_hash, 'created_at': s.created_at} for s in submissions], 'jobs': [job_dict(j) for j in jobs]}


@app.delete('/api/projects/{project_id}', status_code=204)
def delete_project(project_id: str):
    with Session() as session:
        p = require(session, Project, project_id)
        expire_stale(session)
        active = session.scalar(select(AnalysisJob.id).join(Submission).where(Submission.project_id == project_id, AnalysisJob.status.in_(['queued', 'running'])).limit(1))
        if active:
            raise HTTPException(409, 'Wait for active analysis to finish before deleting this project.')
        session.delete(p)
        session.commit()


def save_submission(project_id, name, data):
    try:
        files, skipped = ingest(name, data)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    with Session() as session:
        require(session, Project, project_id)
        sub = Submission(project_id=project_id, content_hash=content_hash(files), skipped=skipped)
        session.add(sub)
        session.flush()
        session.add_all(SourceFile(submission_id=sub.id, path=path, content=content) for path, content in files.items())
        session.commit()
        return {'id': sub.id, 'content_hash': sub.content_hash, 'skipped': skipped}


@app.post('/api/projects/{project_id}/submissions', status_code=201)
def submit_code(project_id: str, body: CodeInput):
    if not body.path.endswith('.py'):
        raise HTTPException(400, 'Pasted source requires a .py filename')
    return save_submission(project_id, body.path, body.code.encode())


@app.post('/api/projects/{project_id}/uploads', status_code=201)
async def upload(project_id: str, file: UploadFile = File(...)):
    data = await file.read(settings.max_upload_bytes + 1)
    await file.close()
    return save_submission(project_id, file.filename or 'upload.py', data)


@app.get('/api/submissions/{submission_id}')
def submission(submission_id: str):
    with Session() as session:
        s = require(session, Submission, submission_id)
        files = list(session.scalars(select(SourceFile).where(SourceFile.submission_id == submission_id).order_by(SourceFile.path)))
        return {'id': s.id, 'project_id': s.project_id, 'content_hash': s.content_hash, 'skipped': s.skipped,
                'files': [{'path': f.path, 'content': f.content, 'index': source_index(f.path, f.content)} for f in files]}


@app.get('/api/submissions/{submission_id}/metrics')
def submission_metrics(submission_id: str):
    with Session() as session:
        s = require(session, Submission, submission_id)
        files = list(session.scalars(select(SourceFile).where(SourceFile.submission_id == submission_id).order_by(SourceFile.path)))
        metrics_list = [analyze_file_metrics(f.path, f.content) for f in files]
        all_smells = [smell for m in metrics_list for smell in m.get('smells', [])]
        score = compute_project_score(metrics_list, all_smells)
        return {
            'submission_id': s.id,
            'project_id': s.project_id,
            'score': score,
            'files': metrics_list,
        }


@app.post('/api/submissions/{submission_id}/jobs', status_code=202)
def start_job(submission_id: str, body: JobInput):
    if any(m not in settings.models for m in body.models):
        raise HTTPException(400, 'Select an allowed model from /api/models')
    if len(set(body.models)) != len(body.models):
        raise HTTPException(400, 'Select each model only once')
    if body.mode == 'static' and body.task != 'review':
        raise HTTPException(400, 'Generated artifacts require an AI model')
    with Session() as session:
        require(session, Submission, submission_id)
        paths = list(session.scalars(select(SourceFile.path).where(SourceFile.submission_id == submission_id)))
        if body.path and body.path not in paths:
            raise HTTPException(400, 'Selected file does not exist')
        if body.task in ('patch', 'docstrings') and body.path is None:
            raise HTTPException(400, 'Select a file for proposed changes')
        job = AnalysisJob(submission_id=submission_id, request=body.model_dump())
        session.add(job)
        session.commit()
        job_id = job.id
    try:
        enqueue(job_id)
    except Exception:
        with Session() as session:
            job = session.get(AnalysisJob, job_id)
            job.status, job.errors = 'failed', ['Queue unavailable. Start Redis and the worker, then retry.']
            session.commit()
    return {'id': job_id}


@app.get('/api/jobs/{job_id}')
def get_job(job_id: str):
    with Session() as session:
        expire_stale(session)
        job = require(session, AnalysisJob, job_id)
        runs = []
        for run in session.scalars(select(ModelRun).where(ModelRun.job_id == job_id)):
            findings = []
            for f in session.scalars(select(Finding).where(Finding.run_id == run.id)):
                feedback = session.get(FindingFeedback, f.id)
                findings.append({'id': f.id, **f.data, 'feedback': feedback.verdict if feedback else None})
            artifacts = [{'id': a.id, 'kind': a.kind, **a.data} for a in session.scalars(select(GeneratedArtifact).where(GeneratedArtifact.run_id == run.id))]
            runs.append({'id': run.id, 'model': run.model, 'status': run.status, 'metrics': run.metrics, 'coverage': run.coverage, 'error': run.error, 'findings': findings, 'artifacts': artifacts})
        return {**job_dict(job), 'runs': runs}


@app.get('/api/runs/{run_id}/raw')
def raw_response(run_id: str):
    with Session() as session:
        return {'raw_response': require(session, ModelRun, run_id).raw_response}


@app.post('/api/findings/{finding_id}/feedback')
def feedback(finding_id: str, body: FeedbackInput):
    with Session() as session:
        require(session, Finding, finding_id)
        session.merge(FindingFeedback(finding_id=finding_id, verdict=body.verdict))
        session.commit()
        return {'verdict': body.verdict}


@app.get('/api/jobs/{job_id}/export')
def export(job_id: str, format: str = 'json'):
    result = get_job(job_id)
    if format == 'json':
        content, media = json.dumps(result, default=str, indent=2), 'application/json'
        extension = 'json'
    elif format == 'markdown':
        chunks = [f"# CodeLens review\n\nStatus: {result['status']}\n\nJob: {job_id}\n"]
        for run in result['runs']:
            chunks.append(f"## {run['model']}\n\nStatus: {run['status']}\n\nCoverage: {json.dumps(run['coverage'])}\n\n{run['error']}\n")
            for f in run['findings']:
                chunks.append(f"### {f['severity'].upper()}: {f['title']}\n\n{f['path']}:{f['start_line']} · {', '.join(f['sources'])} · {f['validation']}\n\n{f['explanation']}\n\nSuggested fix: {f['suggested_fix']}\n")
            for a in run['artifacts']:
                chunks.append(f"## {a['kind']}\n\n{a['markdown']}\n")
        content, media = '\n'.join(chunks), 'text/markdown'
        extension = 'md'
    elif format == 'html':
        runs_html = []
        for run in result['runs']:
            items_html = []
            for f in run['findings']:
                sev = f['severity'].lower()
                border_color = '#dc2626' if sev == 'critical' else ('#ea580c' if sev == 'high' else ('#d97706' if sev == 'medium' else '#2563eb'))
                badge_bg = '#fef2f2' if sev == 'critical' else ('#fff7ed' if sev == 'high' else ('#fffbeb' if sev == 'medium' else '#eff6ff'))
                items_html.append(f"""
                <div style="border: 1px solid #e5e7eb; border-left: 5px solid {border_color}; border-radius: 8px; padding: 16px; margin-bottom: 14px; background: #ffffff;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <span style="font-weight: 700; color: {border_color}; text-transform: uppercase; font-size: 0.75rem; background: {badge_bg}; padding: 3px 8px; border-radius: 4px; border: 1px solid {border_color}33;">{f['severity']} &bull; {f['category']}</span>
                        <span style="color: #6b7280; font-family: monospace; font-size: 0.85rem;">{f['path']}:{f['start_line']}-{f['end_line']} ({', '.join(f.get('sources', []))})</span>
                    </div>
                    <h3 style="margin: 0 0 6px 0; color: #111827; font-size: 1.05rem;">{f['title']}</h3>
                    <p style="color: #4b5563; font-size: 0.95rem; margin: 0 0 10px 0; line-height: 1.5;">{f['explanation']}</p>
                    {f'<pre style="background: #f8fafc; border: 1px solid #e2e8f0; padding: 10px; border-radius: 6px; font-size: 0.85rem; overflow-x: auto; color: #1e293b; font-family: Consolas, monospace;"><code>{f["evidence"]}</code></pre>' if f.get('evidence') else ''}
                    {f'<p style="color: #047857; font-size: 0.9rem; margin: 8px 0 0 0;"><strong>Suggested Fix:</strong> {f["suggested_fix"]}</p>' if f.get('suggested_fix') else ''}
                </div>
                """)
            artifacts_html = []
            for a in run['artifacts']:
                artifacts_html.append(f"""
                <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin-top: 16px;">
                    <h4 style="margin: 0 0 10px 0; text-transform: uppercase; color: #0369a1;">Generated {a['kind']}</h4>
                    <pre style="white-space: pre-wrap; font-family: inherit; font-size: 0.9rem; color: #334155;">{a['markdown']}</pre>
                </div>
                """)
            runs_html.append(f"""
            <div style="background: #ffffff; border-radius: 12px; border: 1px solid #e5e7eb; padding: 24px; margin-bottom: 24px; box-shadow: 0 1px 2px rgba(0,0,0,0.04);">
                <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #f3f4f6; padding-bottom: 12px; margin-bottom: 16px;">
                    <h2 style="margin: 0; font-size: 1.25rem; color: #1e293b;">Model: <code style="background: #f1f5f9; padding: 2px 6px; border-radius: 4px;">{run['model']}</code></h2>
                    <span style="background: #ecfdf5; color: #047857; padding: 3px 10px; border-radius: 9999px; font-weight: 600; font-size: 0.8rem; text-transform: uppercase;">{run['status']}</span>
                </div>
                {''.join(items_html) if items_html else '<p style="color: #6b7280; font-style: italic;">No findings reported by this analyzer.</p>'}
                {''.join(artifacts_html)}
            </div>
            """)
        content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>CodeLens Audit Report - {job_id}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #f8fafc; color: #0f172a; margin: 0; padding: 32px 16px; }}
        .container {{ max-width: 960px; margin: 0 auto; }}
        .header {{ background: linear-gradient(135deg, #0284c7, #2563eb); color: #ffffff; padding: 32px; border-radius: 16px; margin-bottom: 28px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 style="margin: 0 0 8px 0; font-size: 1.8rem; font-weight: 800; letter-spacing: -0.025em;">CodeLens Code Review Audit Report</h1>
            <p style="margin: 0; opacity: 0.9; font-size: 0.95rem;">Job ID: <code>{job_id}</code> &bull; Overall Status: <strong>{result['status'].upper()}</strong></p>
        </div>
        {''.join(runs_html)}
    </div>
</body>
</html>"""
        media = 'text/html'
        extension = 'html'
    else:
        raise HTTPException(400, 'Use json, markdown, or html')
    return Response(content, media_type=media, headers={'Content-Disposition': f'attachment; filename="codelens-{job_id}.{extension}"'})
