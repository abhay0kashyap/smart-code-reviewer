from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


OPENAI_KEY_ENV_NAMES: tuple[str, ...] = (
    "OPENAI_API_KEY",
    "OPENAI_KEY",
    "OPEN_AI_KEY",
)


def _read_env_file(env_path: Path) -> bool:
    loaded = False
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("export "):
            line = line[len("export ") :].strip()

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue

        if value and len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        if key not in os.environ:
            os.environ[key] = value
            loaded = True

    return loaded


def _candidate_env_paths(path: str) -> list[Path]:
    requested = Path(path)
    if requested.is_absolute():
        return [requested]

    repo_root = Path(__file__).resolve().parents[1]
    cwd = Path.cwd()

    candidates = [
        cwd / requested,
        repo_root / requested,
        repo_root / "backend" / requested,
    ]

    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.resolve()) if candidate.exists() else str(candidate)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def load_local_env(path: str = ".env") -> bool:
    """
    Load local env values into process environment if they are not already set.
    Supports common run locations (project root and backend dir).
    """
    loaded_any = False
    for env_path in _candidate_env_paths(path):
        if env_path.exists() and env_path.is_file():
            loaded_any = _read_env_file(env_path) or loaded_any
    return loaded_any


def resolve_first_env_value(names: Iterable[str]) -> str:
    for name in names:
        value = str(os.getenv(name, "")).strip()
        if value:
            return value
    return ""


def resolve_openai_api_key() -> str:
    """
    Resolve OpenAI API key from supported env names.
    Mirrors aliases back to OPENAI_API_KEY for SDK compatibility.
    """
    api_key = resolve_first_env_value(OPENAI_KEY_ENV_NAMES)
    if api_key and not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = api_key
    return api_key
