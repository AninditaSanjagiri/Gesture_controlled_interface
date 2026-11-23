"""Run with the same Python environment used by GestureOS to diagnose Windows startup."""
import sys, platform, traceback
print('Python:',sys.version)
print('Platform:',platform.platform())
checks=['mediapipe','cv2','numpy','sklearn','PySide6','pynput','pycaw','screeninfo']
for name in checks:
    try:
        module=__import__(name)
        print(f'[OK] {name}: {getattr(module,"__version__","imported")}')
    except Exception:
        print(f'[FAIL] {name}')
        traceback.print_exc()
try:
    from src.gesture_classifier import GestureClassifier
    model=GestureClassifier.load()
    print('[OK] RF bundle:',len(model.feature_names),'features; classes=',model.classes)
except Exception:
    print('[FAIL] RF bundle'); traceback.print_exc()
try:
    from src.hand_detector import HandDetector
    detector=HandDetector(max_hands=1)
    detector.close()
    print('[OK] MediaPipe hand model initialized')
except Exception:
    print('[FAIL] MediaPipe detector initialization'); traceback.print_exc()
