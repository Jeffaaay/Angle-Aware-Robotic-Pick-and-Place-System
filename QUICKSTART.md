# Quick Start Guide

Get your angle-aware robotic pick-and-place system running in 5 minutes!

## Prerequisites

- Python 3.7 or higher
- USB camera
- xArm robot (optional for testing detection only)
- Kasa Smart Plug (optional for conveyor control)

## Installation

### 1. Clone and Install

```bash
git clone https://github.com/yourusername/angle-aware-pick-place.git
cd angle-aware-pick-place
pip install -r requirements.txt
```

### 2. Test Camera

```bash
python detect5_angle_aware.py --source 0
```

You should see a camera feed with a yellow ROI box. Press 'q' to exit.

## Basic Usage

### Detection Only (No Robot)

Perfect for testing the vision system:

```bash
python detect5_angle_aware.py \
    --source 0 \
    --classes "bottle,cup,book" \
    --conf 0.5
```

**What you'll see:**
- Green boxes around detected objects
- Yellow ROI (Region of Interest) in center
- FPS and inference time in top-left
- Stability counter (object must be stable before triggering)

### With Angle Detection

Enable angle-aware detection and visualization:

```bash
python detect5_angle_aware.py \
    --source 0 \
    --use_angle \
    --show_angle \
    --classes "bottle,cup"
```

**What you'll see:**
- Everything from above, plus:
- Yellow line showing object orientation
- Angle in degrees displayed on screen
- "ANGLE-AWARE" indicator in top-right

### Full System (Robot + Conveyor)

```bash
python detect5_angle_aware.py \
    --source 0 \
    --use_angle \
    --use_conveyor \
    --conveyor_ip 10.0.0.94 \
    --classes "bottle" \
    --cooldown 5.0
```

**Important:** Start with a high cooldown (5-10 seconds) for safety!

## Understanding the Display

```
┌─────────────────────────────────────────┐
│ 30.5 FPS | 45.2 ms        ANGLE-AWARE  │  ← Performance & Mode
│ Stable: 3/5                CONVEYOR: ON │  ← Stability & Conveyor Status
│                                          │
│              ┌───────────┐              │
│              │           │              │
│              │    ROI    │              │  ← Yellow = Region of Interest
│      [Object]           │              │  ← Green box = Detected object
│              │           │              │
│              └───────────┘              │
│                                          │
│ Angle: 25.3deg                          │  ← Object orientation
└─────────────────────────────────────────┘
```

## Common Workflows

### 1. Test Vision System

```bash
# Just detection, no robot
python detect5_angle_aware.py --source 0 --classes "bottle"
```

Place objects in the ROI. Green boxes should appear when detected.

### 2. Tune Detection

```bash
# Adjust confidence threshold
python detect5_angle_aware.py --source 0 --conf 0.6  # Higher = stricter

# Adjust ROI size
python detect5_angle_aware.py --source 0 --roi_x 0.2 --roi_y 0.2  # Larger ROI

# Detect specific objects
python detect5_angle_aware.py --source 0 --classes "bottle,cup,cell phone"
```

### 3. Debug Angle Detection

```bash
python detect5_angle_aware.py \
    --source 0 \
    --use_angle \
    --debug_angle \
    --show_angle
```

This opens extra windows showing the angle detection process.

### 4. Production Run

Once everything is tuned:

```bash
python detect5_angle_aware.py \
    --source 0 \
    --use_angle \
    --use_conveyor \
    --classes "bottle,cup" \
    --conf 0.55 \
    --cooldown 3.0 \
    --stable_n 5
```

## Key Parameters Explained

| Parameter | What It Does | Typical Values |
|-----------|-------------|----------------|
| `--conf` | Minimum confidence to accept detection | 0.4 - 0.7 |
| `--cooldown` | Seconds between pick actions | 2.0 - 10.0 |
| `--stable_n` | Frames object must be stable | 3 - 10 |
| `--roi_x/y` | ROI size (0-1, smaller = tighter) | 0.1 - 0.3 |

## Troubleshooting

### "Could not open camera"
```bash
# Try different camera indices
python detect5_angle_aware.py --source 1
python detect5_angle_aware.py --source 2
```

### Objects not detected
- Lower confidence: `--conf 0.3`
- Check lighting (avoid shadows)
- Verify object class is in `--classes`

### Robot doesn't move
- Check USB connection
- Verify xArm SDK is installed
- Check console for error messages

### Conveyor doesn't stop/start
- Verify smart plug IP: `--conveyor_ip YOUR_IP`
- Check network connection
- Test plug independently

### Angle detection seems wrong
- Use `--debug_angle` to visualize
- Improve lighting
- Ensure camera is perpendicular to workspace

## Next Steps

1. **Read the full README** for detailed explanations
2. **Configure hardware** following HARDWARE_SETUP.md
3. **Customize for your objects** by adjusting thresholds
4. **Fine-tune arm sequence** in the code
5. **Add more object classes** as needed

## Safety Reminders

⚠️ **Always:**
- Test without robot connected first
- Start with high cooldown values
- Keep emergency stop accessible
- Clear workspace of obstacles
- Monitor first runs closely

## Getting Help

- **Issues?** Open an issue on GitHub
- **Questions?** Check the full README and HARDWARE_SETUP guide
- **Customization?** See the code comments for detailed explanations

---

**Tip:** Start simple! Run detection-only first, then add angle detection, then add robot control, then add conveyor control. One step at a time ensures each component works before integration.

Happy picking! 🤖📦
