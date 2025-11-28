# Camera-Guided Object Sorting Arm

A sophisticated robotic manipulation system that combines YOLOv5 object detection with dynamic gripper rotation and automated conveyor belt control for intelligent pick-and-place operations.

![System Status](https://img.shields.io/badge/status-active-brightgreen)
![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

##  Overview

This system integrates computer vision, robotic control, and automation to create an intelligent sorting system capable of:

- **Real-time object detection** using YOLOv5/Roboflow models
- **Angle-aware gripper rotation** that adapts to object orientation
- **Dual-box sorting** (recyclable vs. non-recyclable items)
- **Automated conveyor control** via smart plug integration
- **Position fine-tuning** for precise object pickup
- **ROI-priority selection** for optimal target acquisition
- **State machine coordination** for reliable operation

##  Key Features

###  Angle-Aware Gripper Rotation
Automatically detects object orientation and adjusts gripper rotation angle for optimal pickup of bottles and cylindrical objects.

###  ROI-Based Targeting
Configurable region of interest ensures the system prioritizes objects in the optimal pickup zone, improving reliability and success rate.

###  Dual-Box Sorting
Intelligently categorizes and sorts objects into two boxes:
- **Left Box**: Recyclable items (plastic bottles, glass bottles, metal cans)
- **Right Box**: Non-recyclable items (paper cups, chip bags)

### Automated Conveyor Control
Smart plug integration automatically stops the conveyor during picking operations and restarts it afterward, eliminating manual intervention.

###  Position Fine-Tuning
Dynamic servo adjustments compensate for object position offsets from the ideal center point, improving pickup accuracy.

### State Machine Architecture
Robust state management (IDLE → PICKING → COOLDOWN → IDLE) prevents race conditions and ensures safe, coordinated operation.

### Stability Tracking
Requires multiple consecutive stable detections before triggering arm movement, reducing false positives and improving reliability.

##  System Architecture

```
Camera Feed → YOLOv5 Detection → Angle Detection → Gripper Rotation Calculation
                                                           ↓
                                                    Arm Controller
                                                           ↓
                                               [Conveyor Auto-Stop/Start]
```

### Component Flow

1. **Detection Phase**: Camera captures frame → YOLOv5 detects objects → ROI-priority selection
2. **Analysis Phase**: Object angle detection → Position offset calculation → Servo adjustment computation
3. **Execution Phase**: Conveyor stops → Arm executes pick sequence → Object sorted to appropriate box
4. **Reset Phase**: Arm returns home → Conveyor restarts → System returns to IDLE state

## 📋 Requirements

### Hardware
- **Robotic Arm**: xArm compatible robotic arm with 6+ servos
- **Camera**: USB camera (1920x1080 recommended)
- **Conveyor Belt**: Motorized conveyor with Kasa smart plug control
- **Computer**: System capable of running real-time object detection

### Software Dependencies

```bash
pip install -r requirements.txt
```

**Core Dependencies:**
- Python 3.9+
- OpenCV (cv2)
- NumPy
- Roboflow Inference SDK
- python-kasa (for smart plug control)
- xarm-python (for robotic arm control)

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/angle-aware-robotic-pick-and-place.git
cd angle-aware-robotic-pick-and-place

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Edit the configuration constants at the top of `main.py`:

```python
# Roboflow Model Configuration
ROBOFLOW_MODEL_ID = "your-model-id/version"
ROBOFLOW_API_KEY = "your-api-key"

# Conveyor Belt Configuration
CONVEYOR_PLUG_IP = "192.168.1.xxx"

# Object Categories
RECYCLABLE_ITEMS = ['plastic_bottle', 'glass_bottle', 'metal-can']
NON_RECYCLABLE_ITEMS = ['paper cup', 'chips_bag']
```

### 3. Basic 

```bash
# Run with default settings
python main.py

# Run with angle detection enabled
python main.py --use_angle

# Run with custom confidence threshold
python main.py --conf 0.5 --use_angle

# Run with angle visualization
python main.py --use_angle --show_angle
```

### 4. Advanced 

```bash
python main.py \
  --source 0 \              # Camera index
  --width 1920 \            # Frame width
  --height 1080 \           # Frame height
  --conf 0.40 \             # Confidence threshold
  --cooldown 2.0 \          # Cooldown between picks (seconds)
  --stable_n 2 \            # Stability frames required
  --roi_x 0.15 \            # ROI horizontal margin
  --roi_y 0.15 \            # ROI vertical margin
  --use_angle \             # Enable angle-aware rotation
  --show_angle \            # Display detected angles
  --conveyor_ip 192.168.1.100  # Smart plug IP address

### Gripper Rotation Settings

```python
# Servo Configuration
GRIP_ROT_SERVO_ID = 2          # Gripper rotation servo ID
GRIP_ROT_NEUTRAL = 500         # Neutral position (0°)
GRIP_ROT_MIN = 130             # Minimum rotation (-90°)
GRIP_ROT_MAX = 875             # Maximum rotation (+90°)
GRIP_ROT_FIXED = 130           # Fixed rotation for non-cylindrical objects
# Angle Adjustment Range
ANGLE_ADJUST_MIN = -35.0       # Minimum angle threshold
ANGLE_ADJUST_MAX = 35.0        # Maximum angle threshold
```
### Position Fine-Tuning Settings

```python
ENABLE_FINE_TUNING = True      # Enable/disable fine-tuning
FINE_TUNE_HORIZONTAL_SERVO = 6 # Servo for horizontal adjustment
FINE_TUNE_HORIZONTAL_FACTOR = 0.15  # Pixels to servo conversion
FINE_TUNE_HORIZONTAL_MAX = 100 # Maximum adjustment limit

FINE_TUNE_VERTICAL_SERVO = 3   # Servo for vertical adjustment
FINE_TUNE_VERTICAL_FACTOR = -0.10  # Pixels to servo conversion
FINE_TUNE_VERTICAL_MAX = 80    # Maximum adjustment limit

# Deadzone Configuration
FINE_TUNE_DEADZONE_X = 20      # Horizontal deadzone (pixels)
FINE_TUNE_DEADZONE_Y = 20      # Vertical deadzone (pixels)
```
### Object Categorization

```python
# Recyclable Objects (→ Left Box)
RECYCLABLE_ITEMS = ['plastic_bottle', 'glass_bottle', 'metal-can']

# Non-Recyclable Objects (→ Right Box)
NON_RECYCLABLE_ITEMS = ['paper cup', 'chips_bag']

# Angle Detection Objects
ANGLE_DETECTION_OBJECTS = ['plastic_bottle', 'glass_bottle']

# Fixed Rotation Objects
FIXED_ROTATION_OBJECTS = ['paper cup', 'chips_bag', 'metal-can']
```
### Arm Movement Sequences

Sequences are defined for left and right box sorting. Each sequence is a list of servo positions for 6 servos.

```python
BASE_ARM_SEQUENCE_LEFT = [
    [100, 500, 300, 900, 700, 500],  # Home position
    [100, 500, 150, 660, 310, 500],  # Reach
    # ... additional steps
]
```

### Contact
Jeff - [@Jeffaaay](https://github.com/Jeffaaay)

Project Link: [https://github.com/Jeffaaay/Angle-Aware-Robotic-Pick-and-Place-System](https://github.com/Jeffaaay/Angle-Aware-Robotic-Pick-and-Place-System)



---

**Note**: This system is designed for educational and research purposes. Ensure proper safety measures when operating robotic equipment.
