# Angle-Aware Robotic Pick-and-Place System

A sophisticated robotic manipulation system that combines YOLOv5 object detection with dynamic gripper rotation and automated conveyor belt control for intelligent pick-and-place operations.

## Features

- **Angle-Aware Gripper Rotation**: Automatically detects object orientation and adjusts gripper rotation angle for optimal pickup
- **YOLOv5 Object Detection**: Real-time object detection with customizable class filtering
- **Automated Conveyor Control**: Smart plug integration for automatic conveyor belt start/stop during pick operations
- **ROI-Based Targeting**: Configurable region of interest for precise object positioning
- **Stability Tracking**: Ensures stable detections before triggering arm movements
- **Dynamic Sequence Building**: Generates arm movement sequences adapted to object orientation

## System Architecture

```
Camera Feed → YOLOv5 Detection → Angle Detection → Gripper Rotation Calculation
                                                           ↓
                                                    Arm Controller
                                                           ↓
                                              [Conveyor Auto-Stop/Start]
```

## Hardware Requirements

- **Robot Arm**: xArm manipulator (6 servos)
- **Camera**: USB camera (1920x1080 recommended)
- **Conveyor Belt**: Optional, controlled via Kasa Smart Plug
- **Computer**: CUDA-capable GPU recommended for real-time performance

## Software Requirements

```bash
pip install torch torchvision
pip install opencv-python
pip install numpy
pip install python-kasa  # Optional, for conveyor control
```

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/angle-aware-pick-place.git
cd angle-aware-pick-place
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Download YOLOv5 weights (optional, will auto-download if not present):
```bash
# The script will automatically download yolov5s if yolov5s.pt is not found
# Or manually download:
wget https://github.com/ultralytics/yolov5/releases/download/v6.0/yolov5s.pt
```

## Configuration

### Gripper Rotation Settings

Edit the configuration constants in `detect5_angle_aware.py`:

```python
GRIP_ROT_SERVO_ID = 2        # Servo controlling gripper rotation (1-6)
GRIP_ROT_NEUTRAL = 500       # Neutral position (0° orientation)
GRIP_ROT_MIN = 130           # Minimum servo value (-90°)
GRIP_ROT_MAX = 875           # Maximum servo value (+90°)

# Angle adjustment thresholds
ANGLE_ADJUST_MIN = -35.0     # Only adjust if angle within this range
ANGLE_ADJUST_MAX = 35.0      # Outside this range, use neutral position

# Which steps in sequence get rotation applied
ROTATION_AFFECTED_STEPS = [1, 2, 3]  # Reach, Grip, Lift
```

### Conveyor Belt Settings

```python
CONVEYOR_PLUG_IP = "10.0.0.94"  # Change to your Kasa smart plug IP
```

### Arm Sequence

Modify `BASE_ARM_SEQUENCE` to match your robot's workspace:

```python
BASE_ARM_SEQUENCE = [
    [250, 500, 300, 900, 700, 500],  # Home position
    [250, 500, 150, 660, 330, 500],  # Reach position
    # ... customize for your setup
]
```

## Usage

### Basic Detection (No Angle Adjustment)

```bash
python detect5_angle_aware.py --source 0 --classes "bottle,cup,book"
```

### Angle-Aware Mode

```bash
python detect5_angle_aware.py \
    --source 0 \
    --use_angle \
    --show_angle \
    --classes "bottle,cup,book" \
    --conf 0.5
```

### With Conveyor Control

```bash
python detect5_angle_aware.py \
    --source 0 \
    --use_angle \
    --use_conveyor \
    --conveyor_ip 10.0.0.94 \
    --classes "bottle,cup,book"
```

### Debug Mode

```bash
python detect5_angle_aware.py \
    --source 0 \
    --use_angle \
    --debug_angle \
    --show_angle
```

## Command-Line Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--source` | int | 0 | Camera source index |
| `--width` | int | 1920 | Camera width |
| `--height` | int | 1080 | Camera height |
| `--fps` | int | 30 | Camera FPS |
| `--conf` | float | 0.40 | Detection confidence threshold |
| `--classes` | str | 'bottle,cup...' | Comma-separated class names to detect |
| `--cooldown` | float | 2.0 | Cooldown between pick actions (seconds) |
| `--stable_n` | int | 5 | Frames required for stable detection |
| `--roi_x` | float | 0.15 | ROI margin X (0-1) |
| `--roi_y` | float | 0.15 | ROI margin Y (0-1) |
| `--skip_frames` | int | 0 | Skip N frames between detections |
| `--inference_size` | int | 640 | YOLOv5 inference size |
| `--use_angle` | flag | False | Enable angle-aware gripper rotation |
| `--debug_angle` | flag | False | Show angle detection debug windows |
| `--show_angle` | flag | False | Display detected angle on frame |
| `--use_conveyor` | flag | False | Enable conveyor belt control |
| `--conveyor_ip` | str | 10.0.0.94 | Kasa smart plug IP address |

## How It Works

### 1. Object Detection
- YOLOv5 detects objects in camera feed
- Filters detections by specified classes and confidence threshold
- Tracks object stability within ROI

### 2. Angle Detection
When `--use_angle` is enabled:
- Extracts bounding box region of detected object
- Applies adaptive thresholding and contour detection
- Calculates minimum area rectangle to determine orientation
- Returns angle in range [-90°, +90°]

### 3. Gripper Rotation Calculation
```python
# Example: Object at 20° → Gripper rotates to 20°
# Object at 60° → Gripper uses neutral (outside threshold)

if ANGLE_ADJUST_MIN <= angle <= ANGLE_ADJUST_MAX:
    servo_value = angle_to_servo(angle)
else:
    servo_value = GRIP_ROT_NEUTRAL
```

### 4. Dynamic Sequence Generation
- Copies base arm sequence
- Modifies specified steps with calculated rotation value
- Applies rotation to reach, grip, and lift steps

### 5. Conveyor Control
- **Before Pick**: Stops conveyor belt
- **During Pick**: Executes arm sequence
- **After Pick**: Restarts conveyor belt

## Angle Detection Methods

The system provides two angle detection algorithms:

### 1. Minimum Area Rectangle (Default)
- Fast and robust
- Best for rectangular/elongated objects
- Uses OpenCV's `minAreaRect()`

### 2. Image Moments (Alternative)
- Better for irregular shapes
- More computationally intensive
- Available via `detect_angle_from_moments()`

## Troubleshooting

### Camera Not Opening
```bash
# Linux: Check camera permissions
sudo usermod -a -G video $USER

# Test camera
python -c "import cv2; cap = cv2.VideoCapture(0); print(cap.isOpened())"
```

### xArm Not Connecting
- Ensure USB cable is properly connected
- Check device permissions (Linux)
- Verify xArm SDK is installed correctly

### Conveyor Not Responding
- Verify Kasa smart plug IP address
- Check network connectivity
- Ensure python-kasa is installed
```bash
pip install python-kasa
```

### Poor Angle Detection
- Improve lighting conditions
- Adjust `ANGLE_ADJUST_MIN` and `ANGLE_ADJUST_MAX` thresholds
- Use `--debug_angle` to visualize detection

## Performance Optimization

- **GPU Acceleration**: Automatically used if CUDA available
- **Frame Skipping**: Use `--skip_frames` to reduce CPU load
- **Inference Size**: Reduce `--inference_size` for faster detection (trade-off: accuracy)
- **ROI Size**: Smaller ROI = faster processing

## Project Structure

```
angle-aware-pick-place/
├── detect5_angle_aware.py    # Main detection and control script
├── calibration.py            # Camera-arm calibration system (optional)
├── requirements.txt          # Python dependencies
├── README.md                # This file
└── yolov5s.pt               # YOLOv5 weights (auto-downloaded)
```

## Safety Considerations

⚠️ **Important Safety Notes:**

- Always test arm movements in a safe environment
- Ensure emergency stop is accessible
- Start with dry runs (no arm connected) to verify logic
- Use appropriate force limits on robot arm
- Keep workspace clear of obstacles
- Monitor first runs closely

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Future Enhancements

- [ ] Multi-object tracking and prioritization
- [ ] 3D pose estimation integration
- [ ] Adaptive gripper force control
- [ ] Machine learning-based angle refinement
- [ ] Web-based monitoring dashboard
- [ ] Support for multiple arm types

## License

MIT License - See LICENSE file for details

## Acknowledgments

- YOLOv5 by Ultralytics
- xArm SDK
- python-kasa library
- OpenCV community

## Contact

For questions or issues, please open an issue on GitHub.

---

**Status**: Production-ready with active development

**Version**: 1.0.0

**Last Updated**: November 2025
