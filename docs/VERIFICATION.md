# Implementation and verification record

Verified on 3 October 2026 with Windows, Python 3.12.4 and Node 24.15.0.
This record separates implemented features from runtime validation and remaining
environment-dependent checks.

## Implemented

- [x] React/TypeScript workspace with locally bundled Monaco and responsive styling.
- [x] Paste, Python upload and bounded ZIP upload; immutable source snapshots.
- [x] Real Ruff/Bandit analysis, AST indexing, evidence/location validation.
- [x] AST-aware context budget with original line ranges and coverage reporting.
- [x] Configurable Ollama provider for the three requested model families.
- [x] Schema validation, one repair attempt, useful offline/missing-model errors.
- [x] Queued jobs, sequential comparisons, history, feedback and exports.
- [x] Explanation, docs, README, docstrings, tests and patch-generation workflows.
- [x] Read-only diff previews with Python syntax checks; no source/test execution.
- [x] SQLite native mode and PostgreSQL/Redis/RQ deployment configuration.
- [x] Alembic migration, dependency lockfiles, environment sample, Windows launcher.
- [x] 32 synthetic labeled examples, evaluation harness and adjudication protocol.
- [x] Architecture/ER diagrams, project report outline, demo and viva material.

## Actual checks

| Check | Result |
|---|---|
| Backend pytest | 31 passed; 1 live-Ollama test skipped |
| Frontend Vitest | 3 passed |
| TypeScript / Vite production build | Passed |
| npm audit | 0 vulnerabilities at verification time |
| Alembic upgrade on SQLite | Passed |
| Alembic schema drift check | No new upgrade operations detected |
| Live API readiness | Database and local queue ready |
| Browser: static review | Three real findings returned from included sample |
| Browser: history | Persisted snapshot reopened successfully |
| Browser: evidence and feedback | Evidence displayed; feedback saved |
| Static evaluation, development split | 24/24 completed; raw results saved |
| Model availability | Ollama unavailable; explicit offline state verified |

Backend coverage includes hostile archives, Windows-reserved paths, case collisions,
size/binary rejection, AST ranges, evidence checks, provenance-preserving merging,
real analyzers, no execution of submitted source, API workflow, feedback, deletion,
partial/failed inference, patch immutability, sequential comparison, stale jobs,
queue errors, schema repair and evaluation matching.

One dependency deprecation warning is emitted by Starlette's TestClient for httpx.
Tests pass; it is recorded rather than hidden. The production build emits a large
chunk warning because Monaco is bundled locally. Only Python language support is
included to reduce the download; the editor remains a sizeable browser dependency.

## Static evaluation evidence

See `evaluation/results-static-development.json`. The executed development split
contains 12 positive and 12 clean-control examples. Automatic candidate matching
returned TP=4, FP=5, FN=8 (precision 0.444, recall 0.333, F1 0.381), with zero findings
on the 12 clean controls. These are **provisional location/category scores**, not
human-validated bug detection accuracy. Category mismatches and additional valid
diagnoses require adjudication. Holdout examples were not used for tuning or scored.

The harness's `latency_seconds` measures full request-to-completion wall time.
The saved baseline was rerun after the timer correction. Per-run metrics include
static analysis time and report separate static/model timing fields. Static analysis
is shared across models in a comparison, so adding per-model times double-counts
the shared stage. The final browser sample review completed in 1.426 seconds on
this machine; this single observation is not a performance guarantee.

## Environment-dependent checks remaining

- [ ] Real Ollama inference and model quality: no Ollama installation/model was
  available. Run the opt-in test and evaluation after installing a chosen model.
- [ ] Docker/PostgreSQL/Redis/RQ runtime: Docker was not available on this machine.
  The supplied Compose configuration has not been validated by an actual launch.
- [ ] AI explanation/documentation/patch quality with real weights: contracts and
  failure paths are tested; generated semantic content still needs model validation.
- [ ] Full three-model benchmark and human label adjudication.

Mocked provider outputs appear only in automated tests, never as product results.
No model accuracy figures, GPU performance claims or live AI screenshots are invented.
