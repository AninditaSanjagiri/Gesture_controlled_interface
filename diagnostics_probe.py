"""Temporary diagnostic: call the cached detector loader in Streamlit AppTest."""
from __future__ import annotations

from streamlit.testing.v1 import AppTest


APP_SOURCE = r'''
import os
import re
import sys
import threading
import traceback

import streamlit as st

# AppTest.from_string executes a temporary script outside the project tree. Add
# the current project directory as Streamlit supplies it when launched from root.
project_root = os.getcwd()
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import config
from src.ui import _load_detector


def safe_path_value(value):
    """Redact the current user's home directory from displayed paths."""
    replacements = (
        os.environ.get("USERPROFILE", ""),
        os.environ.get("HOME", ""),
        os.path.expanduser("~"),
    )
    for path in replacements:
        if path:
            value = re.sub(re.escape(path), "%USERPROFILE%", value, flags=re.IGNORECASE)
    return value


st.text("sys.executable: " + sys.executable)
st.text("cwd: " + os.getcwd())
st.text("thread: " + threading.current_thread().name)

relevant_path = [
    p for p in sys.path
    if any(token in p.lower() for token in ("gesture_controlled_interface", ".venv", "python311", "site-packages"))
]
st.text("relevant sys.path: " + repr([safe_path_value(p) for p in relevant_path]))

safe_env_names = (
    "PYTHONHOME", "PYTHONPATH", "PYTHONNOUSERSITE", "PYTHONUTF8", "VIRTUAL_ENV",
    "CUDA_PATH", "MEDIAPIPE_DLL_PATH", "OPENCV_DIR",
)
safe_env = {name: safe_path_value(os.environ[name]) for name in safe_env_names if name in os.environ}
path_tokens = ("python", ".venv", "windows", "cuda", "opencv", "mediapipe", "vc\\", "vc14")
dll_path_entries = [
    safe_path_value(part) for part in os.environ.get("PATH", "").split(os.pathsep)
    if any(token in part.lower() for token in path_tokens)
]
safe_env["PATH_relevant_entries"] = dll_path_entries
st.text("relevant environment: " + repr(safe_env))

settings = config.Settings()
try:
    model_mtime = config.HAND_MODEL_PATH.stat().st_mtime if config.HAND_MODEL_PATH.exists() else 0.0
    detector = _load_detector(
        settings.min_detection_conf,
        settings.min_tracking_conf,
        model_mtime,
    )
    st.text("detector initialization: SUCCESS")
    st.text("detector type: " + type(detector).__module__ + "." + type(detector).__name__)
except Exception:
    st.text("detector initialization: FAILURE")
    st.text(traceback.format_exc())
'''


def main() -> int:
    # Run this file in a fresh Python process so Streamlit's resource cache starts empty.
    app = AppTest.from_string(APP_SOURCE).run(timeout=120)
    texts = [element.value for element in app.text]
    for value in texts:
        print(value)

    if app.exception:
        print("AppTest runner exception(s):")
        for element in app.exception:
            print(element.value)
        return 2
    return 1 if any("detector initialization: FAILURE" in value for value in texts) else 0


if __name__ == "__main__":
    raise SystemExit(main())
