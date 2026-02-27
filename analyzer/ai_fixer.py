from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore

LOGGER = logging.getLogger(__name__)
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_FIX_MODEL = os.getenv("OPENAI_FIX_MODEL", "gpt-4.1-mini")


def clean_code(text: str) -> str:
    cleaned = (text or "").strip()
    fenced = re.findall(r"```(?:python)?\s*(.*?)```", cleaned, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        cleaned = max(fenced, key=len).strip()
    return cleaned.strip()


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    raw = (text or "").strip()
    if not raw:
        return None

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.IGNORECASE | re.DOTALL)
    for block in fenced:
        try:
            parsed = json.loads(block)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue

    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        return None

    try:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        return None

    return None


def _extract_error_line_from_text(error_text: str) -> Optional[int]:
    if not error_text:
        return None

    local_file_matches = re.findall(r'File ".*?main\\.py", line (\d+)', error_text)
    if local_file_matches:
        return int(local_file_matches[-1])

    generic_matches = re.findall(r"line\s+(\d+)", error_text)
    if generic_matches:
        return int(generic_matches[-1])

    return None


def _syntax_error_details(code: str) -> Optional[Dict[str, Any]]:
    try:
        compile(code, "<user_code>", "exec")
        return None
    except SyntaxError as exc:
        return {
            "lineno": int(exc.lineno or 0),
            "offset": int(exc.offset or 0),
            "msg": str(exc.msg or ""),
            "text": str(exc.text or ""),
        }
    except Exception:
        return None


def _is_syntax_valid(code: str) -> bool:
    return _syntax_error_details(code) is None


def _line_index(code: str, one_based_line: Optional[int]) -> int:
    lines = code.splitlines()
    if not lines:
        return -1
    if one_based_line and 1 <= one_based_line <= len(lines):
        return one_based_line - 1
    return 0


def _leading_spaces(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _find_prev_code_line(lines: List[str], idx: int) -> Optional[int]:
    i = idx - 1
    while i >= 0:
        if lines[i].strip():
            return i
        i -= 1
    return None


def _reindent_line(line: str, indent: int) -> str:
    return (" " * max(indent, 0)) + line.lstrip()


def _extract_name_error_identifier(error_blob: str) -> str:
    match = re.search(r"name\s+'([A-Za-z_][A-Za-z0-9_]*)'\s+is\s+not\s+defined", error_blob)
    return match.group(1) if match else ""


def _extract_key_error_key(error_blob: str) -> str:
    match = re.search(r"KeyError:\s*['\"]?([^'\"\n]+)['\"]?", error_blob)
    return match.group(1) if match else ""


def _infer_error_type(error_message: str, traceback_text: str) -> str:
    msg = str(error_message or "").strip()
    if msg and ":" in msg:
        return msg.split(":", 1)[0].strip() or "Error"

    tb = str(traceback_text or "").strip()
    if tb:
        lines = [line.strip() for line in tb.splitlines() if line.strip()]
        if lines:
            last = lines[-1]
            if ":" in last:
                return last.split(":", 1)[0].strip() or "Error"
    return "Error"


def _build_strict_fix_prompt(code: str, error_type: str, error_message: str, traceback_text: str) -> str:
    return f"""
You are an expert Python debugging assistant.

Your task is to fix Python code that contains errors.

You MUST:
1. Fix syntax errors
2. Fix indentation errors
3. Fix NameError, TypeError, IndexError, etc.
4. Correct missing commas, brackets, colons
5. Correct improper indentation
6. Ensure the final code runs without errors

IMPORTANT RULES:
- Return ONLY corrected Python code
- Do NOT include explanation
- Do NOT include markdown
- Do NOT include ```python
- Do NOT include comments unless necessary
- Do NOT repeat the original broken code
- Output clean, runnable Python code only

Original Code:
{code}

Error Type:
{error_type}

Error Message:
{error_message}

Traceback:
{traceback_text}

Now return the fully corrected working Python code.
""".strip()


def _build_structured_tutor_prompt(
    code: str,
    error_type: str,
    error_message: str,
    error_line: Optional[int],
    traceback_text: str,
) -> str:
    return f"""
You are a Python debugging assistant.

Analyze and fix the user code.
Return STRICT JSON only in this format:
{{
  "explanation": "short beginner-friendly explanation",
  "fixed_code": "full corrected python code",
  "improvements": "short improvement suggestions"
}}

Rules:
- JSON only
- No markdown
- No extra keys
- fixed_code must be full runnable Python code

Original Code:
{code}

Error Type:
{error_type}

Error Message:
{error_message}

Error Line:
{error_line}

Traceback:
{traceback_text}
""".strip()


def _validate_tutor_payload(parsed: Dict[str, Any]) -> Optional[Dict[str, str]]:
    explanation = str(parsed.get("explanation") or "").strip()
    fixed_code = clean_code(str(parsed.get("fixed_code") or ""))
    improvements = str(parsed.get("improvements") or "").strip()

    if not fixed_code:
        return None

    return {
        "explanation": explanation or "I fixed the code based on the error context.",
        "fixed_code": fixed_code,
        "improvements": improvements or "Re-run after each small change and handle the first traceback error first.",
    }


def _safe_suggestions(items: Any) -> List[str]:
    if not isinstance(items, list):
        return []

    cleaned: List[str] = []
    for item in items:
        text = str(item or "").strip()
        if text:
            cleaned.append(text)
        if len(cleaned) >= 8:
            break
    return cleaned


def _first_complete_call_end(line: str) -> int:
    in_single = False
    in_double = False
    escape = False
    depth = 0
    saw_open = False

    for i, ch in enumerate(line):
        if escape:
            escape = False
            continue

        if ch == "\\":
            escape = True
            continue

        if ch == "'" and not in_double:
            in_single = not in_single
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            continue

        if in_single or in_double:
            continue

        if ch == "(":
            depth += 1
            saw_open = True
            continue
        if ch == ")" and depth > 0:
            depth -= 1
            if saw_open and depth == 0:
                return i

    return -1


def _trim_garbage_suffix(line: str) -> str:
    stripped = line.rstrip()
    if not stripped:
        return line

    # Common malformed endings from accidental key mash:
    # print("x")abc';] -> print("x")
    tail_pattern = r"^(.+[\)\]\}\"'])\s*[A-Za-z0-9_`~!@#$%^&*=+|\\;:'\",<>/?\-\[\]\{\}]+$"
    match = re.match(tail_pattern, stripped)
    if match:
        candidate = match.group(1).rstrip()
        if candidate:
            return candidate

    # If there's a full function-call close paren and non-comment suffix that does not
    # look like valid continuation, drop the suffix.
    close_pos = _first_complete_call_end(stripped)
    if close_pos != -1 and close_pos < len(stripped) - 1:
        suffix = stripped[close_pos + 1 :].strip()
        if suffix and not suffix.startswith("#"):
            valid_prefixes = (
                ".",
                ",",
                ":",
                "if ",
                "for ",
                "while ",
                "and ",
                "or ",
                "else",
            )
            if not any(suffix.startswith(prefix) for prefix in valid_prefixes):
                return stripped[: close_pos + 1].rstrip()

    return line


def _repair_syntax_line(lines: List[str], line_idx: int, error_offset: int) -> Optional[str]:
    if line_idx < 0 or line_idx >= len(lines):
        return None

    original = lines[line_idx]
    candidates: List[str] = []

    # 0) Common beginner syntax: missing comma between function-call arguments.
    # Example: print('Hello' name) -> print('Hello', name)
    if "(" in original and ")" in original:
        comma_after_string = re.sub(
            r"(['\"][^'\"]*['\"])\s+([A-Za-z_][A-Za-z0-9_]*|\d+|\(|\[|\{)",
            r"\1, \2",
            original,
        )
        if comma_after_string != original:
            candidates.append(comma_after_string)

        comma_before_string = re.sub(
            r"([A-Za-z_][A-Za-z0-9_]*|\d+|\)|\]|\})\s+(['\"])",
            r"\1, \2",
            original,
        )
        if comma_before_string != original:
            candidates.append(comma_before_string)

    # 1) Remove obvious noisy suffix after a valid expression terminator.
    trimmed_suffix = _trim_garbage_suffix(original)
    if trimmed_suffix != original:
        candidates.append(trimmed_suffix)

    # 2) Cut line at syntax error offset when parser points to junk token.
    if error_offset and 1 <= error_offset <= len(original):
        cut = original[: error_offset - 1].rstrip()
        if cut and cut != original:
            candidates.append(cut)

    # 3) If line has odd quotes, close them.
    for quote in ("'", '"'):
        if original.count(quote) % 2 == 1:
            candidates.append(f"{original}{quote}")
            stripped = original.rstrip()
            if "(" in stripped and not stripped.endswith(")"):
                candidates.append(f"{stripped}{quote})")

    # 4) Remove unmatched trailing closers.
    unmatched = re.sub(r"[\)\]\}]+$", "", original).rstrip()
    if unmatched and unmatched != original:
        candidates.append(unmatched)

    # Validate each candidate against full code syntax.
    for candidate in candidates:
        candidate_lines = lines.copy()
        candidate_lines[line_idx] = candidate
        merged = "\n".join(candidate_lines)
        if _is_syntax_valid(merged):
            return candidate

    return None


def _repair_indentation(lines: List[str], line_idx: int, error_blob_lower: str) -> Optional[List[str]]:
    candidates: List[List[str]] = []

    # Normalize tabs globally first.
    tabs_fixed = [line.replace("\t", "    ") for line in lines]
    if tabs_fixed != lines:
        candidates.append(tabs_fixed)

    if 0 <= line_idx < len(lines):
        # Unexpected indent: strip current line indentation.
        if "unexpected indent" in error_blob_lower:
            c = lines.copy()
            c[line_idx] = c[line_idx].lstrip()

            # If this line opens a block, ensure following code line is 4-space indented.
            if c[line_idx].rstrip().endswith(":"):
                c2 = c.copy()
                next_idx = line_idx + 1
                while next_idx < len(c2) and not c2[next_idx].strip():
                    next_idx += 1
                if next_idx < len(c2):
                    c2[next_idx] = _reindent_line(c2[next_idx], 4)
                    candidates.append(c2)

            candidates.append(c)

        prev_idx = _find_prev_code_line(lines, line_idx)
        if prev_idx is not None:
            prev_line = lines[prev_idx]
            prev_indent = _leading_spaces(prev_line)

            # If previous line opens a block, current line should be indented.
            if prev_line.rstrip().endswith(":"):
                c = lines.copy()
                c[line_idx] = _reindent_line(c[line_idx], prev_indent + 4)
                candidates.append(c)

            # Otherwise, align with previous line indentation.
            c = lines.copy()
            c[line_idx] = _reindent_line(c[line_idx], prev_indent)
            candidates.append(c)

        # If current line opens a block, ensure the next code line is indented.
        if lines[line_idx].rstrip().endswith(":"):
            next_idx = line_idx + 1
            while next_idx < len(lines) and not lines[next_idx].strip():
                next_idx += 1
            if next_idx < len(lines):
                c = lines.copy()
                current_indent = _leading_spaces(lines[line_idx])
                c[next_idx] = _reindent_line(c[next_idx], current_indent + 4)
                candidates.append(c)
            else:
                # Empty block: insert pass so code becomes runnable.
                c = lines.copy()
                current_indent = _leading_spaces(lines[line_idx])
                c.append((" " * (current_indent + 4)) + "pass")
                candidates.append(c)

        # Local brute-force indentation search for stubborn errors.
        prev_idx = _find_prev_code_line(lines, line_idx)
        prev_indent = _leading_spaces(lines[prev_idx]) if prev_idx is not None else 0
        indent_options = sorted(
            {
                0,
                4,
                8,
                12,
                max(prev_indent, 0),
                max(prev_indent - 4, 0),
                prev_indent + 4,
            }
        )
        next_idx = line_idx + 1
        while next_idx < len(lines) and not lines[next_idx].strip():
            next_idx += 1

        for indent in indent_options:
            c = lines.copy()
            c[line_idx] = _reindent_line(c[line_idx], indent)
            candidates.append(c)

            if next_idx < len(lines):
                for next_indent in indent_options:
                    c2 = c.copy()
                    c2[next_idx] = _reindent_line(c2[next_idx], next_indent)
                    candidates.append(c2)

    # Global cleanup for odd non-4-space indents.
    normalized = lines.copy()
    changed = False
    for i, line in enumerate(normalized):
        if not line.strip():
            continue
        indent = _leading_spaces(line)
        if indent % 4 != 0:
            normalized[i] = _reindent_line(line, max(0, indent - (indent % 4)))
            changed = True
    if changed:
        candidates.append(normalized)

    for candidate in candidates:
        merged = "\n".join(candidate)
        if _is_syntax_valid(merged):
            return candidate

    return None


def _iterative_indentation_repair(lines: List[str], max_rounds: int = 6) -> Optional[List[str]]:
    current = lines.copy()
    changed = False

    for _ in range(max_rounds):
        merged = "\n".join(current)
        issue = _syntax_error_details(merged)
        if not issue:
            return current if changed else None

        msg = str(issue.get("msg") or "").lower()
        if "indent" not in msg and "tab" not in msg:
            return current if changed and _is_syntax_valid(merged) else None

        idx = _line_index(merged, int(issue.get("lineno") or 0))
        repaired = _repair_indentation(current, idx, msg)
        if not repaired or repaired == current:
            return current if changed and _is_syntax_valid("\n".join(current)) else None

        current = repaired
        changed = True

    if _is_syntax_valid("\n".join(current)):
        return current if changed else None
    return None


def _openai_available() -> bool:
    return OpenAI is not None and bool(os.getenv("OPENAI_API_KEY"))


def _openai_chat(messages: List[Dict[str, str]], temperature: float = 0.0) -> str:
    if OpenAI is None:
        raise RuntimeError("openai package is not installed")

    client = OpenAI()
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=temperature,
    )
    if not response.choices:
        return ""
    return str(response.choices[0].message.content or "")


def ai_fix_with_openai(original_code: str, error_message: str, traceback_text: str) -> str:
    """Primary OpenAI fixer for /ai-fix endpoint using requested prompt/model."""
    result = ai_tutor_structured_response(
        code=original_code,
        error_type=_infer_error_type(error_message, traceback_text),
        error_message=error_message,
        error_line=_extract_error_line_from_text(traceback_text),
        traceback_text=traceback_text,
    )
    return str(result.get("fixed_code") or "")


def ai_tutor_structured_response(
    code: str,
    error_type: str,
    error_message: str,
    error_line: Optional[int],
    traceback_text: str,
) -> Dict[str, str]:
    prompt = _build_structured_tutor_prompt(code, error_type, error_message, error_line, traceback_text)
    LOGGER.info(
        "AI tutor request: type=%s line=%s code_chars=%d traceback_chars=%d",
        error_type,
        error_line,
        len(code),
        len(traceback_text),
    )

    if OpenAI is None or not os.getenv("OPENAI_API_KEY"):
        LOGGER.warning("OpenAI unavailable or OPENAI_API_KEY missing for structured tutor response.")
        return {
            "explanation": "AI service is unavailable. Falling back to local fixer.",
            "fixed_code": "",
            "improvements": "Set OPENAI_API_KEY and retry for full AI tutor output.",
        }

    client = OpenAI()
    raw_text = ""

    try:
        response = client.responses.create(model=OPENAI_FIX_MODEL, input=prompt)
        raw_text = str(getattr(response, "output_text", "") or "")
    except Exception as exc:  # pragma: no cover
        LOGGER.exception("OpenAI responses API tutor error: %s", exc)

    if not raw_text.strip():
        try:
            response = client.chat.completions.create(
                model=OPENAI_FIX_MODEL,
                messages=[
                    {"role": "system", "content": "Return strict JSON only."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
            )
            raw_text = (response.choices[0].message.content or "") if response.choices else ""
        except Exception as exc:  # pragma: no cover
            LOGGER.exception("OpenAI chat fallback tutor error: %s", exc)

    LOGGER.info("AI raw response: %s", (raw_text[:1200] + "...") if len(raw_text) > 1200 else raw_text)
    parsed = _extract_json_object(raw_text)
    if parsed:
        validated = _validate_tutor_payload(parsed)
        if validated:
            LOGGER.info("AI parsed response: %s", validated)
            return validated

    LOGGER.warning("AI output invalid JSON payload; using deterministic fallback.")
    execution_context = {
        "error_type": error_type,
        "error_message": error_message,
        "traceback": traceback_text,
        "error_line": error_line,
    }
    fallback = deterministic_fix(code, execution_context)
    fallback_code = str(fallback.get("fixed_code") or "") if fallback.get("fix_available") else ""
    return {
        "explanation": "AI response was invalid. Applied local deterministic fallback.",
        "fixed_code": fallback_code,
        "improvements": "Fix the first traceback issue, then re-run and repeat.",
    }


def deterministic_fix(code: str, execution: Dict[str, Any]) -> Dict[str, Any]:
    result = {
        "fix_available": False,
        "fixed_code": code,
        "correct_line": "",
        "reason": "No deterministic fix available.",
    }

    if not code or not str(code).strip():
        return result

    lines = str(code).splitlines()
    if not lines:
        return result

    error_type = str(execution.get("error_type") or "")
    error_message = str(execution.get("error_message") or "")
    traceback_text = str(execution.get("traceback") or "")
    error_blob = f"{error_type}\n{error_message}\n{traceback_text}"
    error_blob_lower = error_blob.lower()

    changed = False
    reason = ""

    block_pattern = r"^(\s*(?:if|elif|else|for|while|try|except|finally|with|def|class)\b.*?);(\s*)$"
    for idx, line in enumerate(lines):
        updated = line
        updated = re.sub(r"print\(([^\n)]*?),/\)", r"print(\1)", updated)
        updated = re.sub(r"/\)", ")", updated)
        updated = re.sub(block_pattern, r"\1:\2", updated)
        if updated != line:
            lines[idx] = updated
            changed = True
            if not reason:
                reason = "Applied punctuation and block-syntax corrections."

    error_line = execution.get("error_line")
    if not isinstance(error_line, int):
        error_line = _extract_error_line_from_text(error_blob)
    line_idx = _line_index(code, error_line)

    if line_idx >= 0:
        target = lines[line_idx]
        updated = target

        if "unterminated string" in error_blob_lower or "eol while scanning string literal" in error_blob_lower:
            for quote in ("'", '"'):
                if updated.count(quote) % 2 == 1:
                    trimmed = updated.rstrip()
                    if trimmed.endswith(")"):
                        closing_index = updated.rfind(")")
                        if closing_index >= 0:
                            updated = f"{updated[:closing_index]}{quote}{updated[closing_index:]}"
                        else:
                            updated = f"{updated}{quote}"
                    else:
                        updated = f"{updated}{quote}"
                    # Common beginner case: print('Hello  -> print('Hello')
                    if "(" in updated and not updated.rstrip().endswith(")"):
                        updated = f"{updated})"
                    reason = "Closed unterminated string literal."
                    break

        missing_name = _extract_name_error_identifier(error_blob)
        if missing_name and "nameerror" in error_blob_lower and "print(" in updated:
            safe_word = re.escape(missing_name)
            candidate = re.sub(
                rf"(?<!['\"\.])\b{safe_word}\b(?!['\"])",
                f'"{missing_name}"',
                updated,
            )
            if candidate != updated:
                updated = candidate
                reason = "Converted undefined print token to a string literal."

        if "indexerror" in error_blob_lower:
            index_match = re.search(r"\b([A-Za-z_][A-Za-z0-9_]*)\[(\d+)\]", updated)
            if index_match:
                var_name = index_match.group(1)
                index_value = int(index_match.group(2))
                safe_expr = f"({var_name}[{index_value}] if len({var_name}) > {index_value} else None)"
                updated = re.sub(
                    rf"\b{re.escape(var_name)}\[{index_value}\]",
                    safe_expr,
                    updated,
                    count=1,
                )
                reason = "Guarded list indexing to avoid out-of-range access."

        if "keyerror" in error_blob_lower:
            missing_key = _extract_key_error_key(error_blob)
            if missing_key:
                key_access = rf"\[\s*(['\"])%s\1\s*\]" % re.escape(missing_key)
                if re.search(key_access, updated):
                    updated = re.sub(key_access, f'.get("{missing_key}")', updated)
                    reason = "Replaced dictionary key access with .get() for missing keys."

        if "attributeerror" in error_blob_lower and ".add(" in updated:
            updated = updated.replace(".add(", ".append(")
            reason = "Replaced list .add() with .append()."

        if updated != target:
            lines[line_idx] = updated
            changed = True

    # Syntax-aware fallback for random/changed malformed lines.
    if any(
        token in error_blob_lower
        for token in ("indentationerror", "unexpected indent", "expected an indented block", "unindent")
    ):
        indent_fixed_lines = _iterative_indentation_repair(lines)
        if indent_fixed_lines is not None and indent_fixed_lines != lines:
            lines = indent_fixed_lines
            changed = True
            reason = "Repaired indentation to match Python block structure."

    # Syntax-aware fallback for random/changed malformed lines.
    syntax_issue = _syntax_error_details("\n".join(lines))
    if syntax_issue:
        syntax_lineno = int(syntax_issue.get("lineno") or 0)
        syntax_offset = int(syntax_issue.get("offset") or 0)
        syntax_idx = _line_index("\n".join(lines), syntax_lineno)
        repaired_line = _repair_syntax_line(lines, syntax_idx, syntax_offset)
        if repaired_line is not None and repaired_line != lines[syntax_idx]:
            lines[syntax_idx] = repaired_line
            changed = True
            reason = "Removed malformed trailing syntax and repaired the failing line."

    if not changed:
        return result

    fixed_code = "\n".join(lines).replace("\t", "    ")
    return {
        "fix_available": True,
        "fixed_code": fixed_code,
        "correct_line": lines[line_idx] if line_idx >= 0 else "",
        "reason": reason or "Applied deterministic correction.",
    }


def _build_fix_prompt(code: str, error_type: str, error_message: str, traceback_text: str) -> str:
    return _build_strict_fix_prompt(
        code=code,
        error_type=error_type,
        error_message=error_message,
        traceback_text=traceback_text,
    )


def _openai_fix(code: str, error_type: str, error_message: str, traceback_text: str) -> str:
    if not _openai_available():
        LOGGER.warning("OpenAI unavailable or OPENAI_API_KEY missing. Falling back to deterministic fixer.")
        return ""

    prompt = _build_fix_prompt(
        code=str(code),
        error_type=str(error_type or "Error"),
        error_message=str(error_message or ""),
        traceback_text=str(traceback_text or ""),
    )

    try:
        raw = _openai_chat(
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert Python debugger. Return only corrected full Python code.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
        )
        fixed_code = clean_code(raw)
        LOGGER.info("OpenAI fix response length: %d", len(fixed_code))
        return fixed_code
    except Exception as exc:  # pragma: no cover
        LOGGER.exception("OpenAI fix error: %s", exc)
        return ""


def ai_fix_code(code: str, error: str, execution: Optional[Dict[str, Any]] = None) -> str:
    if not code or not str(code).strip():
        return ""

    error_text = str(error or "")

    execution_context: Dict[str, Any]
    if execution and isinstance(execution, dict):
        execution_context = {
            "error_type": str(execution.get("error_type") or ""),
            "error_message": str(execution.get("error_message") or error_text),
            "traceback": str(execution.get("traceback") or error_text),
            "error_line": execution.get("error_line"),
        }
        error_text = execution_context["traceback"] or execution_context["error_message"]
    else:
        execution_context = {
            "error_type": "",
            "error_message": error_text,
            "traceback": error_text,
            "error_line": _extract_error_line_from_text(error_text),
        }

    fixed_code = _openai_fix(
        code=str(code),
        error_type=str(execution_context.get("error_type") or _infer_error_type(error_text, error_text)),
        error_message=str(execution_context.get("error_message") or error_text),
        traceback_text=str(execution_context.get("traceback") or error_text),
    )
    if fixed_code and fixed_code.strip() and fixed_code.strip() != str(code).strip():
        return fixed_code

    fallback = deterministic_fix(str(code), execution_context)
    if fallback.get("fix_available"):
        return str(fallback.get("fixed_code") or "")
    return ""


def _execution_summary(execution: Optional[Dict[str, Any]]) -> str:
    if not execution:
        return "No runtime execution context provided."

    success = bool(execution.get("success"))
    if success:
        output = str(execution.get("stdout") or execution.get("output") or "")
        return f"Program currently runs. Output: {output[:1200]}"

    return (
        f"error_type={execution.get('error_type')}\n"
        f"error_message={execution.get('error_message')}\n"
        f"error_line={execution.get('error_line')}\n"
        f"traceback={str(execution.get('traceback') or '')[:2500]}"
    )


def _openai_assist(code: str, prompt: str, execution: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not _openai_available():
        return None

    user_prompt = str(prompt or "").strip() or "Help me improve this code and suggest next steps."
    code_block = str(code or "")

    system_instruction = (
        "You are a beginner-friendly Python mentor. "
        "Always return strict JSON only with keys: assistant_message, suggestions, generated_code. "
        "assistant_message must be concise and actionable. suggestions must be an array of short steps. "
        "generated_code must contain full runnable Python code when a code change is useful, else empty string."
    )

    user_message = (
        f"Learner question:\n{user_prompt}\n\n"
        f"Current code:\n{code_block}\n\n"
        f"Execution context:\n{_execution_summary(execution)}\n\n"
        "Return JSON only."
    )

    try:
        raw = _openai_chat(
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_message},
            ],
            temperature=0.2,
        )

        parsed = _extract_json_object(raw)
        if not parsed:
            assistant_message = str(raw or "").strip() or "I could not parse a structured AI answer."
            return {
                "assistant_message": assistant_message,
                "suggestions": [],
                "generated_code": "",
                "can_apply": False,
                "source": "openai",
            }

        assistant_message = str(parsed.get("assistant_message") or "I reviewed your code.").strip()
        suggestions = _safe_suggestions(parsed.get("suggestions"))
        generated_code = clean_code(str(parsed.get("generated_code") or ""))
        can_apply = bool(generated_code and generated_code.strip() and generated_code.strip() != code_block.strip())

        return {
            "assistant_message": assistant_message,
            "suggestions": suggestions,
            "generated_code": generated_code,
            "can_apply": can_apply,
            "source": "openai",
        }
    except Exception as exc:  # pragma: no cover
        LOGGER.exception("OpenAI assist error: %s", exc)
        return None


def ai_assist(code: str, prompt: str, execution: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    code_text = str(code or "")
    prompt_text = str(prompt or "").strip()

    ai_result = _openai_assist(code_text, prompt_text, execution)
    if ai_result:
        return ai_result

    execution = execution or {}
    fix_result = deterministic_fix(code_text, execution) if code_text.strip() else {
        "fix_available": False,
        "fixed_code": "",
    }

    error_type = str(execution.get("error_type") or "")
    if error_type:
        base_message = (
            f"I could not reach OpenAI right now. I found a `{error_type}` issue. "
            "Use the suggestions below and try Run again."
        )
    else:
        base_message = (
            "I could not reach OpenAI right now. Share what you want to build in the prompt box "
            "and I can still guide you with local suggestions."
        )

    fallback_suggestions = [
        "Describe your goal in one sentence, for example: build a number guessing game.",
        "Run code after every small edit so errors stay easy to fix.",
        "When you get an error, fix the first traceback line first.",
        "If Apply Fix is available, apply it and run again.",
    ]

    generated_code = str(fix_result.get("fixed_code") or "") if fix_result.get("fix_available") else ""
    can_apply = bool(generated_code and generated_code.strip() and generated_code.strip() != code_text.strip())

    return {
        "assistant_message": base_message,
        "suggestions": fallback_suggestions,
        "generated_code": generated_code,
        "can_apply": can_apply,
        "source": "fallback",
    }


def generate_fixed_code(
    code: str,
    execution: Dict[str, Any],
    model: str = OPENAI_MODEL,
    use_ollama: bool = False,
) -> Dict[str, Any]:
    _ = model
    _ = use_ollama

    deterministic = deterministic_fix(code, execution)
    if deterministic["fix_available"]:
        return {
            "fixed_code": deterministic["fixed_code"],
            "source": "deterministic",
            "error": None,
            "reason": deterministic["reason"],
        }

    error_text = str(execution.get("traceback") or execution.get("error_message") or "")
    ai_code = ai_fix_code(code, error_text, execution=execution)
    if ai_code and ai_code.strip() and ai_code.strip() != code.strip():
        return {
            "fixed_code": ai_code,
            "source": "openai",
            "error": None,
            "reason": "Generated by OpenAI.",
        }

    return {
        "fixed_code": code,
        "source": "none",
        "error": "No automatic fix generated.",
        "reason": "No deterministic or OpenAI fix available.",
    }
