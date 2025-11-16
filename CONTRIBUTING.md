# Contributing to Angle-Aware Pick-and-Place

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on improving the project
- Help others learn and grow

## How to Contribute

### Reporting Bugs

Before submitting a bug report:
1. Check existing issues to avoid duplicates
2. Test with the latest version
3. Gather relevant information (OS, Python version, hardware setup)

**Good bug report includes:**
- Clear, descriptive title
- Steps to reproduce
- Expected vs actual behavior
- Screenshots/videos if applicable
- System information
- Relevant code snippets or logs

**Template:**
```markdown
**Description:**
Brief description of the bug

**To Reproduce:**
1. Step 1
2. Step 2
3. ...

**Expected Behavior:**
What should happen

**Actual Behavior:**
What actually happens

**Environment:**
- OS: [e.g., Ubuntu 20.04]
- Python: [e.g., 3.9.5]
- PyTorch: [e.g., 1.10.0]
- Camera: [e.g., Logitech C920]
- Robot: [e.g., xArm 6-DOF]

**Logs/Screenshots:**
[Add relevant information]
```

### Suggesting Features

Feature requests are welcome! Please:
1. Check if it's already been suggested
2. Explain the use case
3. Describe the expected behavior
4. Consider implementation complexity

**Template:**
```markdown
**Feature Description:**
Brief description

**Use Case:**
Why is this needed?

**Proposed Solution:**
How might this work?

**Alternatives Considered:**
Other approaches you've thought about
```

### Pull Requests

#### Before Starting

1. **Open an issue** to discuss major changes
2. **Check existing PRs** to avoid duplicates
3. **Fork the repository**

#### Development Process

1. **Create a feature branch:**
```bash
git checkout -b feature/your-feature-name
```

2. **Make your changes:**
   - Follow existing code style
   - Add comments for complex logic
   - Update documentation if needed

3. **Test your changes:**
   - Test with real hardware if possible
   - Test edge cases
   - Ensure no regressions

4. **Commit with clear messages:**
```bash
git commit -m "Add feature: descriptive message"
```

5. **Push to your fork:**
```bash
git push origin feature/your-feature-name
```

6. **Create pull request:**
   - Describe changes clearly
   - Reference related issues
   - Include test results
   - Add screenshots/videos if relevant

#### PR Checklist

- [ ] Code follows project style
- [ ] Comments added for complex sections
- [ ] Documentation updated (if applicable)
- [ ] Tested with real hardware (if applicable)
- [ ] No new warnings or errors
- [ ] Commit messages are clear
- [ ] PR description is complete

## Code Style Guidelines

### Python Style

Follow PEP 8 with these specifics:

**Naming:**
```python
# Classes: PascalCase
class ObjectAngleDetector:
    pass

# Functions/methods: snake_case
def detect_angle(self, frame):
    pass

# Constants: UPPER_SNAKE_CASE
GRIP_ROT_SERVO_ID = 2
MAX_DETECTION_CONFIDENCE = 0.95

# Variables: snake_case
object_angle = 45.0
```

**Imports:**
```python
# Standard library
import os
import sys
import time

# Third-party
import cv2
import torch
import numpy as np

# Local
from calibration import CalibrationManager
```

**Spacing:**
```python
# Two blank lines before class definitions
class MyClass:
    pass


# One blank line between methods
def method_one(self):
    pass

def method_two(self):
    pass
```

**Comments:**
```python
# Good: Explain WHY, not WHAT
# Normalize angle to [-90, 90] range to match gripper limits
angle = normalize_angle(raw_angle)

# Bad: Just describes what the code does
# Set angle to normalized angle
angle = normalize_angle(raw_angle)
```

**Documentation Strings:**
```python
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
    pass
```

### Code Organization

**File structure:**
```python
# 1. Shebang and encoding (if needed)
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 2. Module docstring
"""
Module for angle-aware object detection and robotic manipulation.
"""

# 3. Imports

# 4. Constants

# 5. Classes

# 6. Functions

# 7. Main execution
if __name__ == "__main__":
    main()
```

## Documentation

### Code Comments

- Add comments for non-obvious logic
- Explain complex algorithms
- Document assumptions
- Note hardware-specific requirements

### Inline Documentation

```python
# Good
# Apply rotation only if angle is within safe gripper range
# Outside this range, mechanical limits could be exceeded
if ANGLE_ADJUST_MIN <= angle <= ANGLE_ADJUST_MAX:
    rotation_value = angle_to_servo(angle)

# Bad
# Check if angle is in range
if ANGLE_ADJUST_MIN <= angle <= ANGLE_ADJUST_MAX:
    rotation_value = angle_to_servo(angle)
```

### README Updates

If your change affects usage:
- Update README.md
- Update relevant guide (QUICKSTART, HARDWARE_SETUP)
- Add examples if applicable

## Testing Guidelines

### Manual Testing

For hardware-dependent features:

1. **Vision system:**
   - Test with various lighting conditions
   - Test with different object types
   - Test edge cases (partial occlusion, etc.)

2. **Robot control:**
   - Test without power first (dry run)
   - Test with reduced speed
   - Test full sequence
   - Test error handling

3. **Conveyor control:**
   - Test start/stop
   - Test during pick sequence
   - Test error recovery

### Test Report Template

```markdown
**Feature Tested:** [Feature name]

**Test Environment:**
- Hardware: [Details]
- Software: [Versions]

**Test Cases:**
1. [Test case 1]
   - Expected: [...]
   - Result: [Pass/Fail]
   - Notes: [...]

2. [Test case 2]
   - Expected: [...]
   - Result: [Pass/Fail]
   - Notes: [...]

**Overall Result:** [Pass/Fail]
**Additional Notes:** [Any observations]
```

## Priority Areas for Contribution

We especially welcome contributions in:

### 🎯 High Priority
- **Multi-robot support** - Support for different arm types
- **Improved angle detection** - ML-based orientation estimation
- **Calibration tools** - Easier camera-arm calibration
- **Testing framework** - Automated testing infrastructure

### 🔧 Medium Priority
- **Performance optimization** - Faster inference, better frame rates
- **Additional object detection models** - YOLOv8, Faster R-CNN support
- **Web dashboard** - Real-time monitoring interface
- **Configuration UI** - GUI for parameter adjustment

### 📚 Documentation
- **Tutorial videos** - Step-by-step setup guides
- **Use case examples** - Real-world applications
- **Troubleshooting guide** - Common issues and solutions
- **API documentation** - Detailed function references

### 🐛 Bug Fixes
- Always welcome!
- Include test case if possible
- Document the fix clearly

## Recognition

Contributors will be:
- Listed in CONTRIBUTORS.md
- Mentioned in release notes
- Acknowledged in relevant documentation

## Questions?

- **General questions:** Open a discussion on GitHub
- **Contribution questions:** Comment on the relevant issue
- **Unclear guidelines:** Open an issue to improve this document

---

Thank you for contributing to make this project better! 🚀
