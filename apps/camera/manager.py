# apps/camera/manager.py

import cv2
import threading
import numpy as np
import time
from django.utils import timezone


class CameraManager:
    # Singleton — only one instance ever exists
    # This ensures one VideoCapture connection per device across the whole app
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        # Thread-safe singleton creation
        # Without this lock, two threads could both see _instance is None
        # and both create instances simultaneously — race condition
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # device_id -> {'cap': VideoCapture, 'lock': Lock, 'last_frame': frame}
        # We store last_frame so readers always get something even if capture
        # is momentarily slow — avoids None frames causing crashes downstream
        self.cameras = {}
        self.ready = threading.Event()
        self.started = False

    def start_all_cameras(self):
        """Called once at startup from AppConfig.ready()"""
        if self.started:
            return
        self.started = True

        # Import here to avoid AppConfig circular import at module level
        from apps.core.models import Device
        devices = Device.objects.filter(is_active=True)

        for device in devices:
            # Support any MJPEG stream URL — AirDroid, DroidCam, IP Webcam all use this format
            # User just needs to put their phone's IP in the Device model
            self.start_camera(device.device_id, device.camera_source)

        self.ready.set()

    def start_camera(self, device_id, source):
        if device_id in self.cameras:
            return True

        # Support both local webcam index and IP stream URL
        if str(source).isdigit():
            cap_source = int(source)
            print(f"📷 Local webcam index {cap_source} for device {device_id}")
        else:
            cap_source = source
            print(f"📷 IP stream for device {device_id}")

        cap = cv2.VideoCapture(cap_source)

        if not cap.isOpened():
            print(f"❌ Could not open camera for device {device_id}")
            self._update_device_status(device_id, 'offline')
            return False

        self.cameras[device_id] = {
            'cap': cap,
            'lock': threading.Lock(),
            'last_frame': None,
            'low_variance_count': 0,
        }

        thread = threading.Thread(
            target=self._reader_thread,
            args=(device_id,),
            daemon=True
        )
        thread.start()
        print(f"✅ Camera started for device {device_id}")
        return True

    def _reader_thread(self, device_id):
        """Continuously reads frames and stores the latest one"""
        camera_data = self.cameras[device_id]
        cap = camera_data['cap']

        while True:
            ret, frame = cap.read()

            if not ret or frame is None:
                self._update_device_status(device_id, 'offline')
                time.sleep(1)
                continue

            # Blocked camera detection — check brightness variance
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            std_dev = np.std(gray)

            if std_dev < 8:
                # Low variance — could be blocked or covered
                camera_data['low_variance_count'] += 1
                if camera_data['low_variance_count'] >= 10:
                    # 10 consecutive low-variance frames = blocked
                    self._update_device_status(device_id, 'blocked')
            else:
                # Normal frame — reset counter and mark online
                camera_data['low_variance_count'] = 0
                self._update_device_status(device_id, 'online')

            with camera_data['lock']:
                camera_data['last_frame'] = frame

    def get_frame(self, device_id):
        """Get the latest frame for a device — used by recognition, QR scanner, live feed"""
        camera_data = self.cameras.get(device_id)
        if not camera_data:
            return None
        with camera_data['lock']:
            return camera_data['last_frame']

    def _update_device_status(self, device_id, status):
        """Update camera status in DB — throttled to once per 10 seconds to avoid DB spam"""
        camera_data = self.cameras.get(device_id)
        if not camera_data:
            return

        last_update_key = f'last_status_update_{status}'
        last_update = camera_data.get(last_update_key, 0)

        # Only write to DB if status changed or 10 seconds have passed
        # Alternative: Django signals — but overkill here
        if time.time() - last_update < 10:
            return

        camera_data[last_update_key] = time.time()

        try:
            from apps.core.models import Device
            Device.objects.filter(device_id=device_id).update(
                camera_status=status,
                camera_status_updated_at=timezone.now()
            )
            if status in ('blocked', 'offline'):
                print(f"Camera {device_id} is {status}")
        except Exception as e:
            print(f"Could not update camera status: {e}")


# The singleton instance — imported everywhere else in the app
camera_manager = CameraManager()