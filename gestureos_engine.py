"""CPU-first webcam/gesture worker for GestureOS. All OS actions are guarded by safe mode."""
from __future__ import annotations
import time, traceback
from collections import deque
import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal
import config
from src.hand_detector import HandDetector, draw_hands
from src.feature_extractor import extract_features, InvalidLandmarksError
from src.gesture_classifier import GestureClassifier, StabilityFilter

class ActionExecutor:
    def __init__(self):
        self.enabled = False
        self.simulation = True
        self.estop = False
        self.mouse = None
        self.keyboard = None
        self.pressed = False
        self.last_action = 0.0
        self.last_gesture = None
        self.release_since = 0.0
        self.dragging = False
        self.last_cursor = None
        self.pinch_since = None
        self.pinch_start = None
        self.last_click = 0.0
        self.volume = None

    def _input(self):
        if self.mouse is None:
            from pynput.mouse import Controller as Mouse
            from pynput.keyboard import Controller as Keyboard
            self.mouse, self.keyboard = Mouse(), Keyboard()
        return self.mouse, self.keyboard

    def release_all(self):
        try:
            if self.mouse is not None and self.pressed:
                from pynput.mouse import Button
                self.mouse.release(Button.left)
        except Exception: pass
        self.pressed = False; self.dragging = False; self.pinch_since = None

    def stop(self, emergency=False):
        self.enabled = False
        self.release_all()
        if emergency: self.estop = True; self.simulation = True

    def _key(self, key):
        if self.simulation: return f"SIMULATED key {key}"
        _, kb = self._input()
        from pynput.keyboard import Key
        kb.press(getattr(Key, key, key)); kb.release(getattr(Key, key, key))
        return f"Pressed {key}"

    def _volume(self, direction):
        if self.simulation: return f"SIMULATED volume {direction}"
        from pycaw.pycaw import AudioUtilities
        device = AudioUtilities.GetSpeakers(); volume = device.EndpointVolume
        if direction == 'up': volume.SetMasterVolumeLevelScalar(min(1.0, volume.GetMasterVolumeLevelScalar()+0.05), None)
        elif direction == 'down': volume.SetMasterVolumeLevelScalar(max(0.0, volume.GetMasterVolumeLevelScalar()-0.05), None)
        else: volume.SetMute(not volume.GetMute(), None)
        return f"Volume {direction}"

    def action(self, name):
        now=time.monotonic()
        if now-self.last_action < .55: return None
        self.last_action=now
        if self.simulation: return f"SIMULATED: {name}"
        if name in ('NEXT','PREVIOUS'):
            return self._key('right' if name=='NEXT' else 'left')
        if name in ('SCROLL_UP','SCROLL_DOWN'):
            m,_=self._input(); m.scroll(0, 3 if name=='SCROLL_UP' else -3); return name
        if name=='CLICK':
            from pynput.mouse import Button
            m,_=self._input(); m.click(Button.left); return 'Left click'
        if name=='RIGHT_CLICK':
            from pynput.mouse import Button
            m,_=self._input(); m.click(Button.right); return 'Right click'
        if name=='VOLUME_UP': return self._volume('up')
        if name=='VOLUME_DOWN': return self._volume('down')
        if name=='MUTE': return self._volume('mute')
        if name=='SHOW_DESKTOP':
            from pynput.keyboard import Key
            _,kb=self._input(); kb.press(Key.cmd); kb.press('d'); kb.release('d'); kb.release(Key.cmd); return 'Show desktop'
        if name=='SWITCH_APP':
            from pynput.keyboard import Key
            _,kb=self._input(); kb.press(Key.alt); kb.press(Key.tab); kb.release(Key.tab); kb.release(Key.alt); return 'Switch application'
        return None

    def cursor(self, x, y, width, height):
        if self.simulation: return
        m,_=self._input()
        from pynput.mouse import Controller
        from screeninfo import get_monitors
        monitors=get_monitors(); mon=monitors[0]
        sx=mon.x+int(np.clip(x,0,1)*mon.width); sy=mon.y+int(np.clip(y,0,1)*mon.height)
        if self.last_cursor is None: self.last_cursor=(sx,sy)
        else:
            # smoothing to reduce jitter
            ox,oy=self.last_cursor; sx=int(.35*sx+.65*ox); sy=int(.35*sy+.65*oy); self.last_cursor=(sx,sy)
        m.position=(sx,sy)

    def pinch(self, is_pinched, x, y, w, h):
        now=time.monotonic()
        if is_pinched:
            if self.pinch_since is None:
                self.pinch_since=now; self.pinch_start=(x,y)
            moved=np.linalg.norm(np.array([x,y])-np.array(self.pinch_start))
            if now-self.pinch_since > .18 and moved > .035 and not self.pressed:
                if not self.simulation:
                    from pynput.mouse import Button
                    m,_=self._input(); m.press(Button.left)
                self.pressed=True; self.dragging=True
            if self.dragging: self.cursor(x,y,w,h)
        elif self.pinch_since is not None:
            duration=now-self.pinch_since
            if self.pressed: self.release_all()
            elif duration>.08: self.action('RIGHT_CLICK')
            self.pinch_since=None; self.pinch_start=None

class GestureWorker(QThread):
    frame_ready=Signal(object); status=Signal(str); event=Signal(str); state=Signal(bool,bool)
    def __init__(self, camera_index=0):
        super().__init__(); self.camera_index=camera_index; self.running=True
        self.executor=ActionExecutor(); self.detector=None; self.classifier=None
        self.filter=StabilityFilter(6,.70); self.history=deque(maxlen=12); self.prev_center=None; self.prev_t=None
        self.fist_since=None; self.palm_since=None; self.swipe_points=deque(maxlen=12); self.last_dynamic=0; self.last_static=None

    def set_simulation(self, value): self.executor.simulation=bool(value)
    def set_enabled(self, value):
        if self.executor.estop and value: return
        self.executor.enabled=bool(value); self.state.emit(self.executor.enabled,self.executor.estop)
        if not value: self.executor.release_all()
    def emergency_stop(self):
        self.executor.stop(True); self.state.emit(False,True); self.event.emit('EMERGENCY STOP')
    def reset_estop(self):
        self.executor.estop=False; self.state.emit(False,False); self.event.emit('Emergency stop reset')
    def stop(self): self.running=False; self.executor.stop(); self.wait(2500)

    def run(self):
        cap=None
        try:
            # Import MediaPipe before model/scientific packages have initialized native runtimes.
            import mediapipe  # noqa: F401
            self.detector=HandDetector(max_hands=1)
            self.classifier=GestureClassifier.load()
            cap=cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW if hasattr(cv2,'CAP_DSHOW') else 0)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH,640); cap.set(cv2.CAP_PROP_FRAME_HEIGHT,480)
            if not cap.isOpened(): raise RuntimeError('Could not open webcam. Check Windows Camera privacy settings and close other camera apps.')
            self.status.emit('Camera connected. Show one hand.')
            while self.running:
                ok,frame=cap.read()
                if not ok: self.msleep(10); continue
                frame=cv2.flip(frame,1); now=time.monotonic(); h,w=frame.shape[:2]
                hand=self.detector.detect(frame); label='NO_HAND'; conf=0.; stable=None
                if hand.detected:
                    try:
                        feat=extract_features(hand.landmarks,hand.handedness)
                        label,conf,_=self.classifier.predict(feat)
                        stable=self.filter.update(label,conf)
                    except InvalidLandmarksError: self.filter.reset()
                    lm=hand.landmarks; center=lm[[0,5,9,13,17],:2].mean(axis=0); x,y=float(center[0]),float(center[1])
                    self.swipe_points.append((now,x,y))
                    if self.prev_center is not None and self.prev_t:
                        speed=np.linalg.norm(center-self.prev_center)/max(now-self.prev_t,1e-3)
                    else: speed=0
                    self.prev_center=(x,y); self.prev_t=now
                    fingers=self._finger_states(lm)
                    # Activation/deactivation safety gestures always have priority.
                    if stable=='OPEN_PALM' and not self.executor.enabled and not self.executor.estop:
                        self.palm_since=self.palm_since or now
                        if now-self.palm_since>=.7:
                            self.executor.enabled=True; self.event.emit('Gesture control activated'); self.state.emit(True,False); self.palm_since=None
                    else: self.palm_since=None
                    if stable=='FIST':
                        self.fist_since=self.fist_since or now
                        if self.executor.enabled: self.executor.stop(); self.state.emit(False,self.executor.estop); self.event.emit('Gesture control deactivated')
                        if now-self.fist_since>=2.0: self.emergency_stop()
                    else: self.fist_since=None
                    if self.executor.enabled and not self.executor.estop:
                        if stable is None or stable == 'NO_GESTURE': self.last_static=None
                        self._process_gestures(stable,fingers,lm,x,y,w,h,now,speed)
                    draw_hands(frame,hand)
                else:
                    self.filter.reset(); self.prev_center=None; self.prev_t=None; self.swipe_points.clear(); self.executor.release_all()
                cv2.putText(frame,f'{label}  {conf:.2f}',(12,25),cv2.FONT_HERSHEY_SIMPLEX,.65,(40,230,160),2)
                cv2.putText(frame,('ACTIVE' if self.executor.enabled else 'INACTIVE')+(' | SAFE SIMULATION' if self.executor.simulation else ' | REAL ACTIONS'),(12,52),cv2.FONT_HERSHEY_SIMPLEX,.55,(0,220,0) if self.executor.enabled else (0,150,255),2)
                rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB); self.frame_ready.emit(rgb)
                self.msleep(1)
        except Exception as e:
            self.status.emit(f'ERROR: {e}\n{traceback.format_exc(limit=3)}')
            self.executor.stop()
        finally:
            self.executor.release_all()
            if cap is not None: cap.release()
            if self.detector: self.detector.close()
            self.status.emit('Camera released.')

    @staticmethod
    def _finger_states(lm):
        # Landmark y increases downward. MCP/PIP/DIP/tip indices for four fingers.
        return [lm[8,1] < lm[6,1], lm[12,1] < lm[10,1], lm[16,1] < lm[14,1], lm[20,1] < lm[18,1]]

    def _process_gestures(self,stable,fingers,lm,x,y,w,h,now,speed):
        # Rule-based dynamic gestures are intentionally separated from the static RF model.
        if len(self.swipe_points)>=7 and now-self.last_dynamic>0.8:
            first=self.swipe_points[0]; dx=x-first[1]; dy=y-first[2]; dt=now-first[0]
            if .12<dt<.8 and abs(dy)>.20 and abs(dy)>abs(dx)*1.25:
                msg=self.executor.action('SCROLL_UP' if dy<0 else 'SCROLL_DOWN')
                if msg: self.event.emit(msg)
                self.last_dynamic=now; self.swipe_points.clear(); return
            if .12<dt<.7 and abs(dx)>.22 and abs(dx)>abs(dy)*1.5:
                msg=self.executor.action('NEXT' if dx>0 else 'PREVIOUS')
                if msg: self.event.emit(msg)
                self.last_dynamic=now; self.swipe_points.clear(); return
        # Pinch has priority over cursor click actions.
        thumb_index=float(np.linalg.norm(lm[4,:2]-lm[8,:2])); pinched=thumb_index<.055
        if stable=='POINTING' and not pinched:
            self.executor.cursor(float(lm[8,0]),float(lm[8,1]),w,h)
        self.executor.pinch(pinched,x,y,w,h)
        if pinched: return
        if stable in ('THUMBS_UP','PEACE') and stable != self.last_static:
            msg=self.executor.action('CLICK' if stable=='THUMBS_UP' else 'PREVIOUS')
            if msg: self.event.emit(msg)
            self.last_static=stable
        elif sum(fingers)==3 and self.last_static!='THREE_FINGERS':
            msg=self.executor.action('NEXT')
            if msg: self.event.emit(msg)
            self.last_static='THREE_FINGERS'
        # Thumb direction heuristics (thumb tip relative to thumb MCP).
        if lm[4,0] < lm[2,0]-.10: self._maybe('VOLUME_DOWN',now)
        elif lm[4,0] > lm[2,0]+.10: self._maybe('VOLUME_UP',now)
        if fingers==[False,False,False,True]: self._maybe('SHOW_DESKTOP',now)
        if sum(fingers)==4: self._maybe('SWITCH_APP',now)
        # A deliberate vertical thumb orientation is treated as mute only with a closed fist.
        if not any(fingers) and lm[4,1] > lm[2,1]+.10: self._maybe('MUTE',now)

    def _maybe(self,name,now):
        if now-self.last_dynamic>1.0:
            msg=self.executor.action(name)
            if msg: self.event.emit(msg)
            self.last_dynamic=now
