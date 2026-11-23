"""GestureOS native Windows desktop application entry point."""
from __future__ import annotations
# IMPORTANT: initialize MediaPipe before Qt/scientific libraries on Windows.
# This ordering is intentional due to the original project's native DLL failure.
try:
    import mediapipe as _mediapipe  # noqa: F401
    MEDIAPIPE_IMPORT_ERROR = None
except Exception as _exc:
    MEDIAPIPE_IMPORT_ERROR = _exc

import sys, time
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap, QAction, QKeySequence
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QLabel,QPushButton,QCheckBox,
    QVBoxLayout,QHBoxLayout,QGridLayout,QGroupBox,QTextEdit,QMessageBox,QSystemTrayIcon,
    QMenu,QComboBox,QSlider,QFormLayout,QFrame)
from gestureos_engine import GestureWorker

APP_STYLE = """
QMainWindow,QWidget { background:#101827; color:#edf2f7; font-family:'Segoe UI'; font-size:10pt; }
QGroupBox { border:1px solid #34445c; border-radius:12px; margin-top:12px; padding:14px; font-weight:600; }
QGroupBox::title { subcontrol-origin:margin; left:12px; padding:0 5px; color:#8db8ff; }
QPushButton { background:#2459a6; border:0; border-radius:8px; padding:10px 15px; color:white; font-weight:600; }
QPushButton:hover { background:#3275cf; } QPushButton:disabled { background:#354052; color:#9aa4b2; }
QPushButton#danger { background:#a83245; } QCheckBox { spacing:8px; } QTextEdit { background:#0b1220; border:1px solid #34445c; border-radius:8px; }
QLabel#muted { color:#a9b7ca; } QComboBox { background:#1d2a3d; padding:7px; border-radius:6px; }
"""

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle('GestureOS'); self.resize(1120,760)
        self.worker=None; self.tray=None; self._build(); self._tray()
        if MEDIAPIPE_IMPORT_ERROR:
            self._log('MediaPipe import failed before camera startup: '+repr(MEDIAPIPE_IMPORT_ERROR))
            self.start_btn.setEnabled(False)
            QMessageBox.critical(self,'MediaPipe initialization failed',
                'GestureOS could not initialize MediaPipe.\n\n'+str(MEDIAPIPE_IMPORT_ERROR)+
                '\n\nCheck the bundled Python/runtime dependencies and Microsoft Visual C++ Redistributable. See logs/gestureos.log.')

    def _build(self):
        root=QWidget(); self.setCentralWidget(root); layout=QVBoxLayout(root); layout.setSpacing(14)
        header=QHBoxLayout(); title=QLabel('GestureOS'); title.setStyleSheet('font-size:28pt;font-weight:700;color:#8db8ff')
        subtitle=QLabel('Hands-free desktop control'); subtitle.setObjectName('muted')
        header.addWidget(title); header.addWidget(subtitle); header.addStretch(); layout.addLayout(header)
        body=QGridLayout(); layout.addLayout(body,1)
        self.preview=QLabel('Camera preview will appear here'); self.preview.setAlignment(Qt.AlignCenter); self.preview.setMinimumSize(640,480)
        self.preview.setStyleSheet('background:#080d16;border:1px solid #34445c;border-radius:12px;color:#8493a8')
        body.addWidget(self.preview,0,0,2,1)
        controls=QVBoxLayout(); body.addLayout(controls,0,1)
        statebox=QGroupBox('Control centre'); f=QVBoxLayout(statebox)
        self.status=QLabel('Status: stopped'); self.status.setStyleSheet('font-size:14pt;font-weight:600;color:#f5c76b')
        self.mode=QLabel('SAFE SIMULATION'); self.mode.setStyleSheet('font-size:12pt;color:#7dd3a7;font-weight:700')
        f.addWidget(self.status); f.addWidget(self.mode)
        self.start_btn=QPushButton('Start camera'); self.start_btn.clicked.connect(self.start_camera); f.addWidget(self.start_btn)
        self.activate_btn=QPushButton('Activate gesture control'); self.activate_btn.clicked.connect(lambda:self.set_active(True)); self.activate_btn.setEnabled(False); f.addWidget(self.activate_btn)
        self.deactivate_btn=QPushButton('Deactivate control'); self.deactivate_btn.clicked.connect(lambda:self.set_active(False)); self.deactivate_btn.setEnabled(False); f.addWidget(self.deactivate_btn)
        self.real=QCheckBox('Enable real mouse and keyboard actions'); self.real.setChecked(False); self.real.stateChanged.connect(self._mode_changed); f.addWidget(self.real)
        warning=QLabel('Real actions can affect other applications. Start in simulation and test carefully.'); warning.setWordWrap(True); warning.setObjectName('muted'); f.addWidget(warning)
        self.estop_btn=QPushButton('EMERGENCY STOP'); self.estop_btn.setObjectName('danger'); self.estop_btn.clicked.connect(self.emergency_stop); f.addWidget(self.estop_btn)
        self.reset_btn=QPushButton('Reset emergency stop'); self.reset_btn.clicked.connect(self.reset_estop); f.addWidget(self.reset_btn)
        self.stop_btn=QPushButton('Stop camera'); self.stop_btn.clicked.connect(self.stop_camera); self.stop_btn.setEnabled(False); f.addWidget(self.stop_btn)
        controls.addWidget(statebox)
        gestures=QGroupBox('Gesture reference'); gl=QVBoxLayout(gestures)
        for line in ['Open palm · hold to activate','Fist · deactivate | hold 2 seconds · emergency stop','Peace · previous item | three fingers · next item','Index pointing · move cursor','Thumbs up · left click','Pinch and move · drag and drop | hold still · right click','Swipe up/down · scroll','Thumb left/right · volume down/up | thumb down · mute','Pinky · show desktop | four fingers · switch application']:
            lab=QLabel('• '+line); lab.setWordWrap(True); gl.addWidget(lab)
        controls.addWidget(gestures); controls.addStretch()
        logbox=QGroupBox('Activity and diagnostics'); ll=QVBoxLayout(logbox); self.log=QTextEdit(); self.log.setReadOnly(True); self.log.setMaximumHeight(120); ll.addWidget(self.log); layout.addWidget(logbox)
        self._log('Ready. Camera processing is local. Real actions are disabled by default.')
        # Physical emergency shortcut: Ctrl+Shift+Esc.
        shortcut=QAction(self); shortcut.setShortcut(QKeySequence('Ctrl+Shift+F12')); shortcut.triggered.connect(self.emergency_stop); self.addAction(shortcut)

    def _tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable(): return
        self.tray=QSystemTrayIcon(self); self.tray.setToolTip('GestureOS')
        menu=QMenu(); show=menu.addAction('Show GestureOS'); show.triggered.connect(self.showNormal)
        stop=menu.addAction('Emergency stop'); stop.triggered.connect(self.emergency_stop)
        quit_action=menu.addAction('Quit'); quit_action.triggered.connect(self._quit)
        self.tray.setContextMenu(menu); self.tray.show()

    def _log(self,text):
        stamp=time.strftime('%H:%M:%S'); self.log.append(f'[{stamp}] {text}')
        try:
            Path('logs').mkdir(exist_ok=True); Path('logs/gestureos.log').open('a',encoding='utf8').write(f'[{stamp}] {text}\n')
        except Exception: pass

    def start_camera(self):
        if self.worker and self.worker.isRunning(): return
        self.worker=GestureWorker(); self.worker.frame_ready.connect(self._frame); self.worker.status.connect(self._status); self.worker.event.connect(self._log); self.worker.state.connect(self._state)
        self.worker.set_simulation(not self.real.isChecked()); self.worker.start()
        self.start_btn.setEnabled(False); self.stop_btn.setEnabled(True); self.activate_btn.setEnabled(True); self.deactivate_btn.setEnabled(True)
        self._log('Starting webcam and loading local gesture models…')

    def _frame(self,arr):
        h,w,ch=arr.shape; q=QImage(arr.data,w,h,ch*w,QImage.Format_RGB888).copy()
        self.preview.setPixmap(QPixmap.fromImage(q).scaled(self.preview.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation))
    def _status(self,msg): self.status.setText('Status: '+msg.splitlines()[0]); self._log(msg)
    def _state(self,active,estop):
        self.status.setText('Status: '+('ACTIVE' if active else 'inactive')+(' · emergency stop latched' if estop else ''))
        self.status.setStyleSheet('font-size:14pt;font-weight:600;color:'+('#7dd3a7' if active else '#f5c76b'))
    def _mode_changed(self,state):
        if state and QMessageBox.warning(self,'Enable real desktop actions','Gestures will control your actual mouse and keyboard in other applications. Continue?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No) != QMessageBox.Yes:
            self.real.blockSignals(True); self.real.setChecked(False); self.real.blockSignals(False); state=0
        if self.worker: self.worker.set_simulation(not bool(state))
        self.mode.setText('SAFE SIMULATION' if not state else 'REAL ACTIONS ENABLED')
        self.mode.setStyleSheet('font-size:12pt;font-weight:700;color:'+('#7dd3a7' if not state else '#ff9c85'))
        self._log('Real desktop actions '+('enabled' if state else 'disabled'))
    def set_active(self,value):
        if self.worker: self.worker.set_enabled(value); self._log('Gesture control '+('activated' if value else 'deactivated'))
    def emergency_stop(self):
        if self.worker: self.worker.emergency_stop()
        self.real.setChecked(False); self._log('EMERGENCY STOP: actions disabled and held inputs released')
    def reset_estop(self):
        if self.worker: self.worker.reset_estop()
        self._log('Emergency stop reset. Control remains inactive.')
    def stop_camera(self):
        if self.worker: self.worker.stop(); self.worker=None
        self.start_btn.setEnabled(True); self.stop_btn.setEnabled(False); self.activate_btn.setEnabled(False); self.deactivate_btn.setEnabled(False); self.preview.setText('Camera stopped'); self.preview.setPixmap(QPixmap())
        self.status.setText('Status: stopped'); self._log('Camera stopped and released.')
    def closeEvent(self,event):
        if self.tray and self.tray.isVisible():
            self.hide(); self.tray.showMessage('GestureOS','Running in the system tray. Choose Quit to exit.'); event.ignore()
        else: self._quit(); event.accept()
    def _quit(self):
        if self.worker: self.worker.stop(); self.worker=None
        if self.tray: self.tray.hide()
        QApplication.quit()

def main():
    app=QApplication(sys.argv); app.setStyleSheet(APP_STYLE); win=MainWindow(); win.show(); return app.exec()

if __name__=='__main__':
    sys.exit(main())
