import cv2
import threading
import time
from django.conf import settings
import django
import os

class CameraManager:
    def __init__(self):
        self.cameras = {}
        self.ready = threading.Event()
        self.started = False  # ✅ Add this flag

    def start_all_registered_cameras(self):
        if self.started:
            print("🔁 CameraManager already started. Skipping.")
            return
        self.started = True
        from .models import Device
        devices = Device.objects.all()
        total = len(devices)
        ready_count = 0

        for device in devices:
            stream_url = f"http://{device.ip_address}:4747/video"
            started = self.start_camera(device.id, stream_url)
            if started:
                ready_count += 1

        if ready_count == total:
            print("✅ All cameras are ready.")
            self.ready.set()
        else:
            print("⚠️ Some cameras failed to start.")

    def start_camera(self, device_id, url):
        if device_id in self.cameras:
            print(f"⚠️ Camera for device {device_id} is already running.")
            return True

        cap = cv2.VideoCapture(url)
        if cap.isOpened():
            self.cameras[device_id] = {
                'cap': cap,
                'lock': threading.Lock(),
                'stream_url': url
            }
            print(f"✅ Started camera for device {device_id}")
            return True
        else:
            print(f"❌ Failed to open camera for device {device_id} at {url}")
            return False

    def get_frame(self, device_id):
        camera_data = self.cameras.get(device_id)
        if not camera_data:
            return None

        with camera_data['lock']:
            cap = camera_data['cap']
            if not cap.isOpened():
                return None
            ret, frame = cap.read()
            return frame if ret else None

# Singleton instance
camera_manager = CameraManager()
