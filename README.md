# CodeLens

An intelligent Python code review assistant for a college project. CodeLens combines
Ruff and Bandit with a configurable local Ollama coding model, and presents evidence,
explanations, documentation, suggested tests and proposed changes in a React workspace.

**No submitted code is executed.** Static findings are actual analyzer output. AI
features require an installed model; the app never substitutes demo responses.

## Quick start on Windows

Requirements: Python 3.12 and Node.js 22.12+ (Node 24 also works). From this folder:

```powershell
./start.ps1
```

The script creates a project-local Python environment, installs locked dependencies,
migrates SQLite, builds the frontend and starts both services. Open
http://127.0.0.1:4173. Press Enter in the launching terminal to stop its processes.
Do not start this script while another CodeLens instance uses ports 8000 or 4173.

Choose **Static**, then **Run review** for a complete working flow without Ollama.
The included sample deliberately contains mutable-default and subprocess issues.

## Development setup

Terminal 1, from the project root:

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.lock.txt
cd backend
Copy-Item .env.example .env
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Terminal 2, from the project root:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173. API documentation: http://127.0.0.1:8000/docs.
On macOS/Linux use `backend/.venv/bin/python` in place of the Windows executable.
Use Python 3.12 for the supplied lockfile. `requirements.txt` contains direct version
ranges; `requirements.lock.txt` and `package-lock.json` record tested resolutions.

## Enable AI

Install [Ollama](https://ollama.com/download) separately. Start its service and pull
one model that fits your hardware:

```powershell
ollama pull qwen2.5-coder:1.5b
ollama list
```

The other default tags are `deepseek-coder:1.3b` and `codellama:7b`. Install only what
you intend to use. Change `ALLOWED_MODELS` and `DEFAULT_MODEL` in `backend/.env` to
use different exact tags, then restart the API. Tags must match the installed names.
Model licenses and hardware requirements vary; model weights are not bundled.

In Settings, refresh the model status. Select Hybrid or AI only, then run a review.
Explain, Docs, Tests and Changes use the currently selected AI model regardless of
the review-mode toggle. Model Lab runs selected models sequentially in hybrid mode.

Models are called through `/api/chat` with a JSON schema. Invalid responses receive
one repair attempt. Missing models, server failures and timeouts are visible errors.
Hybrid mode keeps successful static analysis when the model fails. An evidence match
only verifies that quoted code exists; it does not prove that the diagnosis is true.

## Docker: PostgreSQL + Redis + RQ

Install Docker Desktop with Linux containers, then:

```powershell
docker compose up --build
```

Open http://127.0.0.1:8080. The Compose deployment includes PostgreSQL, Redis, an API,
one RQ worker, and nginx serving the built React app. Data persists in named volumes.
`docker compose down` stops services without deleting those volumes.

The worker contacts host Ollama at `http://host.docker.internal:11434`. On Docker
Desktop, verify this route reaches your Ollama service. Ollama bound exclusively to
host loopback may not be reachable from containers. The native setup avoids this
issue; alternatively, use a properly restricted host bind or an Ollama container on
the same private Docker network. Do not expose the unauthenticated Ollama API publicly.

The Compose configuration is supplied but was not run on the development machine
because Docker was unavailable. Native SQLite/local-worker mode is the verified path.

## Using CodeLens

1. Create a project, or let the first submission create one.
2. Paste Python, upload a `.py` file, or upload a ZIP of up to 30 Python files.
3. Select Static, AI only, or Hybrid. Run review.
4. Inspect findings by category/severity. Click one to navigate to its source lines.
5. Read evidence, source attribution and verification status. Mark feedback.
6. Generate explanations, Markdown documentation, README drafts, docstrings,
   suggested tests, or proposed changes. Changes appear in a read-only diff.
7. Export the persisted result as Markdown or JSON. History reopens the exact source
   snapshot and model run used for that result.

Uploads accept UTF-8 Python only. ZIP metadata, paths, expanded size and symlinks are
checked; dependency folders and non-Python files are skipped and reported. Snapshots
are immutable; "Edit a copy" creates a fresh single-file submission. The current
file selector handles project navigation. Source content is stored in the database,
not in a publicly served directory. Temporary analyzer files are deleted after use.

## Tests

From `backend` using the project environment:

```powershell
.venv/Scripts/python.exe -m pytest -q
```

From `frontend`:

```powershell
npm test
npm run build
npm audit
```

Tests invoke real Ruff/Bandit but mock model responses. To opt into live inference:

```powershell
# From backend, after installing the model:
$env:CODELENS_REAL_MODEL = 'qwen2.5-coder:1.5b'
.venv/Scripts/python.exe -m pytest tests/test_provider.py -q
Remove-Item Env:CODELENS_REAL_MODEL
```

No live AI accuracy claim is made until that path and the model evaluation are run.
See [verification](docs/VERIFICATION.md) for the actual verification record.

## Repository

```text
codelens/
  backend/
    app/                  API, schemas, storage, analysis, context, jobs, provider
    migrations/           Alembic database migration
    tests/                Integration and domain tests
    requirements*.txt     Direct dependencies and lockfile
  frontend/
    src/                  React workspace, components, types and tests
    public/               Local favicon
  evaluation/             32 labeled examples, harness and scoring protocol
  samples/                Deliberately buggy demonstration source
  docs/                   Architecture, report outline, demo, viva, verification
  compose.yaml            PostgreSQL/Redis/RQ deployment
  start.ps1               Native Windows startup
```

## Scope and limitations

- Local single-user project. No authentication or tenant isolation. Keep services
  bound to loopback; public deployment needs additional access and resource controls.
- Python only. No code execution, automatic patch application, fine-tuning, PR
  posting, vector database, or autonomous shell access.
- AST context selection prioritizes complete top-level units and imports. It is not
  a full cross-file call graph. A character budget estimates context conservatively;
  line coverage and omitted units are shown. Token counts are not invented.
- Native mode uses one in-process worker. Run one API process, without reload or
  multiple workers. Interrupted jobs are marked failed on restart. RQ mode uses one
  separate worker. New jobs are explicit retries; schema repair is bounded.
- Long-running jobs become stale after the configured deadline, so the UI stops
  polling forever. There is no cancellation UI or distributed multiworker guarantee.
- Model responses may be wrong. Generated tests are not run. Syntax-valid proposed
  code can still change behavior. Deduplication is deliberately conservative.
- Source, responses, findings and feedback persist until project deletion. Deletion
  cascades across associated database rows and is blocked while a review is active.
  Database backups and previously exported reports are outside app deletion.
- Model benchmarks use a small synthetic dataset and require human adjudication.
  Do not present provisional location matching as established semantic accuracy.

## Project material

- [Architecture and ER diagram](docs/ARCHITECTURE.md)
- [College report, demo script and viva](docs/COLLEGE_PROJECT.md)
- [Evaluation protocol](evaluation/README.md)
- [Implementation and verification checklist](docs/VERIFICATION.md)

## Official integration references

- [Ollama chat API](https://docs.ollama.com/api/chat)
- [RQ workers](https://python-rq.org/docs/workers/)
- [Ruff configuration](https://docs.astral.sh/ruff/configuration/)

This is an engineering implementation and evaluation framework, not a trained new
model or a claim of research-level code-review accuracy.
