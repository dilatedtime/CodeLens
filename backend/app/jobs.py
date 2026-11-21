import ast
import difflib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import select, delete
from .config import settings
from .db import Session, AnalysisJob, SourceFile, ModelRun, Finding, GeneratedArtifact, now
from .context import build_context
from .analysis import run_static, validate_finding, deduplicate
from .provider import OllamaProvider, ProviderError, get_default_provider
from .schemas import ReviewOutput, ArtifactOutput
from .prompts import REVIEW, TASKS, PROMPT_VERSION

executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='codelens')


def enqueue(job_id):
    if settings.queue_mode == 'rq':
        from redis import Redis
        from rq import Queue
        Queue('reviews', connection=Redis.from_url(settings.redis_url)).enqueue(
            'app.jobs.process_job', job_id, job_id=job_id, job_timeout=settings.job_stale_seconds)
    else:
        executor.submit(process_job, job_id)


def stage(job_id, text):
    with Session() as session:
        job = session.get(AnalysisJob, job_id)
        if job is None or job.status not in ('queued', 'running'):
            raise RuntimeError('Job no longer active')
        job.stage, job.status, job.updated_at = text, 'running', now()
        session.commit()


def process_job(job_id, provider=None):
    provider = provider or get_default_provider()
    try:
        with Session() as session:
            job = session.get(AnalysisJob, job_id)
            if job is None or job.status in ('completed', 'partial', 'failed'):
                return
            # Rerunning an interrupted job replaces its incomplete runs atomically.
            session.execute(delete(ModelRun).where(ModelRun.job_id == job_id))
            session.commit()
            request = job.request
            files = {x.path: x.content for x in session.scalars(select(SourceFile).where(SourceFile.submission_id == job.submission_id))}
        stage(job_id, 'Parsing source and preparing context')
        context, coverage = build_context(files, settings.context_chars, request.get('path'), request.get('symbol'))
        static, static_errors, raw_static = [], [], {}
        static_started = time.perf_counter()
        if request['task'] == 'review' and request['mode'] != 'ai':
            stage(job_id, 'Running Ruff and Bandit')
            static, static_errors, raw_static = run_static(files)
        static_seconds = time.perf_counter() - static_started
        models = ['static'] if request['mode'] == 'static' else request['models']
        errors = list(static_errors)
        results = []
        for model in models:
            stage(job_id, f'Analyzing with {model}')
            started = time.perf_counter()
            selected_coverage = dict(coverage)
            if model == 'static':
                selected_coverage = {'included_lines': sum(len(x.splitlines()) for x in files.values()), 'total_lines': sum(len(x.splitlines()) for x in files.values()), 'complete': not static_errors, 'omitted_units': [], 'note': 'All accepted files sent to static tools; tool errors are listed separately.'}
            metrics = {'prompt_version': PROMPT_VERSION, 'mode': request['mode'], 'static_seconds': round(static_seconds, 3)}
            findings = list(static)
            artifact, raw, error = None, '', ''
            status = 'partial' if static_errors else 'completed'
            if model != 'static':
                try:
                    if context == '[]':
                        raise ProviderError('No complete source unit fits the context budget. Submit a smaller file or increase CONTEXT_CHARS.')
                    task = request['task']
                    instruction = REVIEW if task == 'review' else TASKS[task]
                    prompt = f"{instruction}\nAudience: {request.get('audience', 'beginner')}. Selected file: {request.get('path')}. Selected symbol: {request.get('symbol')}.\n<source_data>\n{context}\n</source_data>"
                    # Identical review context across static/AI/hybrid evaluation;
                    # hybrid combines independent findings after inference.
                    parsed, raw, provider_metrics = provider.generate(model, prompt, ReviewOutput if task == 'review' else ArtifactOutput)
                    metrics.update(provider_metrics)
                    if task == 'review':
                        findings += [validate_finding(x, files) for x in parsed.findings]
                    else:
                        artifact = parsed.model_dump()
                        artifact['path'] = request.get('path')
                        artifact['syntax_valid'] = None
                        if artifact['proposed_code']:
                            original = files.get(request.get('path'), '')
                            artifact['diff'] = ''.join(difflib.unified_diff(original.splitlines(True), artifact['proposed_code'].splitlines(True), fromfile='original.py', tofile='proposed.py'))
                            try:
                                ast.parse(artifact['proposed_code'])
                                artifact['syntax_valid'] = True
                            except (SyntaxError, ValueError, RecursionError):
                                artifact['syntax_valid'] = False
                        artifact['warning'] = 'AI-generated suggestion. Not executed; syntax checks do not prove correctness.'
                    if not coverage['complete']:
                        status = 'partial'
                except ProviderError as exc:
                    error, raw = str(exc), exc.raw
                    metrics['schema_failures'] = exc.failures
                    errors.append(f'{model}: {error}')
                    status = 'partial' if request['mode'] == 'hybrid' and request['task'] == 'review' and len(raw_static) else 'failed'
            metrics['model_seconds'] = round(time.perf_counter() - started, 3) if model != 'static' else 0
            metrics['latency_seconds'] = round(time.perf_counter() - started + static_seconds, 3)
            findings = deduplicate(findings)
            metrics['finding_count'] = len(findings)
            with Session() as session:
                job = session.get(AnalysisJob, job_id)
                if job is None or job.status != 'running':
                    return
                run = ModelRun(job_id=job_id, model=model, status=status, metrics=metrics, coverage=selected_coverage,
                    raw_response=json.dumps({'model': raw, 'static': raw_static}), error=error)
                session.add(run)
                session.flush()
                session.add_all(Finding(run_id=run.id, data=f) for f in findings)
                if artifact:
                    session.add(GeneratedArtifact(run_id=run.id, kind=request['task'], data=artifact))
                session.commit()
            results.append(status)
        with Session() as session:
            job = session.get(AnalysisJob, job_id)
            if job and job.status == 'running':
                job.status = 'failed' if all(x == 'failed' for x in results) else ('partial' if any(x != 'completed' for x in results) else 'completed')
                job.stage, job.errors, job.updated_at = 'Analysis finished', errors, now()
                session.commit()
    except Exception as exc:
        with Session() as session:
            job = session.get(AnalysisJob, job_id)
            if job and job.status in ('queued', 'running'):
                has_results = session.scalar(select(ModelRun.id).where(ModelRun.job_id == job_id).limit(1))
                job.status = 'partial' if has_results else 'failed'
                job.stage = 'Worker stopped'
                job.errors = [f'Analysis interrupted ({type(exc).__name__}). Retry with a new job; persisted results remain available.']
                job.updated_at = now()
                session.commit()
