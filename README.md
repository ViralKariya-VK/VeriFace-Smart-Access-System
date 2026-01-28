# VeriFace – Smart Face-Based Door Access System

VeriFace is a capstone project that implements a face-based smart door access
control system by integrating computer vision, backend logic, and hardware
components.

The system automates door locking and unlocking using face verification,
while providing monitoring, logging, and security features via a web interface.

---

## System Overview
- Camera captures live video feed
- Faces are detected and verified against registered users
- Verified identity triggers Arduino-controlled solenoid door lock
- Door automatically relocks after a fixed time interval

---

## Key Features
- Product-key–based user registration and device isolation
- Facial enrollment and verification for up to multiple family members per device
- Real-time door unlock and auto-lock via Arduino UNO and solenoid lock
- Access logs and captured frames for unknown or suspicious activity
- Camera blinding detection with user alerts
- QR-code–based temporary access for guests
- Live camera feed accessible through the web application

---

## Tech Stack
- Python
- Django
- Computer Vision (pre-trained face recognition models)
- Arduino UNO
- Solenoid Door Lock
- HTML, CSS, JavaScript

---

## Notes
- This repository contains the original project code and system outputs
- Hardware configuration and environment-specific setup may be required
  to run the system on other machines
- The project focuses on system integration and applied problem solving
  rather than model research

---

## Future Improvements
- Liveness detection to prevent spoofing
- Improved robustness under varying lighting conditions
- Scalable deployment for multiple devices
