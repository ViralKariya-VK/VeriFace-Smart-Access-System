from django.utils import timezone
from datetime import datetime
import json
import time
import threading
from cryptography.fernet import Fernet
import cv2
from .arduino_control import arduino_instance
from .camera_capture import camera_manager
from .models import Guest, Device

door_open = False
scanner_threads = {}

def start_qr_scanners():
    """Start a QR scanning thread for each registered device."""
    devices = Device.objects.all()
    for device in devices:
        if device.id not in scanner_threads:
            thread = threading.Thread(target=scan_qr_and_open_door, args=(device.id,), daemon=True)
            thread.start()
            scanner_threads[device.id] = thread
            print(f"🟢 Started QR scanner for device: {device.id}")

def auto_lock_door():
    """Automatically locks the door after 5 seconds."""
    global door_open
    time.sleep(5)
    arduino_instance.send_command("close")
    door_open = False
    print("🔒 Door locked automatically after 5 seconds.")

def scan_qr_and_open_door(device_id):
    """Scans QR codes from the live feed and opens the door if valid for this camera."""
    global door_open
    print(f"📡 QR Scanner Running on device {device_id}...")
    detector = cv2.QRCodeDetector()

    while True:
        frame = camera_manager.get_frame(device_id)
        if frame is None or frame.size == 0:
            continue

        try:
            data, points, _ = detector.detectAndDecode(frame)
        except cv2.error as e:
            print("⚠️ OpenCV decode error:", e)
            continue

        if points is not None and data:
            qr_data = data.encode()  # Match the original encrypted bytes
            guests = Guest.objects.all().order_by('-id')

            for guest in guests:
                try:
                    cipher_suite = Fernet(guest.encryption_key.encode())
                    decoded_data = cipher_suite.decrypt(qr_data).decode()
                    guest_details = json.loads(decoded_data)

                    expiration_time = datetime.strptime(
                        guest_details["expiration_time"], "%m/%d/%Y %I:%M %p"
                    )
                    current_time = timezone.now()

                    if expiration_time > current_time:
                        guest_device_id = guest.created_by.device.id
                        if guest_device_id == device_id:
                            if not door_open:
                                print(f"✅ Valid QR for device {device_id}! Opening door...")
                                arduino_instance.send_command("open")
                                door_open = True
                                threading.Thread(target=auto_lock_door, daemon=True).start()
                            break
                        else:
                            print(f"🚫 QR valid but not for this device ({device_id}). Ignored.")
                    else:
                        print("⏳ QR Code Expired.")
                except Exception:
                    continue

        time.sleep(0.1)
