import argparse, time, cv2, os, sys, math
import numpy as np
import asyncio
from time import sleep
from enum import Enum, auto
from threading import Lock

from inference import get_model  # Roboflow

ROBOFLOW_MODEL_ID = "my-first-project-h9b7i/14"
ROBOFLOW_API_KEY = "DvvhfNRPyKrEfKNvJuvL"
try:
    from kasa import SmartPlug
    KASA_AVAILABLE = True
except ImportError:
    KASA_AVAILABLE = False
    print("[WARN] kasa module not found. Conveyor control will be disabled.")
    print("[WARN] Install with: pip install python-kasa")

# Import calibration system
try:
    from calibration import CalibrationManager, ArmController, OrientationCalculator
    CALIBRATION_AVAILABLE = True
except ImportError:
    CALIBRATION_AVAILABLE = False
    print("[WARN] calibration.py not found. Running without calibration.")

# Import xarm
try:
    import xarm
    XARM_AVAILABLE = True
except ImportError:
    XARM_AVAILABLE = False
    print("[WARN] xarm module not found. Arm control will be disabled.")

# ============================================================================
# CONVEYOR BELT CONFIGURATION
# ============================================================================
CONVEYOR_PLUG_IP = "192.168.137.242"
GRIP_ROT_SERVO_ID = 2
GRIP_ROT_NEUTRAL = 500
GRIP_ROT_MIN = 130
GRIP_ROT_MAX = 875
GRIP_ROT_FIXED = 130
ROTATION_AFFECTED_STEPS = [1, 2, 3]
ANGLE_ADJUST_MIN = -35.0
ANGLE_ADJUST_MAX = 35.0

# ============================================================================
# POSITION FINE-TUNING CONFIGURATION
# ============================================================================
ENABLE_FINE_TUNING = True
FINE_TUNE_HORIZONTAL_SERVO = 6
FINE_TUNE_HORIZONTAL_FACTOR = 0.15
FINE_TUNE_HORIZONTAL_MAX = 100
FINE_TUNE_VERTICAL_SERVO = 3
FINE_TUNE_VERTICAL_FACTOR = -0.10
FINE_TUNE_VERTICAL_MAX = 80
FINE_TUNE_AFFECTED_STEPS = [1, 2]
FINE_TUNE_DEADZONE_X = 20
FINE_TUNE_DEADZONE_Y = 20

# ============================================================================
# OBJECT CATEGORIZATION
# ============================================================================
RECYCLABLE_ITEMS = ['plastic_bottle', 'glass_bottle', 'metal-can']
NON_RECYCLABLE_ITEMS = ['paper cup', 'chips_bag']
ANGLE_DETECTION_OBJECTS = ['plastic_bottle', 'glass_bottle']
FIXED_ROTATION_OBJECTS = ['paper cup', 'chips_bag', 'metal-can']

# ============================================================================
# STATE MACHINE
# ============================================================================

class SystemState(Enum):
    IDLE = auto()
    PICKING = auto()
    COOLDOWN = auto()


# ============================================================================
# CONVEYOR BELT CONTROL - FIXED WITH CUSTOM EVENT LOOP HANDLER
# ============================================================================

class ConveyorController:
    """
    Fixed conveyor controller with proper asyncio event loop handling.
    Creates a fresh event loop for each async operation.
    """
    
    def __init__(self, plug_ip: str = "10.0.0.94"):
        self.plug_ip = plug_ip
        self.is_initialized = False
        self._state = None
        
        if not KASA_AVAILABLE:
            print("[CONVEYOR] Kasa module not available")
            return
        
        try:
            print(f"[CONVEYOR] Initializing smart plug at {plug_ip}")
            self._initialize()
            self.is_initialized = True
            
        except Exception as e:
            print(f"[CONVEYOR] Failed to initialize: {e}")
            self.is_initialized = False
    
    def _run_coro(self, coro):
        """
        Run a coroutine with a fresh event loop.
        This fixes the "Event loop is closed" error.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            try:
                loop.close()
            except:
                pass
    
    def _initialize(self):
        """Initialize and test connection to smart plug."""
        async def init_async():
            plug = SmartPlug(self.plug_ip)
            await plug.update()
            print(f"[CONVEYOR] Connected to: {plug.alias}")
            print(f"[CONVEYOR] Current state: {'ON' if plug.is_on else 'OFF'}")
            return plug.is_on
        
        self._state = self._run_coro(init_async())
    
    def start(self) -> bool:
        """Start the conveyor belt (turn plug ON)."""
        if not self.is_initialized:
            print("[CONVEYOR] Not initialized, cannot start")
            return False
        
        try:
            async def turn_on():
                plug = SmartPlug(self.plug_ip)
                await plug.update()
                if not plug.is_on:
                    await plug.turn_on()
                    await plug.update()
                return plug.is_on
            
            self._state = self._run_coro(turn_on())
            print("[CONVEYOR] ✓ Started (Plug ON)")
            return True
            
        except Exception as e:
            print(f"[CONVEYOR] Failed to start: {e}")
            return False
    
    def stop(self) -> bool:
        """Stop the conveyor belt (turn plug OFF)."""
        if not self.is_initialized:
            print("[CONVEYOR] Not initialized, cannot stop")
            return False
        
        try:
            async def turn_off():
                plug = SmartPlug(self.plug_ip)
                await plug.update()
                if plug.is_on:
                    await plug.turn_off()
                    await plug.update()
                return plug.is_on
            
            self._state = self._run_coro(turn_off())
            print("[CONVEYOR] ✓ Stopped (Plug OFF)")
            return True
            
        except Exception as e:
            print(f"[CONVEYOR] Failed to stop: {e}")
            return False
    
    def get_state(self):
        """Get current conveyor state (cached)."""
        if not self.is_initialized:
            return None
        return self._state


# ============================================================================
# OBJECT ANGLE DETECTION
# ============================================================================

class ObjectAngleDetector:
    """
    Detects the orientation angle of an object from its bounding box region.
    Uses contour analysis and moments to estimate the principal axis.
    """
    
    def __init__(self, debug=False):
        self.debug = debug
    
    def detect_angle(self, frame, x1, y1, x2, y2, label="object"):
        """
        Detect the orientation angle of an object in the given bbox.
        
        Args:
            frame: Full camera frame (BGR)
            x1, y1, x2, y2: Bounding box coordinates
            label: Object label for context
            
        Returns:
            angle_deg: Angle in degrees (-90 to +90)
                      0° = horizontal, +90° = vertical pointing up
                      Returns 0.0 if detection fails
        """
        try:
            roi = frame[y1:y2, x1:x2].copy()
            
            if roi.size == 0:
                return 0.0
            
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            
            binary = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY_INV, 11, 2
            )
            
            contours, _ = cv2.findContours(
                binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            
            if not contours:
                return 0.0
            
            largest_contour = max(contours, key=cv2.contourArea)
            
            rect = cv2.minAreaRect(largest_contour)
            angle = rect[2]
            
            (w, h) = rect[1]
            if w < h:
                angle = angle + 90
            
            if angle > 90:
                angle = angle - 180
            elif angle < -90:
                angle = angle + 180
            
            if self.debug:
                box = cv2.boxPoints(rect)
                box = np.int0(box)
                debug_roi = roi.copy()
                cv2.drawContours(debug_roi, [box], 0, (0, 255, 0), 2)
                cv2.imshow(f"Angle Debug: {label}", debug_roi)
            
            return float(angle)
            
        except Exception as e:
            print(f"[WARN] Angle detection failed: {e}")
            return 0.0


# ============================================================================
# POSITION FINE-TUNING
# ============================================================================

class PositionFineTuner:
    """
    Calculates servo adjustments to compensate for object position offsets.
    Maps pixel coordinates to servo value adjustments.
    """
    
    def __init__(self):
        self.enabled = ENABLE_FINE_TUNING
        self.h_servo = FINE_TUNE_HORIZONTAL_SERVO
        self.h_factor = FINE_TUNE_HORIZONTAL_FACTOR
        self.h_max = FINE_TUNE_HORIZONTAL_MAX
        self.v_servo = FINE_TUNE_VERTICAL_SERVO
        self.v_factor = FINE_TUNE_VERTICAL_FACTOR
        self.v_max = FINE_TUNE_VERTICAL_MAX
        self.deadzone_x = FINE_TUNE_DEADZONE_X
        self.deadzone_y = FINE_TUNE_DEADZONE_Y
        self.affected_steps = FINE_TUNE_AFFECTED_STEPS
    
    def calculate_adjustments(self, object_u: int, object_v: int, 
                            center_x: int, center_y: int) -> dict:
        """Calculate servo adjustments based on object offset from center."""
        if not self.enabled:
            return {
                'enabled': False,
                'offset_x': 0,
                'offset_y': 0,
                'h_servo': self.h_servo,
                'h_adjust': 0,
                'v_servo': self.v_servo,
                'v_adjust': 0
            }
        
        offset_x = object_u - center_x
        offset_y = object_v - center_y
        
        if abs(offset_x) < self.deadzone_x:
            offset_x = 0
        if abs(offset_y) < self.deadzone_y:
            offset_y = 0
        
        h_adjust = int(offset_x * self.h_factor)
        v_adjust = int(offset_y * self.v_factor)
        
        h_adjust = max(-self.h_max, min(self.h_max, h_adjust))
        v_adjust = max(-self.v_max, min(self.v_max, v_adjust))
        
        return {
            'enabled': True,
            'offset_x': offset_x,
            'offset_y': offset_y,
            'h_servo': self.h_servo,
            'h_adjust': h_adjust,
            'v_servo': self.v_servo,
            'v_adjust': v_adjust
        }
    
    def apply_adjustments(self, sequence: list, adjustments: dict) -> list:
        """Apply calculated adjustments to the arm sequence."""
        if not adjustments['enabled']:
            return sequence
        
        for step_idx in self.affected_steps:
            if step_idx >= len(sequence):
                continue
            
            if adjustments['h_adjust'] != 0:
                servo_idx = adjustments['h_servo'] - 1
                if 0 <= servo_idx < len(sequence[step_idx]):
                    old_val = sequence[step_idx][servo_idx]
                    new_val = old_val + adjustments['h_adjust']
                    sequence[step_idx][servo_idx] = new_val
            
            if adjustments['v_adjust'] != 0:
                servo_idx = adjustments['v_servo'] - 1
                if 0 <= servo_idx < len(sequence[step_idx]):
                    old_val = sequence[step_idx][servo_idx]
                    new_val = old_val + adjustments['v_adjust']
                    sequence[step_idx][servo_idx] = new_val
        
        return sequence
    
    def print_adjustments(self, adjustments: dict):
        """Print human-readable adjustment info."""
        if not adjustments['enabled']:
            print("[FINE-TUNE] Disabled")
            return
        
        print(f"[FINE-TUNE] === Position Adjustments ===")
        print(f"[FINE-TUNE] Offset: X={adjustments['offset_x']:+4d}px, Y={adjustments['offset_y']:+4d}px")
        
        if adjustments['h_adjust'] != 0:
            print(f"[FINE-TUNE] Horizontal: Servo {adjustments['h_servo']} {adjustments['h_adjust']:+4d} units")
        else:
            print(f"[FINE-TUNE] Horizontal: No adjustment (within deadzone)")
        
        if adjustments['v_adjust'] != 0:
            print(f"[FINE-TUNE] Vertical: Servo {adjustments['v_servo']} {adjustments['v_adjust']:+4d} units")
        else:
            print(f"[FINE-TUNE] Vertical: No adjustment (within deadzone)")


# ============================================================================
# ANGLE TO SERVO MAPPING
# ============================================================================

def angle_to_servo(angle_deg: float) -> int:
    """Map object angle (in degrees) to servo position value."""
    angle_deg = max(-90.0, min(90.0, angle_deg))
    
    if angle_deg >= 0:
        ratio = angle_deg / 90.0
        servo_val = GRIP_ROT_NEUTRAL + (GRIP_ROT_MAX - GRIP_ROT_NEUTRAL) * ratio
    else:
        ratio = angle_deg / 90.0
        servo_val = GRIP_ROT_NEUTRAL + (GRIP_ROT_NEUTRAL - GRIP_ROT_MIN) * ratio
    
    return int(round(servo_val))


# ============================================================================
# ARM SEQUENCES - LEFT AND RIGHT BOXES
# ============================================================================

BASE_ARM_SEQUENCE_LEFT = [
    [100, 500, 300, 900, 700, 500],
    [100, 500, 150, 660, 310, 500],
    [600, 500, 150, 660, 310, 500],
    [600, 500, 150, 660, 450, 500],
    [600, 500, 150, 660, 450, 1000],
    [600, 500, 125, 800, 475, 1000],
    [250, 500, 125, 800, 475, 1000],
    [250, 500, 125, 900, 700, 1000],
    [250, 500, 300, 900, 700, 500]
]

BASE_ARM_SEQUENCE_RIGHT = [
    [250, 500, 300, 900, 700, 500],
    [250, 500, 150, 660, 310, 500],
    [600, 500, 150, 660, 310, 500],
    [600, 500, 150, 660, 450, 500],
    [600, 500, 150, 660, 450, 0],
    [600, 500, 125, 800, 475, 0],
    [250, 500, 125, 800, 475, 0],
    [250, 500, 125, 900, 700, 0],
    [250, 500, 300, 900, 700, 500]
]


# ============================================================================
# DYNAMIC SEQUENCE BUILDER
# ============================================================================

def build_pick_sequence(label: str, object_angle_deg: float, sequence_type: str,
                       object_u: int, object_v: int, center_x: int, center_y: int) -> list:
    """Build a dynamic pick sequence with gripper rotation and position fine-tuning."""
    if sequence_type == 'right':
        base_sequence = BASE_ARM_SEQUENCE_RIGHT
        box_name = "RIGHT (Non-recyclable)"
    else:
        base_sequence = BASE_ARM_SEQUENCE_LEFT
        box_name = "LEFT (Recyclable)"
    
    print(f"[SEQUENCE] Using {box_name} box sequence")
    
    sequence = [step.copy() for step in base_sequence]
    
    label_lower = label.lower()
    
    if label_lower in FIXED_ROTATION_OBJECTS:
        rotation_value = GRIP_ROT_FIXED
        print(f"[SEQUENCE] Object: {label} → Using FIXED rotation")
        print(f"[SEQUENCE] → Gripper: Servo {GRIP_ROT_SERVO_ID} = {rotation_value} (FIXED)")
        
    elif label_lower in ANGLE_DETECTION_OBJECTS:
        if ANGLE_ADJUST_MIN <= object_angle_deg <= ANGLE_ADJUST_MAX:
            rotation_value = angle_to_servo(object_angle_deg)
            print(f"[SEQUENCE] Object: {label} (bottle) → Using ANGLE-BASED rotation")
            print(f"[SEQUENCE] Object angle: {object_angle_deg:.1f}° (within range)")
            print(f"[SEQUENCE] → Adjusting gripper: Servo {GRIP_ROT_SERVO_ID} = {rotation_value}")
        else:
            rotation_value = GRIP_ROT_NEUTRAL
            print(f"[SEQUENCE] Object: {label} (bottle) → Using NEUTRAL rotation")
            print(f"[SEQUENCE] Object angle: {object_angle_deg:.1f}° (outside range)")
            print(f"[SEQUENCE] → Using neutral gripper position: Servo {GRIP_ROT_SERVO_ID} = {rotation_value}")
    else:
        rotation_value = GRIP_ROT_NEUTRAL
        print(f"[SEQUENCE] Object: {label} (unknown) → Using NEUTRAL rotation")
        print(f"[SEQUENCE] → Gripper: Servo {GRIP_ROT_SERVO_ID} = {rotation_value}")
    
    servo_index = GRIP_ROT_SERVO_ID - 1
    
    for step_idx in ROTATION_AFFECTED_STEPS:
        if 0 <= step_idx < len(sequence):
            sequence[step_idx][servo_index] = rotation_value
            print(f"[SEQUENCE] Step {step_idx}: Set servo {GRIP_ROT_SERVO_ID} to {rotation_value}")
    
    fine_tuner = PositionFineTuner()
    adjustments = fine_tuner.calculate_adjustments(object_u, object_v, center_x, center_y)
    fine_tuner.print_adjustments(adjustments)
    
    if adjustments['enabled']:
        sequence = fine_tuner.apply_adjustments(sequence, adjustments)
    
    return sequence


# ============================================================================
# OBJECT CATEGORIZATION HELPER
# ============================================================================

def get_sequence_type_for_label(label: str) -> str:
    """Determine which box sequence to use based on object label."""
    label_lower = label.lower()
    
    if label_lower in RECYCLABLE_ITEMS:
        return 'left'
    elif label_lower in NON_RECYCLABLE_ITEMS:
        return 'right'
    else:
        print(f"[WARN] Unknown label '{label}', defaulting to LEFT box")
        return 'left'


# ============================================================================
# SYSTEM CONTROLLER - STATE MACHINE
# ============================================================================

class SystemController:
    """
    Central state machine that coordinates conveyor and arm actions.
    Ensures only one pick sequence can run at a time.
    """
    
    def __init__(self, conveyor, arm):
        self.conveyor = conveyor
        self.arm = arm
        self.state = SystemState.IDLE
        self.lock = Lock()
        self._last_pick_time = 0.0
        
        if self.conveyor and self.conveyor.is_initialized:
            print("[SYSTEM] Starting conveyor in IDLE state...")
            self.conveyor.start()
    
    def can_trigger_pick(self, cooldown_s: float) -> bool:
        """Check if system is ready for a new pick action."""
        with self.lock:
            if self.state != SystemState.IDLE:
                return False
            
            now = time.time()
            if now - self._last_pick_time < cooldown_s:
                return False
            
            return True
    
    def execute_pick_sequence(self, label: str, u: int, v: int, conf: float,
                             object_angle_deg: float, center_x: int, center_y: int,
                             cooldown_s: float):
        """Execute a pick sequence with proper state management."""
        with self.lock:
            if self.state != SystemState.IDLE:
                print(f"[SYSTEM] Cannot pick - state is {self.state.name}")
                return False
            
            self.state = SystemState.PICKING
            print(f"[SYSTEM] State: IDLE → PICKING")
        
        try:
            if self.conveyor and self.conveyor.is_initialized:
                print("[SYSTEM] Stopping conveyor...")
                success = self.conveyor.stop()
                if not success:
                    print("[ERROR] Failed to stop conveyor!")
                    return False
                sleep(0.5)
            
            self._run_arm_sequence(label, u, v, conf, object_angle_deg, 
                                  center_x, center_y)
            
            print("[SYSTEM] ✓ Pick sequence complete")
            return True
            
        except Exception as e:
            print(f"[ERROR] Pick sequence failed: {e}")
            import traceback
            traceback.print_exc()
            return False
            
        finally:
            with self.lock:
                self._last_pick_time = time.time()
                self.state = SystemState.COOLDOWN
                print(f"[SYSTEM] State: PICKING → COOLDOWN")
            
            if self.conveyor and self.conveyor.is_initialized:
                print("[SYSTEM] Restarting conveyor...")
                success = self.conveyor.start()
                if not success:
                    print("[ERROR] Failed to restart conveyor!")
                    sleep(0.5)
                    success = self.conveyor.start()
                    if success:
                        print("[SYSTEM] ✓ Conveyor restart successful on retry")
                    else:
                        print("[ERROR] Conveyor restart failed even after retry!")
                sleep(0.3)
            
            with self.lock:
                self.state = SystemState.IDLE
                print(f"[SYSTEM] State: COOLDOWN → IDLE")
    
    def _run_arm_sequence(self, label, u, v, conf, object_angle_deg, 
                         center_x, center_y):
        """Execute the actual arm movement sequence."""
        sequence_type = get_sequence_type_for_label(label)
        
        print(f"\n[ARM] === PICK SEQUENCE ===")
        print(f"[ARM] Target: {label} at ({u}, {v})")
        print(f"[ARM] Confidence: {conf:.2%}")
        print(f"[ARM] Angle: {object_angle_deg:.1f}°")
        print(f"[ARM] Box: {'LEFT (Recyclable)' if sequence_type == 'left' else 'RIGHT (Non-recyclable)'}")
        
        if not XARM_AVAILABLE or self.arm is None:
            print("[WARN] xArm not available. Simulating movement...")
            sleep(3)
            return
        
        try:
            dynamic_sequence = build_pick_sequence(
                label, object_angle_deg, sequence_type,
                u, v, center_x, center_y
            )
            
            print("[ARM] Executing sequence...")
            step_names = ["Home", "Reach", "Grip", "Lift", "Rotate", 
                         "Position", "Release", "Retract", "Home"]
            
            for idx, step in enumerate(dynamic_sequence):
                step_name = step_names[idx] if idx < len(step_names) else f"Step {idx}"
                print(f"[ARM] → {step_name}")
                
                self.arm.setPosition(
                    [[i+1, pos] for i, pos in enumerate(step)],
                    2000
                )
                sleep(1)
            
            sleep(1)
            
        except Exception as e:
            print(f"[ERROR] Arm control failed: {e}")
            raise
        finally:
            try:
                self.arm.servoOff()
            except:
                pass
    
    def get_state(self) -> SystemState:
        """Get current system state (thread-safe)."""
        with self.lock:
            return self.state
    
    def emergency_stop(self):
        """Emergency stop - turn off conveyor and arm."""
        print("[SYSTEM] !!! EMERGENCY STOP !!!")
        with self.lock:
            self.state = SystemState.IDLE
        
        if self.conveyor and self.conveyor.is_initialized:
            self.conveyor.stop()
        
        if self.arm:
            try:
                self.arm.servoOff()
            except:
                pass


# ============================================================================
# ROI-PRIORITY BEST HIT SELECTION
# ============================================================================

def is_in_roi(u: int, v: int, cx: int, cy: int, rx: int, ry: int) -> bool:
    """Check if a point (u, v) is inside the ROI."""
    return (cx - rx) <= u <= (cx + rx) and (cy - ry) <= v <= (cy + ry)


def select_best_hit_with_roi_priority(detections: list, cx: int, cy: int, 
                                      rx: int, ry: int) -> dict:
    """Select the best detection with ROI priority."""
    if not detections:
        return None
    
    roi_detections = []
    all_detections = []
    
    for x1, y1, x2, y2, conf, label in detections:
        u = (x1 + x2) // 2
        v = (y1 + y2) // 2
        in_roi = is_in_roi(u, v, cx, cy, rx, ry)
        
        detection_info = {
            "label": label,
            "conf": float(conf),
            "u": u,
            "v": v,
            "bbox": (x1, y1, x2, y2),
            "in_roi": in_roi
        }
        
        all_detections.append(detection_info)
        if in_roi:
            roi_detections.append(detection_info)
    
    if roi_detections:
        best_hit = max(roi_detections, key=lambda d: d["conf"])
        return best_hit
    
    if all_detections:
        best_hit = max(all_detections, key=lambda d: d["conf"])
        return best_hit
    
    return None


# ============================================================================
# SIMPLIFIED TRIGGER LOGIC
# ============================================================================

def maybe_trigger_arm(system: SystemController, label, u, v, conf, 
                     bbox_coords, frame, cooldown_s, angle_detector):
    """Simplified trigger logic using SystemController."""
    if not system.can_trigger_pick(cooldown_s):
        return
    
    center_x = frame.shape[1] // 2
    center_y = frame.shape[0] // 2
    
    if angle_detector:
        x1, y1, x2, y2 = bbox_coords
        object_angle = angle_detector.detect_angle(frame, x1, y1, x2, y2, label)
    else:
        object_angle = 0.0
    
    print(f"[TRIGGER] Initiating pick for {label}")
    system.execute_pick_sequence(
        label, u, v, conf, object_angle,
        center_x, center_y, cooldown_s
    )


# ============================================================================
# ARGUMENT PARSING
# ============================================================================

def parse():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', type=int, default=0)
    ap.add_argument('--width', type=int, default=1920)
    ap.add_argument('--height', type=int, default=1080)
    ap.add_argument('--fps', type=int, default=30)
    ap.add_argument('--conf', type=float, default=0.40)
    ap.add_argument('--classes', type=str, default='plastic_bottle,glass_bottle,paper cup,metal-can')
    ap.add_argument('--cooldown', type=float, default=2.0)
    ap.add_argument('--stable_n', type=int, default=2)
    ap.add_argument('--roi_x', type=float, default=0.15)
    ap.add_argument('--roi_y', type=float, default=0.15)
    ap.add_argument('--skip_frames', type=int, default=0)
    ap.add_argument('--inference_size', type=int, default=640)
    ap.add_argument('--use_angle', action='store_true',
                    help='Enable angle-aware gripper rotation for bottles')
    ap.add_argument('--debug_angle', action='store_true',
                    help='Show angle detection debug windows')
    ap.add_argument('--show_angle', action='store_true',
                    help='Display detected angle on frame')
    ap.add_argument('--conveyor_ip', type=str, default=CONVEYOR_PLUG_IP,
                    help=f'IP address of Kasa smart plug (default: {CONVEYOR_PLUG_IP})')
    return ap.parse_args()


# ============================================================================
# MODEL LOADING
# ============================================================================

def load_model(conf):
    """Load Roboflow RF-DETR model via the `inference` SDK."""
    if not ROBOFLOW_API_KEY:
        raise RuntimeError("ROBOFLOW_API_KEY not set!")
    
    print(f"[INFO] Loading Roboflow model: {ROBOFLOW_MODEL_ID}")
    model = get_model(
        model_id=ROBOFLOW_MODEL_ID,
        api_key=ROBOFLOW_API_KEY,
    )
    return model


# ============================================================================
# MAIN LOOP
# ============================================================================

def main():
    args = parse()
    
    print(f"\n[INFO] ===== OBJECT CATEGORIZATION =====")
    print(f"[INFO] RECYCLABLE (→ LEFT box): {RECYCLABLE_ITEMS}")
    print(f"[INFO] NON-RECYCLABLE (→ RIGHT box): {NON_RECYCLABLE_ITEMS}")
    print(f"[INFO] ===================================")
    print(f"\n[INFO] ===== ROTATION STRATEGY =====")
    print(f"[INFO] ANGLE-BASED (bottles): {ANGLE_DETECTION_OBJECTS}")
    print(f"[INFO] FIXED ROTATION ({GRIP_ROT_FIXED}): {FIXED_ROTATION_OBJECTS}")
    print(f"[INFO] ===================================")
    print(f"\n[INFO] ===== POSITION FINE-TUNING =====")
    if ENABLE_FINE_TUNING:
        print(f"[INFO] ✓ ENABLED")
        print(f"[INFO] Horizontal: Servo {FINE_TUNE_HORIZONTAL_SERVO}, Factor: {FINE_TUNE_HORIZONTAL_FACTOR}, Max: ±{FINE_TUNE_HORIZONTAL_MAX}")
        print(f"[INFO] Vertical: Servo {FINE_TUNE_VERTICAL_SERVO}, Factor: {FINE_TUNE_VERTICAL_FACTOR}, Max: ±{FINE_TUNE_VERTICAL_MAX}")
        print(f"[INFO] Deadzone: X=±{FINE_TUNE_DEADZONE_X}px, Y=±{FINE_TUNE_DEADZONE_Y}px")
        print(f"[INFO] Affected steps: {FINE_TUNE_AFFECTED_STEPS}")
    else:
        print(f"[INFO] ✗ DISABLED")
    print(f"[INFO] ===================================")
    print(f"\n[INFO] ===== DETECTION STRATEGY =====")
    print(f"[INFO] ROI-Priority Selection: ENABLED")
    print(f"[INFO] ===================================")
    print(f"\n[INFO] ===== STATE MACHINE =====")
    print(f"[INFO] IDLE: Normal detection, conveyor running")
    print(f"[INFO] PICKING: Arm executing, conveyor stopped")
    print(f"[INFO] COOLDOWN: Post-pick, conveyor running")
    print(f"[INFO] ===================================\n")
    
    angle_detector = None
    if args.use_angle:
        angle_detector = ObjectAngleDetector(debug=args.debug_angle)
        print(f"[INFO] ✓ Angle detection ENABLED (for bottles only)")
        print(f"[INFO] Gripper rotation servo: ID{GRIP_ROT_SERVO_ID}")
        print(f"[INFO] Rotation range: {GRIP_ROT_MIN} to {GRIP_ROT_MAX} (neutral: {GRIP_ROT_NEUTRAL})")
        print(f"[INFO] Fixed rotation for non-bottles: {GRIP_ROT_FIXED}")
        print(f"[INFO] Angle threshold: [{ANGLE_ADJUST_MIN}°, {ANGLE_ADJUST_MAX}°]")
    else:
        print(f"[INFO] Using FIXED sequences")
        print(f"[INFO] Non-bottles use fixed rotation: {GRIP_ROT_FIXED}")
    
    arm = None
    if XARM_AVAILABLE:
        try:
            arm = xarm.Controller('USB')
            print("[INFO] ✓ Connected to xArm")
        except Exception as e:
            print(f"[WARN] Could not connect to xArm: {e}")
    
    conveyor = None
    if KASA_AVAILABLE:
        try:
            conveyor = ConveyorController(args.conveyor_ip)
            if conveyor.is_initialized:
                print("[INFO] ✓ Conveyor control ENABLED")
                print(f"[INFO] Plug IP: {args.conveyor_ip}")
            else:
                print("[WARN] Conveyor initialization failed")
                conveyor = None
        except Exception as e:
            print(f"[WARN] Could not initialize conveyor: {e}")
            conveyor = None
    else:
        print("[WARN] Kasa module not available. Install with: pip install python-kasa")
    
    system = SystemController(conveyor, arm)
    print("[INFO] ✓ System controller initialized")
    
    cv2.destroyAllWindows()
    WIN_NAME = f"YOLOv5_DualBox_{os.getpid()}"
    cv2.namedWindow(WIN_NAME, cv2.WINDOW_NORMAL)
    
    ROI_MARGIN_X = float(max(0.0, min(1.0, args.roi_x)))
    ROI_MARGIN_Y = float(max(0.0, min(1.0, args.roi_y)))
    STABLE_N = int(max(1, args.stable_n))
    MIN_CONF = max(0.50, args.conf)
    
    model = load_model(args.conf)
    print(f"[INFO] Detecting with Roboflow model: {ROBOFLOW_MODEL_ID}")
    
    cap = cv2.VideoCapture(args.source, cv2.CAP_DSHOW if os.name == 'nt' else 0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    cap.set(cv2.CAP_PROP_FPS, args.fps)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    
    if not cap.isOpened():
        raise RuntimeError('Could not open camera.')
    
    t_prev = time.time()
    stable_count = 0
    last_label = None
    last_bbox = None
    frame_counter = 0
    last_det = []
    last_angle = 0.0
    
    print("[INFO] Starting detection loop. Press 'q' or ESC to quit.")
    
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            
            H, W = frame.shape[:2]
            cx, cy = W // 2, H // 2
            rx = int(W * ROI_MARGIN_X / 2.0)
            ry = int(H * ROI_MARGIN_Y / 2.0)
            
            frame_counter += 1
            should_detect = (frame_counter % (args.skip_frames + 1) == 0)
            
            if should_detect:
                t0 = time.time()
                rf_result = model.infer(frame, confidence=args.conf)[0]
                infer_ms = (time.time() - t0) * 1000.0
                
                det = []
                for p in rf_result.predictions:
                    x1 = int(p.x - p.width / 2)
                    y1 = int(p.y - p.height / 2)
                    x2 = int(p.x + p.width / 2)
                    y2 = int(p.y + p.height / 2)
                    det.append((x1, y1, x2, y2, float(p.confidence), p.class_name))
                
                last_det = det
            else:
                det = last_det
                infer_ms = 0.0
            
            best_hit = select_best_hit_with_roi_priority(det, cx, cy, rx, ry)
            
            for x1, y1, x2, y2, conf, label in det:
                category = get_sequence_type_for_label(label)
                label_lower = label.lower()
                
                u = (x1 + x2) // 2
                v = (y1 + y2) // 2
                in_roi = is_in_roi(u, v, cx, cy, rx, ry)
                
                is_best_hit = (best_hit is not None and 
                              best_hit["u"] == u and 
                              best_hit["v"] == v and 
                              best_hit["label"] == label)
                
                thickness = 3 if is_best_hit else 2
                
                if category == 'left':
                    box_color = (0, 255, 0)
                    label_suffix = " [R]"
                else:
                    box_color = (0, 165, 255)
                    label_suffix = " [N]"
                
                if label_lower in FIXED_ROTATION_OBJECTS:
                    label_suffix += f" FIX:{GRIP_ROT_FIXED}"
                elif label_lower in ANGLE_DETECTION_OBJECTS:
                    label_suffix += " ANG"
                
                if in_roi:
                    label_suffix += " ✓ROI"
                
                if is_best_hit:
                    label_suffix += " ★BEST"
                
                cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, thickness)
                cv2.putText(frame, f"{label}{label_suffix} {conf:.2f}",
                            (x1, max(20, y1 - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, box_color, 2)
            
            cv2.rectangle(frame, (cx - rx, cy - ry), (cx + rx, cy + ry), (255, 255, 0), 2)
            cv2.putText(frame, "CENTER ROI", (cx - rx, cy - ry - 8),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            
            cv2.line(frame, (cx - 10, cy), (cx + 10, cy), (255, 255, 0), 1)
            cv2.line(frame, (cx, cy - 10), (cx, cy + 10), (255, 255, 0), 1)
            
            in_roi = False
            if best_hit is not None and best_hit["conf"] >= MIN_CONF:
                u, v = best_hit["u"], best_hit["v"]
                in_roi = best_hit["in_roi"]
                
                cv2.circle(frame, (u, v), 7, (255, 0, 255), -1)
                cv2.circle(frame, (u, v), 5, (0, 255, 0), -1)
                
                if ENABLE_FINE_TUNING:
                    cv2.line(frame, (cx, cy), (u, v), (255, 0, 255), 2)
                    offset_x = u - cx
                    offset_y = v - cy
                    cv2.putText(frame, f"Offset: ({offset_x:+d}, {offset_y:+d})",
                               (10, 150), cv2.FONT_HERSHEY_SIMPLEX, 
                               0.7, (255, 0, 255), 2)
                
                if args.show_angle and angle_detector:
                    x1, y1, x2, y2 = best_hit["bbox"]
                    detected_angle = angle_detector.detect_angle(frame, x1, y1, x2, y2, best_hit["label"])
                    last_angle = detected_angle
                    
                    cv2.putText(frame, f"Angle: {detected_angle:.1f}deg",
                               (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 
                               0.8, (0, 255, 255), 2)
                    
                    length = 50
                    angle_rad = math.radians(detected_angle)
                    dx = int(length * math.cos(angle_rad))
                    dy = int(length * math.sin(angle_rad))
                    cv2.line(frame, (u, v), (u + dx, v - dy), (0, 255, 255), 2)
            
            current_state = system.get_state()
            if current_state == SystemState.IDLE:
                if in_roi and best_hit is not None:
                    if last_label == best_hit["label"]:
                        stable_count += 1
                        last_bbox = best_hit["bbox"]
                    else:
                        last_label = best_hit["label"]
                        last_bbox = best_hit["bbox"]
                        stable_count = 1
                else:
                    stable_count = 0
                    last_label = None
                    last_bbox = None
            else:
                stable_count = 0
                last_label = None
                last_bbox = None
            
            now = time.time()
            fps = 1.0 / max(1e-6, now - t_prev)
            t_prev = now
            
            cv2.putText(frame, f"{fps:4.1f} FPS | {infer_ms:5.1f} ms", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (50, 200, 50), 2)
            cv2.putText(frame, f"Stable: {stable_count}/{STABLE_N}", 
                       (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (50, 200, 50), 2)
            cv2.putText(frame, f"Mode: ROI-PRIORITY", 
                       (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 165, 0), 2)
            
            if args.use_angle:
                cv2.putText(frame, "ANGLE: Bottles only", (W - 250, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            
            if conveyor and conveyor.is_initialized:
                conv_state = conveyor.get_state()
                if conv_state is not None:
                    status_text = "CONVEYOR: ON" if conv_state else "CONVEYOR: OFF"
                    status_color = (0, 255, 0) if conv_state else (0, 0, 255)
                    cv2.putText(frame, status_text, (W - 220, 60),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
            
            if ENABLE_FINE_TUNING:
                cv2.putText(frame, "FINE-TUNE: ON", (W - 220, 90),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)
            
            state = system.get_state()
            state_colors = {
                SystemState.IDLE: (0, 255, 0),
                SystemState.PICKING: (0, 0, 255),
                SystemState.COOLDOWN: (0, 165, 255)
            }
            cv2.putText(frame, f"STATE: {state.name}", 
                       (W - 250, 120),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, 
                       state_colors.get(state, (255, 255, 255)), 2)
            
            cv2.putText(frame, "Green[R] = Recyclable | Orange[N] = Non-Recyclable", 
                       (10, H - 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(frame, f"✓ROI = In ROI | ★BEST = Selected Target", 
                       (10, H - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            if best_hit is not None and in_roi and stable_count >= STABLE_N:
                if current_state == SystemState.IDLE:
                    maybe_trigger_arm(
                        system,
                        best_hit["label"],
                        best_hit["u"],
                        best_hit["v"],
                        best_hit["conf"],
                        best_hit["bbox"],
                        frame,
                        args.cooldown,
                        angle_detector
                    )
                
                stable_count = 0
                last_label = None
                last_bbox = None
            
            cv2.imshow(WIN_NAME, frame)
            k = cv2.waitKey(1) & 0xFF
            if k in (27, ord('q')):
                break
    
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user")
    
    finally:
        print("[INFO] Cleaning up...")
        system.emergency_stop()
        cap.release()
        cv2.destroyAllWindows()
        print("[INFO] Done!")


if __name__ == "__main__":
    main()