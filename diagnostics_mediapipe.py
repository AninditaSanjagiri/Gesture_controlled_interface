"""Standalone Streamlit diagnostic matching the app's MediaPipe import path.

Run from the project root with:
    .venv\\Scripts\\python.exe -m streamlit run diagnostics\\streamlit_mediapipe_page.py
"""
from __future__ import annotations

import os
import re
import sys
import threading
import traceback

import streamlit as st

# Streamlit adds this page's directory to sys.path. Match app.py, whose script
# directory is the project root, so local imports resolve as they do in production.
PROJECT_ROOT = os.getcwd()
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Mirror app.py's imports, followed by the imports at the top of the Live page.
import config
from src import data_utils as du
from src import ui

import time
import cv2
import pandas as pd
from src.webcam_manager import WebcamError


def _redact(value: str) -> str:
    for home in (os.environ.get("USERPROFILE", ""), os.environ.get("HOME", ""), os.path.expanduser("~")):
        if home:
            value = re.sub(re.escape(home), "%USERPROFILE%", value, flags=re.IGNORECASE)
    return value


def _context() -> dict:
    relevant_paths = [
        _redact(p) for p in sys.path
        if any(token in p.lower() for token in ("gesture_controlled_interface", ".venv", "python311", "site-packages"))
    ]
    env_names = (
        "PYTHONHOME", "PYTHONPATH", "PYTHONNOUSERSITE", "PYTHONUTF8", "VIRTUAL_ENV",
        "CUDA_PATH", "MEDIAPIPE_DLL_PATH", "OPENCV_DIR",
    )
    env = {name: _redact(os.environ[name]) for name in env_names if name in os.environ}
    tokens = ("python", ".venv", "windows", "cuda", "opencv", "mediapipe", "vc\\", "vc14")
    env["PATH_relevant_entries"] = [
        _redact(part) for part in os.environ.get("PATH", "").split(os.pathsep)
        if any(token in part.lower() for token in tokens)
    ]
    return {
        "sys.executable": sys.executable,
        "cwd": os.getcwd(),
        "thread": threading.current_thread().name,
        "sys.path": relevant_paths,
        "environment": env,
    }


st.set_page_config(page_title="MediaPipe initialization diagnostic")
st.title("MediaPipe initialization diagnostic")
st.caption("This page initializes only the hand detector. It does not open the camera or modify project data.")
st.json(_context())

settings = config.Settings()
asset_mtime = config.HAND_MODEL_PATH.stat().st_mtime if config.HAND_MODEL_PATH.exists() else 0.0
try:
    detector = ui._load_detector(
        settings.min_detection_conf,
        settings.min_tracking_conf,
        asset_mtime,
    )
    st.success(f"Detector initialized: {type(detector).__module__}.{type(detector).__name__}")
except Exception:
    st.error("Detector initialization failed. Full traceback:")
    st.code(traceback.format_exc())
