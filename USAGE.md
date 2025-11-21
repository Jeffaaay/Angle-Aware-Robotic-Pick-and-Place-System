# Usage Guide

Comprehensive guide for operating the Angle-Aware Robotic Pick-and-Place System.

## Table of Contents

1. [Basic Operation](#basic-operation)
2. [Command Line Options](#command-line-options)
3. [Operating Modes](#operating-modes)
4. [Visual Feedback](#visual-feedback)
5. [Best Practices](#best-practices)
6. [Performance Tuning](#performance-tuning)
7. [Safety Guidelines](#safety-guidelines)

## Basic Operation

### Starting the System

**Minimal command:**
```bash
python main.py
```

**Recommended for production:**
```bash
python main.py --use_angle --conf 0.40 --stable_n 2 --cooldown 2.0
```

**With angle visualization:**
```bash
python main.py --use_angle --show_angle
```

### System Startup Sequence

1. **Initialization** (2-3 seconds)
   - Loads Roboflow model
   - Connects to camera
   - Initializes smart plug connection
   - Connects to robotic arm
   - Starts conveyor belt

2. **Detection Phase**
   - Camera feed displays
   - Objects are detected in real-time
   - ROI (Region of Interest) overlay visible

3. **Ready State**
   - System displays "STATE: IDLE"
   - Conveyor shows "ON"
   - System is ready to pick objects

### Normal Operation Flow

1. Place object on conveyor belt
2. Object enters camera field of view
3. System detects object and tracks for stability
4. When stable detection achieved:
   - Conveyor automatically stops
   - Arm executes pick sequence
   - Object is placed in appropriate box
   - Conveyor automatically restarts
5. System returns to IDLE state

### Stopping the System

- Press `q` or `ESC` key to exit
- System will:
  - Complete any ongoing pick operation
  - Stop conveyor belt
  - Turn off arm servos
  - Close camera connection
  - Clean up resources

## Command Line Options

### Camera Configuration

```bash
--source 0                    # Camera index (default: 0)
--width 1920                  # Frame width (default: 1920)
--height 1080                 # Frame height (default: 1080)
--fps 30                      # Target frame rate (default: 30)
```

**Example:**
```bash
python main.py --source 1 --width 1280 --height 720 --fps 30
```

### Detection Parameters

```bash
--conf 0.40                   # Confidence threshold (default: 0.40)
--classes "bottle,cup,can"    # Object classes to detect
--stable_n 2                  # Stability frames required (default: 2)
--inference_size 640          # Inference resolution (default: 640)
```

**Example:**
```bash
python main.py --conf 0.35 --stable_n 3
```

### ROI Configuration

```bash
--roi_x 0.15                  # Horizontal ROI margin (0.0-1.0, default: 0.15)
--roi_y 0.15                  # Vertical ROI margin (0.0-1.0, default: 0.15)
```

**Example:**
```bash
# Larger ROI (30% margins)
python main.py --roi_x 0.30 --roi_y 0.30

# Smaller ROI (10% margins)
python main.py --roi_x 0.10 --roi_y 0.10
```

### Timing Parameters

```bash
--cooldown 2.0                # Cooldown between picks (seconds, default: 2.0)
--skip_frames 0               # Frames to skip between detections (default: 0)
```

**Example:**
```bash
# Faster operation with shorter cooldown
python main.py --cooldown 1.5

# Better performance by skipping frames
python main.py --skip_frames 2
```

### Feature Flags

```bash
--use_angle                   # Enable angle-aware gripper rotation
--show_angle                  # Display detected angles on frame
--debug_angle                 # Show angle detection debug windows
```

**Example:**
```bash
# Full angle detection with visualization
python main.py --use_angle --show_angle --debug_angle
```

### Network Configuration

```bash
--conveyor_ip "192.168.1.100"  # Smart plug IP address
```

**Example:**
```bash
python main.py --conveyor_ip "192.168.1.242"
```

## Operating Modes

### Mode 1: Standard Operation (No Angle Detection)

```bash
python main.py
```

**Behavior:**
- All objects use fixed gripper rotation
- Paper cups and chip bags: Fixed rotation (130)
- Bottles and cans: Neutral rotation (500)
- Fastest operation
- Most reliable for simple objects

**Use when:**
- Objects don't require specific orientation
- Maximum speed is priority
- Testing basic functionality

### Mode 2: Angle-Aware Operation (Bottles Only)

```bash
python main.py --use_angle
```

**Behavior:**
- Bottles: Gripper rotation adapts to object angle
- Non-bottles: Fixed rotation as in Mode 1
- Slightly slower due to angle calculation
- Better pickup success for cylindrical objects

**Use when:**
- Working with bottles or cylindrical objects
- Object orientation varies significantly
- Pickup accuracy is priority

### Mode 3: Full Visualization Mode

```bash
python main.py --use_angle --show_angle --debug_angle
```

**Behavior:**
- Shows detected angles on main feed
- Opens debug windows for angle detection
- Displays angle calculation process
- Slowest operation

**Use when:**
- Debugging angle detection
- Calibrating system
- Training or demonstration
- Not recommended for production

### Mode 4: High-Performance Mode

```bash
python main.py --skip_frames 3 --inference_size 416 --stable_n 1
```

**Behavior:**
- Skips frames for faster processing
- Lower inference resolution
- Less strict stability requirements
- Maximum throughput

**Use when:**
- System resources are limited
- Speed is critical
- Objects are simple and consistent
- Accuracy requirements are relaxed

## Visual Feedback

### On-Screen Indicators

#### Top-Left Corner (System Stats)
```
24.3 FPS | 42.1 ms      # Frame rate and inference time
Stable: 2/2             # Stability counter
Mode: ROI-PRIORITY      # Detection mode
```

#### Top-Right Corner (System Status)
```
ANGLE: Bottles only     # Angle detection status
CONVEYOR: ON            # Conveyor state
FINE-TUNE: ON           # Position fine-tuning status
STATE: IDLE             # System state machine
```

#### Bottom (Legend)
```
Green[R] = Recyclable | Orange[N] = Non-Recyclable
✓ROI = In ROI | ★BEST = Selected Target
```

### Detection Box Colors

| Color | Meaning | Box Type |
|-------|---------|----------|
| 🟢 Green | Recyclable item | Left box |
| 🟠 Orange | Non-recyclable item | Right box |

### Detection Labels

```
plastic_bottle [R] ANG ✓ROI ★BEST 0.92
│              │   │   │    │      └─ Confidence
│              │   │   │    └─ Best detection
│              │   │   └─ In ROI
│              │   └─ Angle-aware rotation
│              └─ Recyclable
└─ Object class
```

Label suffixes:
- `[R]` - Recyclable (→ left box)
- `[N]` - Non-recyclable (→ right box)
- `FIX:130` - Fixed rotation value
- `ANG` - Angle-aware rotation enabled
- `✓ROI` - Object is inside ROI
- `★BEST` - Selected as best target

### Visual Overlays

1. **Yellow ROI Box**: Region of interest for prioritized detection
2. **Yellow Crosshair**: Frame center point
3. **Magenta Line**: Offset from center to target (when fine-tuning enabled)
4. **Yellow Angle Line**: Detected object orientation (when --show_angle enabled)

### State Machine Visual Feedback

| State | Color | Meaning |
|-------|-------|---------|
| IDLE | 🟢 Green | Ready for next object |
| PICKING | 🔴 Red | Currently executing pick sequence |
| COOLDOWN | 🟠 Orange | Post-pick recovery period |

## Best Practices

### Optimal Object Placement

1. **Spacing**: Place objects 15-20cm apart on conveyor
2. **Orientation**: No specific requirement (system handles all angles)
3. **Position**: Try to place objects near center of belt
4. **Speed**: Conveyor speed should allow 2-3 seconds in camera view

### Lighting Conditions

- **Brightness**: 600-1000 lux recommended
- **Type**: Diffuse lighting preferred (avoid harsh shadows)
- **Consistency**: Avoid flickering lights
- **Direction**: Top-down or side lighting (avoid backlighting)

### System Warm-up

Allow 10-15 seconds after startup for:
- Camera auto-exposure to stabilize
- System to initialize fully
- First few detections to calibrate

### Maintenance Schedule

**Daily:**
- Check camera lens for dirt/smudges
- Verify conveyor belt alignment
- Test emergency stop functionality

**Weekly:**
- Clean gripper mechanism
- Check servo connections
- Verify smart plug connectivity
- Review system logs for errors

**Monthly:**
- Recalibrate camera position if needed
- Check servo calibration
- Update Roboflow model if accuracy declines
- Verify all configuration parameters

## Performance Tuning

### For Maximum Accuracy

```bash
python main.py \
  --use_angle \
  --conf 0.50 \
  --stable_n 3 \
  --roi_x 0.10 \
  --roi_y 0.10 \
  --skip_frames 0 \
  --cooldown 3.0
```

**Settings:**
- Higher confidence threshold reduces false positives
- More stability frames ensure solid lock
- Smaller ROI increases precision
- No frame skipping for all detections
- Longer cooldown ensures complete cycle

### For Maximum Speed

```bash
python main.py \
  --conf 0.35 \
  --stable_n 1 \
  --roi_x 0.20 \
  --roi_y 0.20 \
  --skip_frames 2 \
  --cooldown 1.5 \
  --inference_size 416
```

**Settings:**
- Lower confidence accepts more detections
- Single frame stability for instant trigger
- Larger ROI for easier acquisition
- Frame skipping reduces processing load
- Shorter cooldown for faster cycles
- Smaller inference size for speed

### For Difficult Objects

```bash
python main.py \
  --use_angle \
  --show_angle \
  --conf 0.30 \
  --stable_n 4 \
  --roi_x 0.25 \
  --roi_y 0.25
```

**Settings:**
- Angle detection for optimal grip
- Visual feedback for debugging
- Lower confidence to catch edge cases
- More stability frames to filter noise
- Larger ROI for easier detection

## Safety Guidelines

### Before Operation

✅ **Do:**
- Verify emergency stop is functional
- Check arm workspace is clear
- Ensure boxes are properly positioned
- Test conveyor start/stop manually
- Verify camera view is unobstructed

❌ **Don't:**
- Operate with loose clothing near moving parts
- Place hands in arm workspace during operation
- Block camera view
- Modify code without testing
- Override safety cooldowns

### During Operation

✅ **Do:**
- Monitor system continuously
- Keep emergency stop accessible
- Watch for unusual behavior
- Stop system if errors occur
- Log any anomalies

❌ **Don't:**
- Reach into arm workspace
- Place oversized objects on conveyor
- Adjust hardware while system is running
- Ignore warning messages
- Force arm movements manually

### Emergency Procedures

**Emergency Stop:**
1. Press `q` or `ESC` immediately
2. Or use power switch on conveyor
3. System will safe-stop (complete pick if safe, then stop)

**System Freeze:**
1. Press `Ctrl+C` to force quit
2. Manually turn off conveyor
3. Power cycle robotic arm
4. Restart system

**Collision or Jam:**
1. Emergency stop system
2. Power off arm and conveyor
3. Clear obstruction
4. Inspect for damage
5. Test manually before restarting

## Troubleshooting During Operation

### Objects Not Being Picked

**Check:**
1. Objects are in ROI (yellow box)
2. Confidence is above threshold
3. Stability counter reaches target (e.g., 2/2)
4. System state is IDLE (not PICKING or COOLDOWN)
5. Conveyor is running

**Solutions:**
- Lower confidence: `--conf 0.30`
- Reduce stability: `--stable_n 1`
- Increase ROI: `--roi_x 0.25 --roi_y 0.25`
- Increase cooldown: `--cooldown 3.0`

### Inaccurate Pickups

**Check:**
1. Fine-tuning is enabled (`ENABLE_FINE_TUNING = True`)
2. Angle detection is working (if bottles)
3. Servo calibration is correct
4. Camera is properly mounted and focused

**Solutions:**
- Enable angle detection: `--use_angle`
- Adjust fine-tuning factors in configuration
- Recalibrate servos
- Improve lighting conditions

### System Running Slowly

**Check:**
1. FPS counter (should be >20 FPS)
2. Inference time (should be <100ms)
3. CPU/GPU usage

**Solutions:**
- Skip frames: `--skip_frames 2`
- Reduce resolution: `--width 1280 --height 720`
- Lower inference size: `--inference_size 416`
- Close other applications

## Advanced Usage

### Custom Object Categories

Edit configuration in `main.py`:

```python
# Define your categories
RECYCLABLE_ITEMS = ['plastic_bottle', 'glass_bottle', 'metal-can', 'cardboard']
NON_RECYCLABLE_ITEMS = ['paper cup', 'chips_bag', 'styrofoam']

# Specify which need angle detection
ANGLE_DETECTION_OBJECTS = ['plastic_bottle', 'glass_bottle']

# Specify which use fixed rotation
FIXED_ROTATION_OBJECTS = ['paper cup', 'chips_bag', 'metal-can']
```

### Multiple Camera Support

```bash
# Test different cameras
python main.py --source 0  # First camera
python main.py --source 1  # Second camera
```

### Logging and Monitoring

Redirect output to log file:
```bash
python main.py --use_angle 2>&1 | tee system_log.txt
```

### Batch Processing Mode

For testing without arm/conveyor:

```python
# In main.py, set:
XARM_AVAILABLE = False
KASA_AVAILABLE = False

# System will simulate picks without hardware
```

---

**Support:** For usage questions, check the [FAQ](FAQ.md) or open a discussion on GitHub.
