# Installation Guide

Complete setup instructions for the Angle-Aware Robotic Pick-and-Place System.

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Hardware Setup](#hardware-setup)
3. [Software Installation](#software-installation)
4. [Configuration](#configuration)
5. [Verification](#verification)
6. [Troubleshooting](#troubleshooting)

## System Requirements

### Operating System
- **Recommended**: Ubuntu 20.04+ or Windows 10/11
- **Alternative**: macOS 11+ (with limitations on some hardware interfaces)

### Hardware Requirements
- **CPU**: Intel i5 or equivalent (i7+ recommended for real-time processing)
- **RAM**: 8GB minimum (16GB recommended)
- **GPU**: Optional but recommended (CUDA-compatible for faster inference)
- **Storage**: 10GB free space
- **USB Ports**: 2+ available (camera + robotic arm)
- **Network**: Ethernet or WiFi for smart plug communication

### Python Version
- **Required**: Python 3.9 or higher
- **Recommended**: Python 3.9 - 3.11

## Hardware Setup

### 1. Robotic Arm

**xArm Configuration:**

1. Connect xArm to computer via USB
2. Verify servo connections (6 servos required)
3. Test servo movements manually before running the system

**Servo Layout:**
- Servo 1: Base rotation
- Servo 2: Gripper rotation (critical for angle-aware operation)
- Servo 3: Vertical positioning
- Servo 4: Arm extension
- Servo 5: Gripper height
- Servo 6: Horizontal fine-tuning

### 2. Camera Setup

1. Connect USB camera to computer
2. Position camera above the conveyor belt
3. Recommended height: 60-100cm above objects
4. Ensure adequate lighting (600+ lux recommended)

**Camera Settings:**
- Resolution: 1920x1080 (Full HD)
- Frame rate: 30 FPS
- Format: MJPEG (for better performance)

### 3. Conveyor Belt

1. Connect conveyor motor to Kasa smart plug
2. Plug smart plug into power outlet
3. Configure smart plug using Kasa app:
   - Connect to WiFi network
   - Note the IP address (needed for configuration)
   - Test on/off functionality

### 4. Sorting Boxes

Position two boxes at the end of the arm's reach:
- **Left Box**: For recyclable items
- **Right Box**: For non-recyclable items

Recommended box specifications:
- Size: 30x30x40cm minimum
- Material: Rigid plastic or cardboard
- Position: 40-60cm from arm base

## Software Installation

### Step 1: Clone Repository

```bash
git clone https://github.com/Jeffaaay/Angle-Aware-Robotic-Pick-and-Place-System.git
cd Angle-Aware-Robotic-Pick-and-Place-System
```

### Step 2: Create Virtual Environment (Recommended)

**Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows:**
```cmd
python -m venv venv
venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Install System-Specific Dependencies

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install python3-opencv
sudo apt-get install libusb-1.0-0-dev
```

**Windows:**
- Install Visual C++ Redistributable
- Install USB drivers for xArm (if needed)

**macOS:**
```bash
brew install opencv
```

### Step 5: Verify Installations

```bash
# Test OpenCV
python -c "import cv2; print(cv2.__version__)"

# Test Roboflow
python -c "from inference import get_model; print('Roboflow OK')"

# Test xArm
python -c "import xarm; print('xArm OK')"

# Test Kasa
python -c "from kasa import SmartPlug; print('Kasa OK')"
```

## Configuration

### 1. Roboflow Setup

1. Create a Roboflow account at [roboflow.com](https://roboflow.com)
2. Train or upload your object detection model
3. Note your Model ID and API Key
4. Update in `main.py`:

```python
ROBOFLOW_MODEL_ID = "your-project/version"
ROBOFLOW_API_KEY = "your-api-key-here"
```

### 2. Smart Plug Configuration

1. Find your Kasa smart plug IP address:
   ```bash
   # Linux/macOS
   arp -a | grep kasa
   
   # Or use Kasa app to find IP
   ```

2. Update in `main.py`:
   ```python
   CONVEYOR_PLUG_IP = "192.168.1.XXX"
   ```

3. Test connection:
   ```bash
   python -c "from kasa import SmartPlug; import asyncio; asyncio.run(SmartPlug('192.168.1.XXX').update())"
   ```

### 3. Camera Configuration

1. Find your camera index:
   ```python
   python -c "import cv2; print([i for i in range(10) if cv2.VideoCapture(i).isOpened()])"
   ```

2. Update camera source in command line or `main.py`:
   ```bash
   python main.py --source 0  # Use detected index
   ```

### 4. Servo Calibration

Create a calibration script to test servo ranges:

```python
import xarm
arm = xarm.Controller('USB')

# Test each servo individually
for servo_id in range(1, 7):
    print(f"Testing servo {servo_id}")
    arm.setPosition([[servo_id, 500]], 1000)  # Neutral
    time.sleep(1)
    arm.setPosition([[servo_id, 300]], 1000)  # Min
    time.sleep(1)
    arm.setPosition([[servo_id, 700]], 1000)  # Max
    time.sleep(1)

arm.servoOff()
```

Adjust ranges in `main.py` based on your findings.

### 5. Object Categories

Update object categories based on your detection model:

```python
RECYCLABLE_ITEMS = ['plastic_bottle', 'glass_bottle', 'metal-can']
NON_RECYCLABLE_ITEMS = ['paper cup', 'chips_bag']
```

## Verification

### Test 1: Camera Feed

```bash
python main.py --source 0
```

Expected output:
- Live camera feed window
- FPS counter visible
- No detection boxes (no objects yet)

### Test 2: Object Detection

Place a test object in view:

```bash
python main.py --source 0 --conf 0.3
```

Expected output:
- Detection boxes around objects
- Confidence scores displayed
- Object labels visible

### Test 3: Conveyor Control

```bash
python test_conveyor.py  # See below for script
```

Test script:
```python
from kasa import SmartPlug
import asyncio

async def test():
    plug = SmartPlug("YOUR_IP_HERE")
    await plug.update()
    print(f"Current state: {plug.is_on}")
    
    print("Turning ON...")
    await plug.turn_on()
    await asyncio.sleep(2)
    
    print("Turning OFF...")
    await plug.turn_off()

asyncio.run(test())
```

### Test 4: Arm Movement

```bash
python test_arm.py  # See below for script
```

Test script:
```python
import xarm
from time import sleep

arm = xarm.Controller('USB')

# Home position
arm.setPosition([[i+1, pos] for i, pos in enumerate([250, 500, 300, 900, 700, 500])], 2000)
sleep(2)

# Test position
arm.setPosition([[i+1, pos] for i, pos in enumerate([250, 500, 150, 660, 310, 500])], 2000)
sleep(2)

# Return home
arm.setPosition([[i+1, pos] for i, pos in enumerate([250, 500, 300, 900, 700, 500])], 2000)
sleep(2)

arm.servoOff()
print("Test complete!")
```

### Test 5: Full System

```bash
python main.py --use_angle --show_angle
```

Place objects one at a time and verify:
- Detection is stable
- Angle is detected (for bottles)
- Arm picks up object
- Conveyor stops/starts
- Object is placed in correct box

## Troubleshooting

### Issue: "No module named 'inference'"

**Solution:**
```bash
pip install inference inference-sdk
```

### Issue: "Could not open camera"

**Solutions:**
1. Check camera is connected: `ls /dev/video*` (Linux)
2. Try different camera index: `python main.py --source 1`
3. Check permissions: `sudo usermod -a -G video $USER`

### Issue: "xArm not found"

**Solutions:**
1. Check USB connection
2. Install xArm library: `pip install xarm-python`
3. Check USB permissions (Linux): `sudo chmod 666 /dev/ttyUSB0`

### Issue: "Kasa smart plug connection failed"

**Solutions:**
1. Verify IP address: `ping YOUR_PLUG_IP`
2. Ensure plug and computer are on same network
3. Check firewall settings
4. Update plug firmware via Kasa app

### Issue: "Detection is slow"

**Solutions:**
1. Use frame skipping: `python main.py --skip_frames 2`
2. Reduce inference size: `python main.py --inference_size 416`
3. Consider GPU acceleration
4. Lower camera resolution: `python main.py --width 1280 --height 720`

### Issue: "Arm movements are inaccurate"

**Solutions:**
1. Calibrate servo ranges
2. Enable fine-tuning: Set `ENABLE_FINE_TUNING = True`
3. Adjust fine-tuning factors in configuration
4. Check for mechanical issues (loose servos, worn gears)

### Issue: "Event loop is closed" error

**Solution:**
This has been fixed in the latest version. Update to the latest code:
```bash
git pull origin main
```

## Next Steps

After successful installation:

1. Read [CONFIGURATION.md](CONFIGURATION.md) for detailed configuration options
2. Review [USAGE.md](USAGE.md) for operation guidelines
3. Check [CALIBRATION.md](CALIBRATION.md) for calibration procedures
4. See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for advanced issues

## Getting Help

If you encounter issues not covered here:

1. Check [Issues](https://github.com/Jeffaaay/Angle-Aware-Robotic-Pick-and-Place-System/issues) on GitHub
2. Review [Discussions](https://github.com/Jeffaaay/Angle-Aware-Robotic-Pick-and-Place-System/discussions)
3. Create a new issue with:
   - System information (OS, Python version)
   - Full error message
   - Steps to reproduce
   - Log output

---

**Installation Support:** For installation help, please open an issue with the `installation` label.
