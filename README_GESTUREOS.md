# GestureOS

GestureOS is a Windows desktop prototype for local, webcam-based hand-gesture control. It builds on the supplied PS 15 project: MediaPipe hand landmarks, the existing 88-feature extractor, and the supplied Random Forest model. The native interface uses PySide6.

## What is included

- Native PySide6 desktop interface with webcam preview, activity log, system-tray support and emergency-stop controls.
- One-hand MediaPipe Tasks tracking using the supplied `models/hand_landmarker.task`.
- Existing Random Forest bundle (`models/gesture_rf.joblib`) and its original six labels. The model is not retrained or altered.
- Temporal stability filtering and simple trajectory rules for swipe/scroll gestures.
- Safe simulation mode by default. Real desktop actions require an explicit checkbox and confirmation.
- Windows packaging spec and Inno Setup installer script.
- Original dataset, metrics and evaluation artifacts retained for reproducibility.

## Current gesture implementation

| Gesture | Action |
|---|---|
| Open palm held ~0.7 s | Activate control |
| Fist | Deactivate; holding for ~2 s latches emergency stop |
| Peace | Previous item |
| Three extended fingers | Next item |
| Vertical swipe | Scroll up/down |
| Index pointing | Move cursor |
| Thumbs up | Left click |
| Pinch and move | Drag/drop; short stationary pinch release maps to right-click |
| Thumb pointing left/right | Volume down/up (heuristic) |
| Thumb down while fist-like | Mute (heuristic) |
| Pinky only | Show desktop |
| Four fingers | Switch application |

Gesture recognition beyond the original six classes uses geometric/temporal heuristics, not a newly trained model. The three-finger, thumb-direction and pinch thresholds are initial defaults and require webcam testing and calibration. The supplied RF model was trained for OPEN_PALM, FIST, THUMBS_UP, PEACE, POINTING and NO_GESTURE only.

## Windows setup

Use Windows 10/11 x64 and Python 3.11 x64. Install the Microsoft Visual C++ 2015–2022 Redistributable (x64) before troubleshooting native DLL failures.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-windows.txt
python diagnose_windows.py
python gestureos_app.py
```

The dependency pins match the supplied model's training environment (scikit-learn 1.6.1) and the original MediaPipe 0.10.21 / NumPy 1.26.4 combination. `gestureos_app.py` intentionally imports MediaPipe before Qt and the scientific Python stack because the original project encountered a Windows native-binding initialization error. This import ordering is a mitigation, not proof that every Windows environment is fixed. `diagnose_windows.py` performs the actual import and model initialization checks.

If MediaPipe still reports `_framework_bindings` DLL initialization failure:

1. Confirm 64-bit Python 3.11 is being used (`python -c "import struct; print(struct.calcsize('P')*8)"`).
2. Install/repair Microsoft Visual C++ Redistributable 2015–2022 x64 and reboot.
3. Recreate the virtual environment; do not mix global Python packages with the venv.
4. Run `python diagnose_windows.py` and retain the full traceback. Do not install multiple OpenCV distributions simultaneously.

## Safety

- Simulation is the default. In simulation, no OS input is sent.
- Real actions require the user to explicitly enable the checkbox and confirm the warning.
- The physical emergency shortcut is `Ctrl+Shift+F12`.
- Emergency stop disables control, switches back to simulation and releases a held mouse button.
- Closing/stopping the camera releases the camera and held mouse input.
- Webcam frames are processed locally; this code does not upload frames or landmarks.
- Do not map gestures to destructive actions. GestureOS is not a secure authentication mechanism and should not be used to approve payments, security prompts or irreversible operations.

## Build a Windows executable

From a clean Windows machine with the dependencies installed:

```powershell
.\build_windows.ps1
```

The PyInstaller one-folder build is placed in `dist\GestureOS\`. To create an installer, install Inno Setup and compile `installer\GestureOS.iss`. The installer script expects the PyInstaller output folder to exist.

A successful build on another OS is not evidence of a working Windows package. Test the resulting build on a clean Windows 10/11 x64 machine without Python installed. For public distribution, obtain an Authenticode code-signing certificate and sign the executable/installer; the supplied build is not signed.

## Important validation status

This source bundle was assembled and syntax-checked in a Linux build environment. This environment did not have MediaPipe, PySide6 or pynput installed and had no Windows webcam or desktop session. Therefore, the actual Windows MediaPipe DLL initialization, camera feed, native input controls, and installer have **not** been verified here. Run `diagnose_windows.py` and complete real-hardware tests before distributing it. The supplied trained model and hand-landmarker asset are included, but the model's predictions must also be validated with the intended webcam and users.

## Project structure

- `gestureos_app.py`: PySide6 desktop interface and startup import ordering.
- `gestureos_engine.py`: webcam worker, gesture interpretation and guarded OS actions.
- `src/feature_extractor.py`: original versioned 88-feature extractor.
- `src/gesture_classifier.py`: original Random Forest loader and stability filter.
- `src/hand_detector.py`: MediaPipe Tasks wrapper.
- `models/`: supplied trained RF model, labels and MediaPipe task asset.
- `data/`: supplied labelled training dataset.
- `results/`: supplied model metrics and reliability artifacts.
- `requirements-windows.txt`: pinned Windows dependencies.
- `GestureOS.spec`, `build_windows.ps1`, `installer/`: packaging configuration.
