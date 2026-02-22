# Smart Code Reviewer

Smart Code Reviewer is a beginner-friendly Python coding platform built with Flask.
It runs Python code safely, explains errors, and provides full-code autofix suggestions using:

1. Deterministic syntax heuristics (always available)
2. Optional local AI model fallback (Ollama or llama-cpp)

## Features

- Browser code editor
- `Run Code` execution workflow
- Structured error detection:
  - error type
  - error message
  - traceback
  - error line
- Highlighted error line view
- Fixed code preview
- Apply fixed code back into editor
- Optional local AI autofix

## Project Structure

- `app.py`: Flask routes (`/`, `/run`, `/ai_fix`)
- `analyzer/executor.py`: safe subprocess code execution
- `analyzer/error_explainer.py`: beginner-friendly error explanations
- `analyzer/ai_fixer.py`: deterministic fixer + local model orchestration
- `analyzer/llm_fix.py`: optional Ollama/llama-cpp adapters
- `templates/index.html`: UI shell
- `static/css/styles.css`: UI styling
- `static/js/main.js`: frontend workflow

## Requirements

Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run Locally

```bash
python app.py
```

Open:

`http://127.0.0.1:8000`

## Autofix Workflow

1. Write code in editor
2. Click **Run Code**
3. Inspect output/error panels
4. Click **AI Auto Fix**
5. Review **Fixed Code Preview**
6. Click **Apply Fixed Code**
7. Click **Run Code** again

## Optional Ollama Setup (Local, Free)

If you want local AI fallback:

```bash
ollama serve
ollama pull llama3
```

The app will try deterministic fixes first, then optional local AI.
If Ollama is unavailable, the backend still works without crashing.

## Optional llama-cpp Setup

```bash
pip install llama-cpp-python
```

Set model path:

```bash
export LLAMA_CPP_MODEL_PATH=/absolute/path/to/model.gguf
```

## Run Tests

```bash
python -m unittest tests/test_deterministic_fixer.py tests/test_run_endpoint.py
```

Tests verify:

- Deterministic syntax fixes
- `/run` returns structured execution + explanation
- `/ai_fix` returns `autofix` payload
