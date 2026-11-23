$ErrorActionPreference = 'Stop'
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-windows.txt
.\.venv\Scripts\python.exe -c "import mediapipe; print('MediaPipe import OK', mediapipe.__version__)"
.\.venv\Scripts\python.exe -c "import cv2; print('OpenCV import OK', cv2.__version__)"
.\.venv\Scripts\python.exe -c "import PySide6; print('PySide6 import OK', PySide6.__version__)"
.\.venv\Scripts\python.exe -c "import joblib; b=joblib.load('models/gesture_rf.joblib'); print('RF model OK; features:',len(b['feature_names']))"
.\.venv\Scripts\pyinstaller.exe --noconfirm --clean GestureOS.spec
Write-Host 'Build output: dist\GestureOS\GestureOS.exe'
