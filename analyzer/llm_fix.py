from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"


def _extract_json_block(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None

    text = text.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None

    try:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        return None

    return None


def _build_json_prompt(code: str, error: str) -> str:
    return f"""
You are an expert Python debugger.
Fix the Python code and return STRICT JSON only.

Output format (JSON only):
{{
  "fixed_code": "full corrected python code",
  "reason": "short reason",
  "changed_lines": [1, 2]
}}

Rules:
- Return full corrected code
- No markdown
- No explanations outside JSON

CODE:
{code}

ERROR:
{error}
""".strip()


def try_ollama_fix(code: str, error: str, model: str = "llama3") -> Dict[str, Any]:
    prompt = _build_json_prompt(code, error)

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0, "top_p": 1},
            },
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return {"ok": False, "error": str(exc), "fixed_code": code, "reason": "", "changed_lines": []}

    raw_text = str(payload.get("response") or "").strip()
    parsed = _extract_json_block(raw_text)

    if not parsed:
        return {
            "ok": False,
            "error": "Ollama did not return valid JSON.",
            "fixed_code": code,
            "reason": "",
            "changed_lines": [],
        }

    fixed_code = str(parsed.get("fixed_code") or "").strip()
    reason = str(parsed.get("reason") or "").strip()
    changed_lines = parsed.get("changed_lines") or []
    if not isinstance(changed_lines, list):
        changed_lines = []

    if not fixed_code:
        return {
            "ok": False,
            "error": "Ollama JSON missing fixed_code.",
            "fixed_code": code,
            "reason": reason,
            "changed_lines": changed_lines,
        }

    return {
        "ok": True,
        "error": None,
        "fixed_code": fixed_code,
        "reason": reason or "Fixed by local Ollama model.",
        "changed_lines": changed_lines,
    }


def try_llama_cpp_fix(code: str, error: str) -> Dict[str, Any]:
    try:
        from llama_cpp import Llama  # type: ignore
    except Exception:
        return {
            "ok": False,
            "error": "llama_cpp not installed.",
            "fixed_code": code,
            "reason": "",
            "changed_lines": [],
        }

    model_path = os.getenv("LLAMA_CPP_MODEL_PATH", "").strip()
    if not model_path or not os.path.exists(model_path):
        return {
            "ok": False,
            "error": "LLAMA_CPP_MODEL_PATH is missing or invalid.",
            "fixed_code": code,
            "reason": "",
            "changed_lines": [],
        }

    prompt = _build_json_prompt(code, error)

    try:
        llm = Llama(model_path=model_path, n_ctx=4096, verbose=False)
        output = llm.create_completion(
            prompt=prompt,
            max_tokens=1200,
            temperature=0,
            top_p=1,
            stop=["\n\n\n"],
        )
        raw_text = str(output["choices"][0]["text"] or "").strip()
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "fixed_code": code,
            "reason": "",
            "changed_lines": [],
        }

    parsed = _extract_json_block(raw_text)
    if not parsed:
        return {
            "ok": False,
            "error": "llama_cpp returned non-JSON output.",
            "fixed_code": code,
            "reason": "",
            "changed_lines": [],
        }

    fixed_code = str(parsed.get("fixed_code") or "").strip()
    reason = str(parsed.get("reason") or "").strip()
    changed_lines = parsed.get("changed_lines") or []
    if not isinstance(changed_lines, list):
        changed_lines = []

    if not fixed_code:
        return {
            "ok": False,
            "error": "llama_cpp JSON missing fixed_code.",
            "fixed_code": code,
            "reason": reason,
            "changed_lines": changed_lines,
        }

    return {
        "ok": True,
        "error": None,
        "fixed_code": fixed_code,
        "reason": reason or "Fixed by local llama-cpp model.",
        "changed_lines": changed_lines,
    }
