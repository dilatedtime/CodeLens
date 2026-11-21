# Evaluation protocol

The 32 author-owned synthetic fixtures form 16 buggy/clean pairs. Development has
24 cases; holdout has 8. Pairs remain in the same split. Do not tune prompts on the
holdout. All source is treated as data and is never executed by this harness.

From the project root with backend dependencies installed and API/worker running:

```powershell
python evaluation/build_dataset.py
python evaluation/evaluate.py --modes static --split development
python evaluation/evaluate.py --modes static ai hybrid --model qwen2.5-coder:1.5b --split holdout --output evaluation/results-qwen.json
```

Repeat for the exact installed DeepSeek Coder and Code Llama tags. Runs are
sequential. Record RAM, GPU/VRAM, quantization and runtime version manually in the
report. The response captures model digest, settings, load duration and inference
counts where the provider supplies them. Ollama unloads models after each request;
do not label this as a warm-cache benchmark. Perform controlled warm/cold trials
separately before making performance claims.

## Matching and adjudication

Automatic scores are **provisional**: one-to-one matching by path, category and
overlapping lines. An extra duplicate prediction counts as a false positive.
The dataset includes an `issue_type` and rationale for a human to verify that the
predicted diagnosis is actually the same issue. For publication, two reviewers
should independently mark each predicted finding TP/FP/unclear and resolve
disagreements. Also inspect unexpected valid findings and revise labels before
freezing the final dataset. "Clean" means a negative control for the target
issue, not proven absence of all style or security concerns.

Failed and partial jobs remain in the output but are excluded from precision,
recall and F1, with exclusion counts shown explicitly. Report coverage and failures
alongside scores; never compare models using only their finding counts. A static
tool's category can differ from the semantic issue label (for example complexity
suggestions categorized as style); adjudicate such cases consistently.

## Human quality rubric

Score each generated explanation/documentation artifact from 1 to 5 on:

- Correctness relative to source behavior.
- Grounding in actual signatures and evidence.
- Completeness of assumptions, edge cases and complexity limits.
- Clarity for the selected audience.
- Usefulness of verification suggestions.

Keep expected labels out of prompts. Record exact prompt version, model digest and
settings with every report. This small synthetic set demonstrates the evaluation
method; it does not establish general code-review accuracy. Extend with real,
licensed bug-fix examples before broader claims.
