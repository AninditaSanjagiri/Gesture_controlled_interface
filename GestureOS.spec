# PyInstaller onedir spec. Build from project root on Windows with dependencies installed.
from PyInstaller.utils.hooks import collect_all
mp_datas, mp_bins, mp_hidden = collect_all('mediapipe')
qt_datas, qt_bins, qt_hidden = collect_all('PySide6')
cv_datas, cv_bins, cv_hidden = collect_all('cv2')

a = Analysis(['app.py'], pathex=['.'], binaries=mp_bins+qt_bins+cv_bins,
             datas=mp_datas+qt_datas+cv_datas+[('models/hand_landmarker.task','models'),
                    ('models/gesture_rf.joblib','models'),('models/class_labels.json','models')],
             hiddenimports=mp_hidden+qt_hidden+cv_hidden+['pynput.keyboard._win32','pynput.mouse._win32',
                    'pycaw.pycaw','comtypes','sklearn.ensemble._forest','sklearn.tree._classes'],
             hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=['tkinter','notebook'],
             noarchive=False, optimize=1)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='GestureOS',debug=False,
        bootloader_ignore_signals=False,strip=False,upx=True,console=False,
        disable_windowed_traceback=False,argv_emulation=False,target_arch=None,
        codesign_identity=None,entitlements_file=None)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=True,upx_exclude=[],name='GestureOS')
