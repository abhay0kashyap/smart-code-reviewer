from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from typing import Any, Dict, Optional

MAX_CODE_CHARS = 100_000
DEFAULT_TIMEOUT_SECONDS = 5


def _parse_error_type_and_message(stderr_text: str) -> tuple[str, str]:
    cleaned = (stderr_text or "").strip()
    if not cleaned:
        return "ExecutionError", "Program exited with an unknown error."

    last_line = cleaned.splitlines()[-1].strip()
    if ":" in last_line:
        error_type, error_message = last_line.split(":", 1)
        return error_type.strip() or "ExecutionError", error_message.strip() or cleaned

    return "ExecutionError", last_line


def _extract_error_line(stderr_text: str) -> Optional[int]:
    if not stderr_text:
        return None

    local_file_matches = re.findall(r'File ".*?main\\.py", line (\d+)', stderr_text)
    if local_file_matches:
        return int(local_file_matches[-1])

    generic_matches = re.findall(r"line\s+(\d+)", stderr_text)
    if generic_matches:
        return int(generic_matches[-1])

    return None


def execute_code(code: str, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> Dict[str, Any]:
    """Execute Python code in a subprocess and return structured execution info."""
    code = "" if code is None else str(code)

    if len(code) > MAX_CODE_CHARS:
        return {
            "success": False,
            "stdout": "",
            "stderr": "",
            "output": "",
            "error_type": "InputTooLargeError",
            "error_message": f"Code is too large. Maximum allowed size is {MAX_CODE_CHARS} characters.",
            "error_line": None,
            "traceback": "",
            "return_code": None,
            "timed_out": False,
        }

    run_env = os.environ.copy()
    run_env["PYTHONIOENCODING"] = "utf-8"
    run_env["PYTHONUNBUFFERED"] = "1"

    try:
        with tempfile.TemporaryDirectory(prefix="smart_code_reviewer_") as tmp_dir:
            script_path = os.path.join(tmp_dir, "main.py")
            with open(script_path, "w", encoding="utf-8", newline="\n") as script_file:
                script_file.write(code)

            result = subprocess.run(
                [sys.executable, "-I", "-B", script_path],
                capture_output=True,
                text=True,
                cwd=tmp_dir,
                env=run_env,
                timeout=timeout_seconds,
            )

            stdout_text = result.stdout or ""
            stderr_text = result.stderr or ""

            if result.returncode == 0:
                return {
                    "success": True,
                    "stdout": stdout_text,
                    "stderr": stderr_text,
                    "output": stdout_text,
                    "error_type": None,
                    "error_message": None,
                    "error_line": None,
                    "traceback": "",
                    "return_code": 0,
                    "timed_out": False,
                }

            error_type, error_message = _parse_error_type_and_message(stderr_text)
            error_line = _extract_error_line(stderr_text)
            return {
                "success": False,
                "stdout": stdout_text,
                "stderr": stderr_text,
                "output": stdout_text,
                "error_type": error_type,
                "error_message": error_message,
                "error_line": error_line,
                "traceback": stderr_text,
                "return_code": result.returncode,
                "timed_out": False,
            }

    except subprocess.TimeoutExpired as timeout_error:
        partial_stdout = (timeout_error.stdout or "") if isinstance(timeout_error.stdout, str) else ""
        partial_stderr = (timeout_error.stderr or "") if isinstance(timeout_error.stderr, str) else ""
        return {
            "success": False,
            "stdout": partial_stdout,
            "stderr": partial_stderr,
            "output": partial_stdout,
            "error_type": "TimeoutError",
            "error_message": f"Execution timed out after {timeout_seconds} seconds.",
            "error_line": None,
            "traceback": partial_stderr,
            "return_code": None,
            "timed_out": True,
        }

    except Exception as exc:  # pragma: no cover - defensive fallback
        return {
            "success": False,
            "stdout": "",
            "stderr": "",
            "output": "",
            "error_type": "ExecutionEngineError",
            "error_message": str(exc),
            "error_line": None,
            "traceback": "",
            "return_code": None,
            "timed_out": False,
        }
