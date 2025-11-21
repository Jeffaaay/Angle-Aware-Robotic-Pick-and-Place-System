import argparse, time, cv2, os, sys, math
import numpy as np
import asyncio
from time import sleep

from inference import get_model  # Roboflow

ROBOFLOW_MODEL_ID = "my-first-project-h9b7i/13"
ROBOFLOW_API_KEY = "DvvhfNRPyKrEfKNvJuvL"  # or "YOUR_PRIVATE_API_KEY"
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
CONVEYOR_PLUG_IP = "10.0.0.94"  # Kasa smart plug IP address
                                 # Change this to your plug's IP!
GRIP_ROT_SERVO_ID = 2  # Which servo controls gripper rotation (1-6)
                        # Change this to match your actual hardware!

GRIP_ROT_NEUTRAL = 500  # Neutral position (0° orientation)
GRIP_ROT_MIN = 130      # Minimum value (e.g., -90°)
GRIP_ROT_MAX = 875      # Maximum value (e.g., +90°)

# Fixed rotation value for non-bottle objects
GRIP_ROT_FIXED = 130    # Fixed rotation for paper_cup, chips_bag, aluminum_can

# Which steps in the sequence should have rotation applied
# Indices are 0-based: 0=home, 1=reach, 2=grip, 3=lift, etc.
ROTATION_AFFECTED_STEPS = [1, 2, 3]  # Apply rotation to reach, grip, lift

# Angle adjustment thresholds
# Only adjust gripper rotation if object angle is within this range
# Outside this range, gripper uses neutral position (straight)
ANGLE_ADJUST_MIN = -35.0  # Minimum angle for adjustment (degrees)
ANGLE_ADJUST_MAX = 35.0   # Maximum angle for adjustment (degrees)

# ============================================================================
# POSITION FINE-TUNING CONFIGURATION
# ============================================================================
# Enable/disable fine-tuning
ENABLE_FINE_TUNING = True

# Pixel-to-servo calibration factors (adjust these based on your setup)
# These determine how much the servo moves per pixel of offset
# Positive values: servo increases when object is to the right/down
# Negative values: servo decreases when object is to the right/down

# Horizontal adjustment (left/right)
# Servo 6 (ID 6) controls base rotation - this handles left/right positioning
FINE_TUNE_HORIZONTAL_SERVO = 6  # Base rotation servo (the last one in your array)
FINE_TUNE_HORIZONTAL_FACTOR = 0.15  # Servo units per pixel (start conservative)
FINE_TUNE_HORIZONTAL_MAX = 100  # Maximum adjustment in servo units

# Vertical adjustment (up/down) 
# Servo 3 or 4 typically affects reach distance (forward/back or up/down)
# You may need to experiment with servo 3, 4, or 5 to find which works best
FINE_TUNE_VERTICAL_SERVO = 3  # Shoulder servo - adjust based on your setup
FINE_TUNE_VERTICAL_FACTOR = -0.10  # Servo units per pixel (negative = down when object is lower)
FINE_TUNE_VERTICAL_MAX = 80  # Maximum adjustment in servo units

# Which steps should have fine-tuning applied
# Usually you want to adjust the reach and grip positions
FINE_TUNE_AFFECTED_STEPS = [1, 2]  # Reach and Grip steps

# Deadzone: Don't adjust if object is within this many pixels of center
FINE_TUNE_DEADZONE_X = 20  # pixels
FINE_TUNE_DEADZONE_Y = 20  # pixels

# ============================================================================
# OBJECT CATEGORIZATION
# ============================================================================
# Define which objects go to which box
RECYCLABLE_ITEMS = ['plastic_bottle', 'glass_bottle', 'aluminum_can']
NON_RECYCLABLE_ITEMS = ['paper_cup', 'chips_bag']

# Objects that use angle detection (bottles only)
ANGLE_DETECTION_OBJECTS = ['plastic_bottle', 'glass_bottle']

# Objects that use fixed rotation (everything else)
FIXED_ROTATION_OBJECTS = ['paper_cup', 'chips_bag', 'aluminum_can']

# ============================================================================
# CONVEYOR BELT CONTROL
# ============================================================================

class ConveyorController:
    """
    Controls the conveyor belt via Kasa smart plug.
    Provides synchronous interface using asyncio.
    Creates a fresh SmartPlug instance for each operation to avoid
    communication errors with reused instances.
    """
    
    def __init__(self, plug_ip: str = "10.0.0.94"):
        self.plug_ip = plug_ip
        self.is_initialized = False
        self._state = None  # cached ON/OFF state
        
        if not KASA_AVAILABLE:
            print("[CONVEYOR] Kasa module not available")
            return
        
        try:
            print(f"[CONVEYOR] Initializing smart plug at {plug_ip}")
            # Test connection on init
            asyncio.run(self._test_connection())
            self.is_initialized = True
            
        except Exception as e:
            print(f"[CONVEYOR] Failed to initialize: {e}")
            self.is_initialized = False
    
    async def _test_connection(self):
        """Test connection to smart plug and cache initial state."""
        try:
            # Create fresh plug instance for testing
            plug = SmartPlug(self.plug_ip)
            await plug.update()
            print(f"[CONVEYOR] Connected to: {plug.alias}")
            print(f"[CONVEYOR] Current state: {'ON' if plug.is_on else 'OFF'}")
            # Cache the initial state
            self._state = plug.is_on
        except Exception as e:
            print(f"[CONVEYOR] Connection test failed: {e}")
            raise
    
    async def _turn_on_async(self):
        """Async method to turn conveyor on with fresh plug instance."""
        plug = SmartPlug(self.plug_ip)
        await plug.update()
        await plug.turn_on()
        await plug.update()
        # Update cached state
        self._state = plug.is_on
    
    async def _turn_off_async(self):
        """Async method to turn conveyor off with fresh plug instance."""
        plug = SmartPlug(self.plug_ip)
        await plug.update()
        await plug.turn_off()
        await plug.update()
        # Update cached state
        self._state = plug.is_on
    
    def start(self):
        """Start the conveyor belt (turn plug ON)."""
        if not self.is_initialized:
            print("[CONVEYOR] Not initialized, cannot start")
            return False
        
        try:
            asyncio.run(self._turn_on_async())
            print("[CONVEYOR] ✓ Started (Plug ON)")
            return True
        except Exception as e:
            print(f"[CONVEYOR] Failed to start: {e}")
            return False
    
    def stop(self):
        """Stop the conveyor belt (turn plug OFF)."""
        if not self.is_initialized:
            print("[CONVEYOR] Not initialized, cannot stop")
            return False
        
        try:
            asyncio.run(self._turn_off_async())
            print("[CONVEYOR] ✓ Stopped (Plug OFF)")
            return True
        except Exception as e:
            print(f"[CONVEYOR] Failed to stop: {e}")
            return False
    
    def get_state(self):
        """
        Get current conveyor state (cached, no network call).
        
        Returns:
            bool: True if running (ON), False if stopped (OFF), None if unknown
        """
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
            # Extract ROI
            roi = frame[y1:y2, x1:x2].copy()
            
            if roi.size == 0:
                return 0.0
            
            # Convert to grayscale
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            
            # Apply binary threshold
            # Try adaptive threshold for better results with varying lighting
            binary = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY_INV, 11, 2
            )
            
            # Find contours
            contours, _ = cv2.findContours(
                binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            
            if not contours:
                return 0.0
            
            # Use the largest contour
            largest_contour = max(contours, key=cv2.contourArea)
            
            # Get minimum area rectangle (this gives us orientation)
            rect = cv2.minAreaRect(largest_contour)
            angle = rect[2]  # Angle from minAreaRect
            
            # minAreaRect returns angle in range [-90, 0]
            # We need to adjust to get meaningful orientation
            # The angle represents the rotation of the rectangle
            
            # Normalize angle to [-90, 90] range
            # If width > height, add 90 to get the long axis angle
            (w, h) = rect[1]
            if w < h:
                angle = angle + 90
            
            # Clamp to [-90, 90]
            if angle > 90:
                angle = angle - 180
            elif angle < -90:
                angle = angle + 180
            
            if self.debug:
                # Draw debug visualization
                box = cv2.boxPoints(rect)
                box = np.int0(box)
                debug_roi = roi.copy()
                cv2.drawContours(debug_roi, [box], 0, (0, 255, 0), 2)
                cv2.imshow(f"Angle Debug: {label}", debug_roi)
            
            return float(angle)
            
        except Exception as e:
            print(f"[WARN] Angle detection failed: {e}")
            return 0.0
    
    def detect_angle_from_moments(self, frame, x1, y1, x2, y2):
        """
        Alternative method using image moments.
        More robust for some object types.
        """
        try:
            roi = frame[y1:y2, x1:x2].copy()
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                return 0.0
            
            largest = max(contours, key=cv2.contourArea)
            moments = cv2.moments(largest)
            
            if moments['mu20'] != moments['mu02']:
                angle = 0.5 * math.atan2(2 * moments['mu11'], 
                                         moments['mu20'] - moments['mu02'])
                angle_deg = math.degrees(angle)
                return float(angle_deg)
            
            return 0.0
            
        except Exception as e:
            print(f"[WARN] Moments-based angle detection failed: {e}")
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
        """
        Calculate servo adjustments based on object offset from center.
        
        Args:
            object_u: Object center X coordinate (pixels)
            object_v: Object center Y coordinate (pixels)
            center_x: Camera center X coordinate (pixels)
            center_y: Camera center Y coordinate (pixels)
            
        Returns:
            dict: {
                'enabled': bool,
                'offset_x': int (pixels),
                'offset_y': int (pixels),
                'h_servo': int (servo ID),
                'h_adjust': int (servo units),
                'v_servo': int (servo ID),
                'v_adjust': int (servo units)
            }
        """
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
        
        # Calculate pixel offsets
        offset_x = object_u - center_x  # Positive = object is to the right
        offset_y = object_v - center_y  # Positive = object is below center
        
        # Apply deadzone
        if abs(offset_x) < self.deadzone_x:
            offset_x = 0
        if abs(offset_y) < self.deadzone_y:
            offset_y = 0
        
        # Calculate servo adjustments
        h_adjust = int(offset_x * self.h_factor)
        v_adjust = int(offset_y * self.v_factor)
        
        # Clamp to maximum adjustments
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
        """
        Apply calculated adjustments to the arm sequence.
        
        Args:
            sequence: List of servo position arrays
            adjustments: Dict from calculate_adjustments()
            
        Returns:
            Modified sequence with adjustments applied
        """
        if not adjustments['enabled']:
            return sequence
        
        # Apply adjustments to specified steps
        for step_idx in self.affected_steps:
            if step_idx >= len(sequence):
                continue
            
            # Apply horizontal adjustment
            if adjustments['h_adjust'] != 0:
                servo_idx = adjustments['h_servo'] - 1  # Convert to 0-based
                if 0 <= servo_idx < len(sequence[step_idx]):
                    old_val = sequence[step_idx][servo_idx]
                    new_val = old_val + adjustments['h_adjust']
                    sequence[step_idx][servo_idx] = new_val
            
            # Apply vertical adjustment
            if adjustments['v_adjust'] != 0:
                servo_idx = adjustments['v_servo'] - 1  # Convert to 0-based
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
    """
    Map object angle (in degrees) to servo position value.
    
    Args:
        angle_deg: Object angle in degrees (-90 to +90)
                  -90 = rotated 90° counterclockwise
                    0 = aligned horizontally
                  +90 = rotated 90° clockwise
    
    Returns:
        servo_value: Integer servo position (GRIP_ROT_MIN to GRIP_ROT_MAX)
    """
    # Clamp angle to valid range
    angle_deg = max(-90.0, min(90.0, angle_deg))
    
    # Linear mapping from angle to servo value
    # -90° → GRIP_ROT_MIN
    #   0° → GRIP_ROT_NEUTRAL  
    # +90° → GRIP_ROT_MAX
    
    if angle_deg >= 0:
        # Positive angles: neutral to max
        ratio = angle_deg / 90.0
        servo_val = GRIP_ROT_NEUTRAL + (GRIP_ROT_MAX - GRIP_ROT_NEUTRAL) * ratio
    else:
        # Negative angles: min to neutral
        ratio = angle_deg / 90.0  # This will be negative
        servo_val = GRIP_ROT_NEUTRAL + (GRIP_ROT_NEUTRAL - GRIP_ROT_MIN) * ratio
    
    return int(round(servo_val))


# ============================================================================
# ARM SEQUENCES - LEFT AND RIGHT BOXES
# ============================================================================

# LEFT BOX SEQUENCE (for recyclable items)
BASE_ARM_SEQUENCE_LEFT = [
    [250, 500, 300, 900, 700, 500],  # 0: Home
    [250, 500, 150, 660, 330, 500],  # 1: Reach
    [600, 500, 150, 660, 330, 500],  # 2: Grip (close claw)
    [600, 500, 150, 660, 450, 500],  # 3: Lift a bit
    [600, 500, 150, 660, 450, 1000], # 4: Rotate base to the LEFT side
    [600, 500, 125, 800, 475, 1000], # 5: Adjust pose above drop
    [250, 500, 125, 800, 475, 1000], # 6: Open claw (release)
    [250, 500, 125, 900, 700, 1000], # 7: Move arm back
    [250, 500, 300, 900, 700, 500]   # 8: Back to home
]

# RIGHT BOX SEQUENCE (for non-recyclable items)
BASE_ARM_SEQUENCE_RIGHT = [
    [250, 500, 300, 900, 700, 500],  # 0: Home
    [250, 500, 150, 660, 330, 500],  # 1: Reach
    [600, 500, 150, 660, 330, 500],  # 2: Grip (close claw)
    [600, 500, 150, 660, 450, 500],  # 3: Lift a bit
    [600, 500, 150, 660, 450, 0],    # 4: Rotate base to the RIGHT side
    [600, 500, 125, 800, 475, 0],    # 5: Adjust pose above drop
    [250, 500, 125, 800, 475, 0],    # 6: Open claw (release)
    [250, 500, 125, 900, 700, 0],    # 7: Move arm back
    [250, 500, 300, 900, 700, 500]   # 8: Back to home
]


# ============================================================================
# DYNAMIC SEQUENCE BUILDER
# ============================================================================

def build_pick_sequence(label: str, object_angle_deg: float, sequence_type: str,
                       object_u: int, object_v: int, center_x: int, center_y: int) -> list:
    """
    Build a dynamic pick sequence with gripper rotation and position fine-tuning.
    
    For plastic_bottle and glass_bottle: Uses angle-based rotation (if enabled)
    For all other objects: Uses fixed rotation of 130
    Additionally applies position fine-tuning based on object offset from center.
    
    Args:
        label: Object label (e.g., 'plastic_bottle', 'paper_cup')
        object_angle_deg: Detected object angle in degrees (-90 to +90)
        sequence_type: 'left' or 'right' to choose which sequence to use
        object_u: Object center X coordinate (pixels)
        object_v: Object center Y coordinate (pixels)
        center_x: Camera center X coordinate (pixels)
        center_y: Camera center Y coordinate (pixels)
    
    Returns:
        sequence: List of servo position arrays, ready for arm.setPosition()
    """
    # Select base sequence
    if sequence_type == 'right':
        base_sequence = BASE_ARM_SEQUENCE_RIGHT
        box_name = "RIGHT (Non-recyclable)"
    else:
        base_sequence = BASE_ARM_SEQUENCE_LEFT
        box_name = "LEFT (Recyclable)"
    
    print(f"[SEQUENCE] Using {box_name} box sequence")
    
    # Deep copy the base sequence
    sequence = [step.copy() for step in base_sequence]
    
    # Determine rotation value based on object type
    label_lower = label.lower()
    
    if label_lower in FIXED_ROTATION_OBJECTS:
        # Use fixed rotation for non-bottle objects
        rotation_value = GRIP_ROT_FIXED
        print(f"[SEQUENCE] Object: {label} → Using FIXED rotation")
        print(f"[SEQUENCE] → Gripper: Servo {GRIP_ROT_SERVO_ID} = {rotation_value} (FIXED)")
        
    elif label_lower in ANGLE_DETECTION_OBJECTS:
        # Use angle-based rotation for bottles (if within threshold)
        if ANGLE_ADJUST_MIN <= object_angle_deg <= ANGLE_ADJUST_MAX:
            rotation_value = angle_to_servo(object_angle_deg)
            print(f"[SEQUENCE] Object: {label} (bottle) → Using ANGLE-BASED rotation")
            print(f"[SEQUENCE] Object angle: {object_angle_deg:.1f}° (within range)")
            print(f"[SEQUENCE] → Adjusting gripper: Servo {GRIP_ROT_SERVO_ID} = {rotation_value}")
        else:
            rotation_value = GRIP_ROT_NEUTRAL
            print(f"[SEQUENCE] Object: {label} (bottle) → Using NEUTRAL rotation")
            print(f"[SEQUENCE] Object angle: {object_angle_deg:.1f}° (outside range [{ANGLE_ADJUST_MIN}, {ANGLE_ADJUST_MAX}])")
            print(f"[SEQUENCE] → Using neutral gripper position: Servo {GRIP_ROT_SERVO_ID} = {rotation_value}")
    else:
        # Unknown object, use neutral
        rotation_value = GRIP_ROT_NEUTRAL
        print(f"[SEQUENCE] Object: {label} (unknown) → Using NEUTRAL rotation")
        print(f"[SEQUENCE] → Gripper: Servo {GRIP_ROT_SERVO_ID} = {rotation_value}")
    
    # Apply rotation to specified steps
    servo_index = GRIP_ROT_SERVO_ID - 1  # Convert to 0-based index
    
    for step_idx in ROTATION_AFFECTED_STEPS:
        if 0 <= step_idx < len(sequence):
            sequence[step_idx][servo_index] = rotation_value
            print(f"[SEQUENCE] Step {step_idx}: Set servo {GRIP_ROT_SERVO_ID} to {rotation_value}")
    
    # Apply position fine-tuning
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
    """
    Determine which box sequence to use based on object label.
    
    Args:
        label: Object class label
        
    Returns:
        'left' for recyclable items, 'right' for non-recyclable items
    """
    label_lower = label.lower()
    
    if label_lower in RECYCLABLE_ITEMS:
        return 'left'
    elif label_lower in NON_RECYCLABLE_ITEMS:
        return 'right'
    else:
        # Default to left if unknown
        print(f"[WARN] Unknown label '{label}', defaulting to LEFT box")
        return 'left'


# ============================================================================
# ARM ACTION HANDLERS
# ============================================================================

def handle_arm_action_with_rotation(label: str, u: int, v: int, conf: float,
                                    object_angle_deg: float, 
                                    center_x: int, center_y: int,
                                    arm, conveyor):
    """
    Execute arm pick sequence with label-based rotation logic and position fine-tuning.
    - Bottles (plastic_bottle, glass_bottle): angle-based rotation
    - Other objects (paper_cup, chips_bag, aluminum_can): fixed rotation 130
    - All objects: position fine-tuning based on offset from center
    
    Args:
        label: Object class label
        u, v: Object center coordinates in pixels
        conf: Detection confidence
        object_angle_deg: Detected object angle
        center_x: Camera center X coordinate
        center_y: Camera center Y coordinate
        arm: xArm controller instance
        conveyor: ConveyorController instance
    """
    # Determine which sequence to use based on label
    sequence_type = get_sequence_type_for_label(label)
    
    print(f"\n[ARM] === PICK SEQUENCE WITH ROTATION & FINE-TUNING ===")
    print(f"[ARM] Target: {label} at ({u}, {v})")
    print(f"[ARM] Center: ({center_x}, {center_y})")
    print(f"[ARM] Offset: ({u - center_x:+d}, {v - center_y:+d}) pixels")
    print(f"[ARM] Confidence: {conf:.2%}")
    print(f"[ARM] Object angle: {object_angle_deg:.1f}°")
    print(f"[ARM] Category: {'RECYCLABLE (→ LEFT box)' if sequence_type == 'left' else 'NON-RECYCLABLE (→ RIGHT box)'}")
    
    # Stop conveyor before picking
    if conveyor and conveyor.is_initialized:
        print("[ARM] Stopping conveyor...")
        conveyor.stop()
        sleep(0.5)  # Brief pause to let conveyor fully stop
    
    if not XARM_AVAILABLE or arm is None:
        print("[WARN] xArm not available. Simulating movement...")
        # Still restart conveyor even if arm not available
        if conveyor and conveyor.is_initialized:
            sleep(2)  # Simulate pick time
            print("[ARM] Restarting conveyor...")
            conveyor.start()
        return
    
    try:
        # Build dynamic sequence based on label, angle, and position
        dynamic_sequence = build_pick_sequence(
            label, object_angle_deg, sequence_type,
            u, v, center_x, center_y
        )
        
        print("[ARM] Executing sequence...")
        
        # Execute each step
        step_names = ["Home", "Reach", "Grip", "Lift", "Rotate", 
                     "Position", "Release", "Retract", "Home"]
        
        for idx, step in enumerate(dynamic_sequence):
            step_name = step_names[idx] if idx < len(step_names) else f"Step {idx}"
            print(f"[ARM] → {step_name}: {step}")
            
            arm.setPosition(
                [[i+1, pos] for i, pos in enumerate(step)],
                2000
            )
            sleep(1)
        
        sleep(2)
        print("[ARM] ✓ Sequence complete!")
        
    except Exception as e:
        print(f"[ERROR] Arm control failed: {e}")
    finally:
        try:
            arm.servoOff()
        except:
            pass
        
        # Restart conveyor after pick sequence
        if conveyor and conveyor.is_initialized:
            print("[ARM] Restarting conveyor...")
            conveyor.start()


# ============================================================================
# TRIGGER LOGIC
# ============================================================================

_last_fire_ts = 0.0

def maybe_trigger_arm(label, u, v, conf, bbox_coords, frame,
                     cooldown_s, use_angle_detection, angle_detector, arm, conveyor):
    """
    Trigger arm action with cooldown protection and rotation logic.
    - Bottles: angle detection (if enabled)
    - Other objects: fixed rotation 130
    - All objects: position fine-tuning
    
    Args:
        label: Object label
        u, v: Center coordinates
        conf: Detection confidence
        bbox_coords: (x1, y1, x2, y2) bounding box
        frame: Current camera frame
        cooldown_s: Cooldown time in seconds
        use_angle_detection: Whether to use angle-aware picking for bottles
        angle_detector: ObjectAngleDetector instance
        arm: xArm controller
        conveyor: ConveyorController instance
    """
    global _last_fire_ts
    now = time.time()
    
    if now - _last_fire_ts < cooldown_s:
        return
    
    _last_fire_ts = now
    
    try:
        label_lower = label.lower()
        
        # Calculate camera center
        center_x = frame.shape[1] // 2
        center_y = frame.shape[0] // 2
        
        # Detect angle for all objects (but only use it for bottles)
        if angle_detector:
            x1, y1, x2, y2 = bbox_coords
            object_angle = angle_detector.detect_angle(frame, x1, y1, x2, y2, label)
        else:
            object_angle = 0.0
        
        # Always use the handler with rotation and fine-tuning
        handle_arm_action_with_rotation(
            label, u, v, conf, object_angle,
            center_x, center_y, arm, conveyor
        )
        
        print(f"[INFO] Triggered arm action for {label}")
        
    except Exception as e:
        print(f"[WARN] Failed to trigger arm action: {e}")


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
    ap.add_argument('--classes', type=str, default='plastic_bottle,glass_bottle,cup')
    ap.add_argument('--cooldown', type=float, default=2.0)
    ap.add_argument('--stable_n', type=int, default=5)
    ap.add_argument('--roi_x', type=float, default=0.15)
    ap.add_argument('--roi_y', type=float, default=0.15)
    ap.add_argument('--skip_frames', type=int, default=0)
    ap.add_argument('--inference_size', type=int, default=640)
    
    # Angle detection options
    ap.add_argument('--use_angle', action='store_true',
                    help='Enable angle-aware gripper rotation for bottles')
    ap.add_argument('--debug_angle', action='store_true',
                    help='Show angle detection debug windows')
    ap.add_argument('--show_angle', action='store_true',
                    help='Display detected angle on frame')
    
    # Conveyor control options
    ap.add_argument('--conveyor_ip', type=str, default=CONVEYOR_PLUG_IP,
                    help=f'IP address of Kasa smart plug (default: {CONVEYOR_PLUG_IP})')

    return ap.parse_args()


# ============================================================================
# MODEL LOADING
# ============================================================================

def load_model(conf):
    """
    Load Roboflow RF-DETR model via the `inference` SDK.
    """
    if not ROBOFLOW_API_KEY:
        raise RuntimeError(
            "ROBOFLOW_API_KEY not set! Set environment variable or fill ROBOFLOW_API_KEY."
        )

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
    
    # Print categorization info
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
        print(f"[INFO] Horizontal: Servo {FINE_TUNE_HORIZONTAL_SERVO} (Base), Factor: {FINE_TUNE_HORIZONTAL_FACTOR}, Max: ±{FINE_TUNE_HORIZONTAL_MAX}")
        print(f"[INFO] Vertical: Servo {FINE_TUNE_VERTICAL_SERVO}, Factor: {FINE_TUNE_VERTICAL_FACTOR}, Max: ±{FINE_TUNE_VERTICAL_MAX}")
        print(f"[INFO] Deadzone: X=±{FINE_TUNE_DEADZONE_X}px, Y=±{FINE_TUNE_DEADZONE_Y}px")
        print(f"[INFO] Affected steps: {FINE_TUNE_AFFECTED_STEPS}")
    else:
        print(f"[INFO] ✗ DISABLED")
    print(f"[INFO] ===================================\n")
    
    # Initialize angle detector if requested
    angle_detector = None
    if args.use_angle:
        angle_detector = ObjectAngleDetector(debug=args.debug_angle)
        print(f"[INFO] ✓ Angle detection ENABLED (for bottles only)")
        print(f"[INFO] Gripper rotation servo: ID{GRIP_ROT_SERVO_ID}")
        print(f"[INFO] Rotation range: {GRIP_ROT_MIN} to {GRIP_ROT_MAX} (neutral: {GRIP_ROT_NEUTRAL})")
        print(f"[INFO] Fixed rotation for non-bottles: {GRIP_ROT_FIXED}")
        print(f"[INFO] Angle threshold: [{ANGLE_ADJUST_MIN}°, {ANGLE_ADJUST_MAX}°]")
        print(f"[INFO] Affected steps: {ROTATION_AFFECTED_STEPS}")
    else:
        print(f"[INFO] Using FIXED sequences")
        print(f"[INFO] Non-bottles use fixed rotation: {GRIP_ROT_FIXED}")
    
    # Initialize arm
    arm = None
    if XARM_AVAILABLE:
        try:
            arm = xarm.Controller('USB')
            print("[INFO] ✓ Connected to xArm")
        except Exception as e:
            print(f"[WARN] Could not connect to xArm: {e}")
    
    # Initialize conveyor controller (ALWAYS TRY)
    conveyor = None
    if KASA_AVAILABLE:
        try:
            conveyor = ConveyorController(args.conveyor_ip)
            if conveyor.is_initialized:
                print("[INFO] ✓ Conveyor control ENABLED")
                print(f"[INFO] Plug IP: {args.conveyor_ip}")
                # Ensure conveyor is running at start
                conveyor.start()
            else:
                print("[WARN] Conveyor initialization failed")
                conveyor = None
        except Exception as e:
            print(f"[WARN] Could not initialize conveyor: {e}")
            conveyor = None
    else:
        print("[WARN] Kasa module not available. Install with: pip install python-kasa")
    
    # Window setup
    cv2.destroyAllWindows()
    WIN_NAME = f"YOLOv5_DualBox_{os.getpid()}"
    cv2.namedWindow(WIN_NAME, cv2.WINDOW_NORMAL)
    
    # Parameters
    ROI_MARGIN_X = float(max(0.0, min(1.0, args.roi_x)))
    ROI_MARGIN_Y = float(max(0.0, min(1.0, args.roi_y)))
    STABLE_N = int(max(1, args.stable_n))
    MIN_CONF = max(0.50, args.conf)
    
    # Load Roboflow model
    model = load_model(args.conf)
    print(f"[INFO] Detecting with Roboflow model: {ROBOFLOW_MODEL_ID}")
    
    # Open camera
    cap = cv2.VideoCapture(args.source, cv2.CAP_DSHOW if os.name == 'nt' else 0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    cap.set(cv2.CAP_PROP_FPS, args.fps)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    
    if not cap.isOpened():
        raise RuntimeError('Could not open camera.')
    
    # State variables
    t_prev = time.time()
    stable_count = 0
    last_label = None
    last_bbox = None
    frame_counter = 0
    last_det = []
    last_angle = 0.0
    
    print("[INFO] Starting detection loop. Press 'q' or ESC to quit.")
    
    # Main loop
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        
        H, W = frame.shape[:2]
        cx, cy = W // 2, H // 2
        rx = int(W * ROI_MARGIN_X / 2.0)
        ry = int(H * ROI_MARGIN_Y / 2.0)
        
        # Frame skipping
        frame_counter += 1
        should_detect = (frame_counter % (args.skip_frames + 1) == 0)
        
        if should_detect:
            t0 = time.time()
            # Roboflow inference: returns a list, take first result
            rf_result = model.infer(frame, confidence=args.conf)[0]
            infer_ms = (time.time() - t0) * 1000.0
            
            det = []
            # rf_result.predictions is a list of ObjectDetectionPrediction
            for p in rf_result.predictions:
                # Convert center-x, center-y, width, height --> x1, y1, x2, y2
                x1 = int(p.x - p.width / 2)
                y1 = int(p.y - p.height / 2)
                x2 = int(p.x + p.width / 2)
                y2 = int(p.y + p.height / 2)
                det.append((x1, y1, x2, y2, float(p.confidence), p.class_name))
            
            last_det = det
        else:
            det = last_det
            infer_ms = 0.0
        
        # Find best detection (SINGLE LOOP, PROPERLY INDENTED)
        best_hit = None
        for x1, y1, x2, y2, conf, label in det:
            # Determine color based on category
            category = get_sequence_type_for_label(label)
            label_lower = label.lower()
            
            if category == 'left':
                box_color = (0, 255, 0)  # Green for recyclable
                label_suffix = " [R]"
            else:
                box_color = (0, 165, 255)  # Orange for non-recyclable
                label_suffix = " [N]"
            
            # Add rotation indicator
            if label_lower in FIXED_ROTATION_OBJECTS:
                label_suffix += f" FIX:{GRIP_ROT_FIXED}"
            elif label_lower in ANGLE_DETECTION_OBJECTS:
                label_suffix += " ANG"
            
            # Draw box with category-specific color
            cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
            cv2.putText(frame, f"{label}{label_suffix} {conf:.2f}",
                        (x1, max(20, y1 - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, box_color, 2)
            
            # Pick best detection
            if best_hit is None or conf > best_hit["conf"]:
                u = (x1 + x2) // 2
                v = (y1 + y2) // 2
                best_hit = {
                    "label": label,
                    "conf": float(conf),
                    "u": u,
                    "v": v,
                    "bbox": (x1, y1, x2, y2)
                }
        
        # Draw ROI (AFTER THE LOOP)
        cv2.rectangle(frame, (cx - rx, cy - ry), (cx + rx, cy + ry), (255, 255, 0), 2)
        cv2.putText(frame, "CENTER ROI", (cx - rx, cy - ry - 8),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        
        # Draw center crosshair
        cv2.line(frame, (cx - 10, cy), (cx + 10, cy), (255, 255, 0), 1)
        cv2.line(frame, (cx, cy - 10), (cx, cy + 10), (255, 255, 0), 1)
        
        # Check if in ROI and stable
        in_roi = False
        if best_hit is not None and best_hit["conf"] >= MIN_CONF:
            u, v = best_hit["u"], best_hit["v"]
            in_roi = (cx - rx) <= u <= (cx + rx) and (cy - ry) <= v <= (cy + ry)
            
            # Draw center marker
            cv2.circle(frame, (u, v), 5, (0, 255, 0), -1)
            
            # Draw offset line from center to object
            if ENABLE_FINE_TUNING:
                cv2.line(frame, (cx, cy), (u, v), (255, 0, 255), 2)
                offset_x = u - cx
                offset_y = v - cy
                cv2.putText(frame, f"Offset: ({offset_x:+d}, {offset_y:+d})",
                           (10, 150), cv2.FONT_HERSHEY_SIMPLEX, 
                           0.7, (255, 0, 255), 2)
            
            # Detect angle if enabled (for display purposes)
            if args.show_angle and angle_detector:
                x1, y1, x2, y2 = best_hit["bbox"]
                detected_angle = angle_detector.detect_angle(frame, x1, y1, x2, y2, best_hit["label"])
                last_angle = detected_angle
                
                cv2.putText(frame, f"Angle: {detected_angle:.1f}deg",
                           (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 
                           0.8, (0, 255, 255), 2)
                
                # Draw orientation line
                length = 50
                angle_rad = math.radians(detected_angle)
                dx = int(length * math.cos(angle_rad))
                dy = int(length * math.sin(angle_rad))
                cv2.line(frame, (u, v), (u + dx, v - dy), (0, 255, 255), 2)
        
        # Stability tracking
        if in_roi:
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
        
        # FPS calculation
        now = time.time()
        fps = 1.0 / max(1e-6, now - t_prev)
        t_prev = now
        
        # Display info
        cv2.putText(frame, f"{fps:4.1f} FPS | {infer_ms:5.1f} ms", 
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (50, 200, 50), 2)
        cv2.putText(frame, f"Stable: {stable_count}/{STABLE_N}", 
                   (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (50, 200, 50), 2)
        
        if args.use_angle:
            cv2.putText(frame, "ANGLE: Bottles only", (W - 250, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        # Show conveyor status
        if conveyor and conveyor.is_initialized:
            conv_state = conveyor.get_state()
            if conv_state is not None:
                status_text = "CONVEYOR: ON" if conv_state else "CONVEYOR: OFF"
                status_color = (0, 255, 0) if conv_state else (0, 0, 255)
                cv2.putText(frame, status_text, (W - 220, 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
        
        # Show fine-tuning status
        if ENABLE_FINE_TUNING:
            cv2.putText(frame, "FINE-TUNE: ON", (W - 220, 90),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)
        
        # Show legend
        cv2.putText(frame, "Green[R] = Recyclable", (10, H - 90),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.putText(frame, "Orange[N] = Non-Recyclable", (10, H - 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
        cv2.putText(frame, f"FIX:{GRIP_ROT_FIXED} = Fixed Rotation | ANG = Angle-based", (10, H - 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # Trigger arm action
        if best_hit is not None and stable_count >= STABLE_N:
            maybe_trigger_arm(
                best_hit["label"],
                best_hit["u"],
                best_hit["v"],
                best_hit["conf"],
                best_hit["bbox"],
                frame,
                args.cooldown,
                args.use_angle,
                angle_detector,
                arm,
                conveyor
            )
            
            stable_count = 0
            last_label = None
            last_bbox = None
        
        cv2.imshow(WIN_NAME, frame)
        k = cv2.waitKey(1) & 0xFF
        if k in (27, ord('q')):
            break
    
    # Cleanup
    cap.release()
    cv2.destroyAllWindows()
    
    if arm:
        try:
            arm.servoOff()
        except:
            pass


if __name__ == "__main__":
    main()