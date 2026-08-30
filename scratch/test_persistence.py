
import sys
import os
import json
from pathlib import Path

# Mocking config.py logic
DEFAULT_EXECUTOR = ""
BASE_DIR = Path(".").resolve()
EXECUTOR_JSON = BASE_DIR / "executor.json"

def _read_json(path, default):
    try:
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _normalize_executor(obj):
    if obj is None: return DEFAULT_EXECUTOR
    if isinstance(obj, str): return obj
    return DEFAULT_EXECUTOR

def load_executor():
    raw = _read_json(EXECUTOR_JSON, DEFAULT_EXECUTOR)
    return _normalize_executor(raw)

def save_executor(name):
    norm = _normalize_executor(name)
    with EXECUTOR_JSON.open("w", encoding="utf-8") as f:
        json.dump(norm, f, ensure_ascii=False, indent=2)

# Test sequence
print(f"Initial load: '{load_executor()}'")

save_executor("松原")
print(f"After save: '{load_executor()}'")

# Simulate what might be happening
# If update_executor("") is called...
save_executor("")
print(f"After clearing: '{load_executor()}'")
