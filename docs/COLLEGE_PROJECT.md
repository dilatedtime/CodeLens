# College project material

## Suggested title and abstract

**CodeLens: Evidence-Grounded Code Review with Static Analysis and Local Coding Models**

CodeLens is a Python code review application that combines deterministic static
analysis with locally hosted coding language models. It accepts code snippets and
small projects, creates immutable source snapshots, and presents findings linked to
source evidence. The system also generates algorithm explanations, documentation,
test suggestions and patch previews. A sequential comparison workflow records
model identity, coverage, latency and response failures. An evaluation harness
supports static-only, model-only and hybrid baselines on a labeled synthetic set.
The project emphasizes traceability, reproducibility and explicit uncertainty rather
than automatic code modification. Accuracy and model-comparison conclusions require
measured, human-adjudicated results and are not assumed by this implementation.

## Report outline

1. **Introduction:** review bottlenecks, learning goals, privacy considerations.
2. **Problem definition:** evidence-backed assistance for small Python projects.
3. **Objectives and scope:** supported tasks, local single-user scope, exclusions.
4. **Related work:** static analyzers, coding models, review assistants. Use primary
   model reports and tool documentation; distinguish product features from research.
5. **Requirements:** input limits, asynchronous processing, provenance, persistence,
   model configuration, failure behavior and user interactions.
6. **Design:** component diagram, ER diagram, job states and API contracts.
7. **Implementation:** AST units, source-line mapping, provider schema, validation,
   queue, deduplication, upload safety and React workspace.
8. **Testing:** unit, API integration, real static tools, mocked provider failures,
   browser workflow and optional real-model integration.
9. **Evaluation:** dataset origin, split, label adjudication, TP/FP/FN definitions,
   identical contexts, exact models/settings, hardware, latency and failures.
10. **Results:** only measured tables and examples; include false positives and misses.
11. **Limitations:** synthetic dataset, model hallucinations, context omission,
    Python-only scope, lack of execution verification and local deployment limits.
12. **Conclusion and future work:** concrete lessons and justified extensions.
13. **Appendices:** setup, sample inputs, prompt versions, schemas and demo script.

## Demonstration script: 7–10 minutes

1. Show the architecture diagram: browser, API, worker, analyzers, model, database.
2. Open the review workspace. Load the example and select Static.
3. Run review. Explain queued/running states and immutable source snapshots.
4. Open the mutable-default finding. Point to line evidence and Ruff rule B006.
5. Open the subprocess finding. Explain that a security diagnostic depends on how
   command input is trusted; a diagnostic is not proof of exploitation.
6. Submit feedback and export a JSON/Markdown report. Reopen it from history.
7. If Ollama is installed, select Hybrid and demonstrate an actual model review.
   Explain the difference between static and model sources. Do not represent
   mocked tests as a live AI demonstration.
8. Generate a beginner explanation, documentation and a suggested patch. Show
   the diff, syntax status and the unchanged original snapshot.
9. In Model Lab, compare installed models. Explain why more findings is not accuracy.
10. Present measured evaluation output and a false-positive/missed-bug example.
    If AI runs have not been executed, identify that as remaining validation.

Offline alternative: complete steps 1–6, show model-unavailable handling, then show
the provider tests and evaluation protocol without claiming live inference.

## Viva questions and concise answers

**What is your contribution beyond calling an LLM?**
The ingestion, immutable snapshots, AST context selection, static integration,
evidence validation, provenance, failure handling, comparison and evaluation workflow.

**Why combine static tools with a model?**
Static tools are reproducible within their rule set. Models may explain context and
identify other issues, but can hallucinate. Combining them preserves both sources;
whether the combination improves accuracy must be measured.

**Why no fine-tuning?**
The project tests system engineering and grounded review. Fine-tuning requires a
larger reliable dataset and compute budget; it is not necessary for the workflow.

**How do you stop hallucinated line numbers?**
Validate the path and line range against the exact snapshot and check quoted evidence.
Unsupported claims remain visibly unverified; semantic correctness still needs review.

**How is complexity determined?**
The model explains it from supplied code and must state assumptions. The system does
not provide a formal complexity proof, especially for external functions.

**What prevents source execution?**
Source is stored as text and parsed as AST. Static tools analyze temporary files.
No imports, eval, subprocess execution of submitted programs or generated tests occur.

**What if a comment tells the model to ignore its instructions?**
The system labels source as untrusted data and grants the model no tools. This limits
impact but does not guarantee generated prose is immune to prompt injection.

**How do you compare models fairly?**
Use the same source, prompt version, selected context, schema and generation settings.
Record exact tags/digests and hardware. Run sequentially and report failures/coverage.

**Define precision and recall.**
Precision is TP/(TP+FP). Recall is TP/(TP+FN). F1 is their harmonic mean. Issue identity
requires human adjudication; matching line ranges alone can overestimate correctness.

**Why PostgreSQL and SQLite?**
PostgreSQL supports the intended separate-worker deployment. SQLite lets the same
domain model run locally with minimal setup. Alembic owns schema changes in both.

**How is history reliable?**
Every run references an immutable submission. Content hashes identify its source;
findings and artifacts refer to that exact snapshot rather than an editable buffer.

**What happens when inference fails?**
The job records the error. Hybrid mode keeps static output as partial results;
AI-only tasks fail visibly. Malformed JSON gets one bounded repair attempt.

**Why does the project not run suggested tests?**
Generated tests and submitted programs are untrusted. Properly isolated execution
with resource and network limits is a separate subsystem, beyond this release.

**Can this be deployed on the internet as-is?**
No. It is a trusted local single-user app. Public deployment needs authentication,
authorization, quotas, stronger isolation, logging policy and operational review.

## Suggested team ownership

- Backend/domain and static analysis.
- Frontend and interaction testing.
- Model integration, prompts and evaluation.
- Deployment, integration tests and report coordination.

Each member should understand the complete request lifecycle before the viva.
