from __future__ import annotations

import re

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"


def _clean_fixed_code(text: str) -> str:
    cleaned = (text or "").strip()
    fenced = re.findall(r"```(?:python)?\s*(.*?)```", cleaned, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        cleaned = max(fenced, key=len).strip()
    cleaned = re.sub(r"^python\s*", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned


def ai_fix_code(code, error):
    prompt = f"""You are an expert Python developer.
Fix the following Python code completely.

Return ONLY the corrected full code.

Code:
{code}

Error:
{error}"""

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": "deepseek-coder",
            "prompt": prompt,
            "stream": False,
        },
        timeout=90,
    )
    response.raise_for_status()

    payload = response.json()
    return _clean_fixed_code(str(payload.get("response") or ""))
