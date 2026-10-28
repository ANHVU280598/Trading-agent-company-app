"""Persist / load model artifacts. Inference never retrains."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import joblib

from core.config import ROOT

MODELS_DIR = ROOT / "models"
V1_PATH = MODELS_DIR / "model_v1.joblib"
V1_META = MODELS_DIR / "model_v1.json"
V2_PATH = MODELS_DIR / "model_v2.joblib"
V2_META = MODELS_DIR / "model_v2.json"
ACTIVE_PATH = MODELS_DIR / "active_model.json"


def ensure_models_dir() -> Path:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    return MODELS_DIR


def save_model(
    model: Any,
    meta: dict[str, Any],
    *,
    version: str,
) -> tuple[Path, Path]:
    ensure_models_dir()
    if version == "v1":
        path, meta_path = V1_PATH, V1_META
    elif version == "v2":
        path, meta_path = V2_PATH, V2_META
    else:
        raise ValueError(f"unknown version {version}")
    joblib.dump(model, path)
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return path, meta_path


def load_model(version: str) -> tuple[Any, dict[str, Any]]:
    if version == "v1":
        path, meta_path = V1_PATH, V1_META
    elif version == "v2":
        path, meta_path = V2_PATH, V2_META
    else:
        raise ValueError(f"unknown version {version}")
    if not path.exists():
        raise FileNotFoundError(path)
    model = joblib.load(path)
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    return model, meta


def set_active_model(version: str, reason: str) -> None:
    ensure_models_dir()
    ACTIVE_PATH.write_text(
        json.dumps({"version": version, "reason": reason}, indent=2),
        encoding="utf-8",
    )


def get_active_version(default: str = "v1") -> str:
    if not ACTIVE_PATH.exists():
        return default
    data = json.loads(ACTIVE_PATH.read_text(encoding="utf-8"))
    return str(data.get("version") or default)


def load_active_model() -> tuple[Optional[Any], dict[str, Any], str]:
    version = get_active_version("v1")
    # Prefer gated choice; fall back to whichever artifact exists
    for candidate in (version, "v1", "v2"):
        try:
            model, meta = load_model(candidate)
            return model, meta, candidate
        except FileNotFoundError:
            continue
    return None, {}, version
