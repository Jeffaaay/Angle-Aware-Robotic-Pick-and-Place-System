# Hardware Configuration Guide

This guide provides detailed instructions for configuring the hardware components of the angle-aware pick-and-place system.

## Table of Contents
1. [xArm Robot Configuration](#xarm-robot-configuration)
2. [Camera Setup](#camera-setup)
3. [Conveyor Belt Setup](#conveyor-belt-setup)
4. [Servo Calibration](#servo-calibration)
5. [Workspace Layout](#workspace-layout)

---

## xArm Robot Configuration

### Servo Identification

The xArm uses 6 servos numbered 1-6:

```
Servo 1: Base rotation
Servo 2: Gripper rotation (default in this project)
Servo 3: Shoulder joint
Servo 4: Elbow joint
Servo 5: Wrist pitch
Servo 6: Gripper open/close
```

### Finding Your Gripper Rotation Servo

1. **Power on the xArm**
2. **Run the test script**:

```python
import xarm

arm = xarm.Controller('USB')

# Test each servo individually
for servo_id in range(1, 7):
    print(f"\nTesting Servo {servo_id}")
    arm.setPosition([[servo_id, 300]], 1000)
    input("Press Enter to move to 700...")
    arm.setPosition([[servo_id, 700]], 1000)
    input("Press Enter to continue...")
```

3. **Identify which servo rotates the gripper** (not opens/closes it)
4. **Update `GRIP_ROT_SERVO_ID`** in `detect5_angle_aware.py`

### Calibrating Servo Range

Once you've identified the gripper rotation servo:

```python
import xarm

arm = xarm.Controller('USB')
servo_id = 2  # Your gripper rotation servo

# Find minimum position (usually around 130-200)
for pos in range(130, 200, 10):
    arm.setPosition([[servo_id, pos]], 1000)
    response = input(f"Position {pos} - Continue? (y/n): ")
    if response.lower() == 'n':
        print(f"Minimum position: {pos}")
        break

# Find maximum position (usually around 800-900)
for pos in range(800, 920, 10):
    arm.setPosition([[servo_id, pos]], 1000)
    response = input(f"Position {pos} - Continue? (y/n): ")
    if response.lower() == 'n':
        print(f"Maximum position: {pos}")
        break

# Find neutral position (straight gripper, usually around 500)
# Adjust until gripper is perfectly horizontal
```

Update these values in `detect5_angle_aware.py`:
```python
GRIP_ROT_SERVO_ID = 2      # Your identified servo
GRIP_ROT_NEUTRAL = 500     # Neutral (0°) position
GRIP_ROT_MIN = 130         # Minimum rotation limit
GRIP_ROT_MAX = 875         # Maximum rotation limit
```

### Customizing the Arm Sequence

The pick-and-place sequence is defined in `BASE_ARM_SEQUENCE`. Each step is an array of 6 servo positions:

```python
BASE_ARM_SEQUENCE = [
    # [Servo1, Servo2, Servo3, Servo4, Servo5, Servo6]
    [250, 500, 300, 900, 700, 500],  # 0: Home position
    [250, 500, 150, 660, 330, 500],  # 1: Reach to object
    [600, 500, 150, 660, 330, 500],  # 2: Close gripper
    [600, 500, 150, 660, 450, 500],  # 3: Lift object
    [600, 500, 150, 660, 450, 865],  # 4: Rotate to drop zone
    [600, 500, 125, 800, 475, 865],  # 5: Position above drop
    [250, 500, 125, 800, 475, 865],  # 6: Open gripper (release)
    [250, 500, 125, 900, 700, 865],  # 7: Retract arm
    [250, 500, 300, 900, 700, 500]   # 8: Return home
]
```

**To customize for your workspace:**

1. **Move arm manually** to desired position
2. **Read current positions**: 
```python
positions = arm.getPosition()
print(positions)
```
3. **Record positions** for each step
4. **Test sequence** slowly with increased duration:
```python
arm.setPosition([[i+1, pos] for i, pos in enumerate(step)], 3000)
```
5. **Reduce duration** once sequence is verified safe

---

## Camera Setup

### Mounting Position

**Recommended setup:**
- Mount camera **above the workspace** looking down
- Distance: 30-50cm from conveyor surface
- Angle: Perpendicular to workspace (90°)
- Ensure good lighting (avoid shadows and glare)

### Camera Configuration

Find your camera index:
```bash
# Linux
ls /dev/video*

# Test different indices
python -c "import cv2; cap = cv2.VideoCapture(0); print('Camera 0:', cap.isOpened())"
python -c "import cv2; cap = cv2.VideoCapture(1); print('Camera 1:', cap.isOpened())"
```

Update camera parameters:
```bash
python detect5_angle_aware.py \
    --source 0 \           # Your camera index
    --width 1920 \         # Resolution
    --height 1080 \
    --fps 30
```

### Camera Calibration (Optional)

For better accuracy, you can calibrate the camera-to-arm coordinate transformation using the included `calibration.py` module.

---

## Conveyor Belt Setup

### Finding Your Smart Plug IP

**Method 1: Using Kasa App**
1. Open Kasa mobile app
2. Select your smart plug
3. Go to Settings → Device Info
4. Note the IP address

**Method 2: Network Scan**
```bash
# Linux/Mac
arp -a | grep kasa

# Or use nmap
nmap -sn 192.168.1.0/24
```

**Method 3: Python Script**
```python
import asyncio
from kasa import Discover

async def discover_devices():
    devices = await Discover.discover()
    for addr, dev in devices.items():
        await dev.update()
        print(f"Found: {dev.alias} at {addr}")

asyncio.run(discover_devices())
```

### Configuring Conveyor Control

Update in `detect5_angle_aware.py`:
```python
CONVEYOR_PLUG_IP = "10.0.0.94"  # Your smart plug IP
```

Enable conveyor control:
```bash
python detect5_angle_aware.py \
    --use_conveyor \
    --conveyor_ip 10.0.0.94
```

### Testing Conveyor

Test smart plug control:
```python
import asyncio
from kasa import SmartPlug

async def test_plug():
    plug = SmartPlug("10.0.0.94")
    await plug.update()
    print(f"Current state: {'ON' if plug.is_on else 'OFF'}")
    
    # Turn on
    await plug.turn_on()
    print("Turned ON")
    await asyncio.sleep(2)
    
    # Turn off
    await plug.turn_off()
    print("Turned OFF")

asyncio.run(test_plug())
```

---

## Servo Calibration

### Understanding Servo Values

- **Servo range**: Typically 0-1000 (varies by model)
- **Safe range**: Usually 130-875 to avoid mechanical limits
- **Neutral position**: Middle of range, often around 500

### Calibration Procedure

1. **Start with neutral position**:
```python
arm.setPosition([[servo_id, 500]], 2000)
```

2. **Test range limits** (do this slowly!):
```python
# Test minimum
for val in range(500, 100, -10):
    arm.setPosition([[servo_id, val]], 1000)
    input(f"Position {val} - Safe? ")
    
# Test maximum  
for val in range(500, 1000, 10):
    arm.setPosition([[servo_id, val]], 1000)
    input(f"Position {val} - Safe? ")
```

3. **Record safe limits**

4. **Map to angles**:
```python
# -90° should map to minimum safe position
# 0° should map to neutral position
# +90° should map to maximum safe position
```

---

## Workspace Layout

### Recommended Setup

```
                    Camera
                       |
                       v
    ┌──────────────────────────────────┐
    │                                  │
    │         Work Area (ROI)          │
    │                                  │
    │    [Conveyor Belt Direction →]  │
    │                                  │
    └──────────────────────────────────┘
            ↑
         xArm Base
```

### ROI (Region of Interest) Configuration

The ROI defines where objects must be positioned to trigger picking.

```python
# ROI as percentage of frame
--roi_x 0.15  # 15% margin on left/right (30% total width)
--roi_y 0.15  # 15% margin on top/bottom (30% total height)
```

**Smaller ROI** = More precise positioning required  
**Larger ROI** = More forgiving, but may trigger on unwanted objects

### Lighting Recommendations

- **Use diffuse lighting** to minimize shadows
- **Avoid backlighting** (don't place bright lights behind objects)
- **LED panels** work well for consistent illumination
- **Avoid flickering** (use DC-powered LEDs or high-frequency AC)

---

## Testing Your Setup

### Step-by-Step Verification

1. **Test camera**:
```bash
python detect5_angle_aware.py --source 0
# Verify you can see the camera feed
# Press 'q' to exit
```

2. **Test detection**:
```bash
python detect5_angle_aware.py --source 0 --classes "bottle"
# Place a bottle in view
# Verify it's detected and labeled
```

3. **Test angle detection**:
```bash
python detect5_angle_aware.py --source 0 --use_angle --show_angle --debug_angle
# Rotate the object
# Verify angle display updates
```

4. **Test arm (dry run)**:
```bash
# Disconnect arm or use simulation mode
# Verify logic without arm movement
```

5. **Test arm (real)**:
```bash
python detect5_angle_aware.py --source 0 --use_angle
# Start with high --cooldown value (e.g., 10.0)
# Monitor first pick carefully
```

6. **Test conveyor**:
```bash
python detect5_angle_aware.py --source 0 --use_conveyor
# Verify conveyor stops/starts during pick
```

7. **Full integration**:
```bash
python detect5_angle_aware.py \
    --source 0 \
    --use_angle \
    --use_conveyor \
    --show_angle \
    --classes "bottle,cup" \
    --cooldown 5.0
```

---

## Safety Checklist

Before running the full system:

- [ ] Workspace is clear of obstacles
- [ ] Emergency stop is accessible
- [ ] Arm movement range is verified safe
- [ ] Servo limits are properly set
- [ ] Camera has clear view of work area
- [ ] Lighting is adequate and consistent
- [ ] Conveyor belt is properly secured
- [ ] All cables are secured and won't interfere
- [ ] You've tested each component individually
- [ ] Initial runs use high cooldown values

---

## Troubleshooting

### Arm moves too fast
- Increase duration in `setPosition()` calls
- Default is 2000ms, try 3000-4000ms

### Gripper rotation is backwards
- Swap `GRIP_ROT_MIN` and `GRIP_ROT_MAX` values

### Objects not detected in ROI
- Use `--show_angle` to visualize ROI
- Adjust camera position or ROI parameters
- Check lighting conditions

### Conveyor doesn't stop
- Verify IP address is correct
- Check network connectivity
- Test smart plug independently

---

## Next Steps

Once basic setup is complete:
1. Fine-tune detection thresholds (`--conf`)
2. Optimize ROI size for your workspace
3. Adjust angle thresholds for your objects
4. Test with various object types
5. Optimize movement speed vs. accuracy

For questions or issues, open an issue on GitHub!
