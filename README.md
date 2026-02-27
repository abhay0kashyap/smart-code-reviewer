# Smart Code Reviewer

Smart Code Reviewer is a Flask-based AI Tutor IDE for beginners. It safely runs Python code, captures structured errors, explains failures, and generates full fixed code.

## Core Features

- Safe Python execution with timeout
- Structured error capture (`type`, `message`, `line`, `traceback`)
- Beginner-friendly explanations
- AI Auto Fix with deterministic fallback
- AI Tutor suggestions and generated code
- Fixed code preview + apply + re-run flow
- Rate-limited AI endpoints and centralized logging

## How AI Tutor Works

1. User clicks **Run Code**.
2. Backend executes code with `analyzer/executor.py`.
3. If failed, backend returns structured error and explanation.
4. User clicks **AI Auto Fix**.
5. Backend sends `code + error_type + error_message + error_line + traceback` to AI service.
6. AI service enforces structured response and extracts `fixed_code`.
7. Frontend shows fixed code preview.
8. User clicks **Apply Fix** and code is re-run automatically.
9. If still failing, refinement retries run up to 2 times.

## Error Handling Flow

- All API routes return JSON.
- Execution failures are normalized into:
  - `success`
  - `output`
  - `error`
  - `execution`
  - `explanation`
- AI failures never crash the backend.
- When model/API is unavailable, deterministic fixes are still attempted.

## Architecture (Text Diagram)

```text
Browser (templates + static/js/main.js)
        |
        v
Flask App (backend/app_factory.py)
        |
        +--> services/execution_service.py
        |         |
        |         v
        |   analyzer/executor.py + analyzer/error_explainer.py
        |
        +--> services/ai_service.py
                  |
                  v
            analyzer/ai_fixer.py
                  |
                  +--> OpenAI (if configured)
                  +--> deterministic fallback rules

Shared utilities:
- utils/logging_config.py
- utils/rate_limiter.py
```

## Project Structure

- `app.py`: app entrypoint
- `backend/app_factory.py`: route wiring + error handling + rate limiting
- `services/`: execution and AI orchestration
- `utils/`: logging and rate limiting
- `analyzer/`: executor, explainer, AI fixer, rule logic
- `templates/`: HTML UI
- `static/css/styles.css`: modern IDE styling
- `static/js/main.js`: frontend workflow
- `logs/`: runtime log files

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run Locally

```bash
python app.py
```

Open `http://127.0.0.1:8000`

## Optional AI Configuration

Set OpenAI key:

```bash
export OPENAI_API_KEY="your_key"
```

Optional local model fallback:

```bash
ollama serve
ollama pull llama3
```

## Run Tests

```bash
.venv/bin/python -m unittest tests/test_deterministic_fixer.py tests/test_run_endpoint.py
```
