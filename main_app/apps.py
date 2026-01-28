import threading
import time
from django.apps import AppConfig

class MainAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'main_app'

    def ready(self):
        print("🚀 Waiting for Django to be ready...")

        from .camera_capture import camera_manager

        def delayed_start():
            time.sleep(5)

            # Only start cameras if they haven't started already
            if not camera_manager.started:
                threading.Thread(target=camera_manager.start_all_registered_cameras, daemon=True).start()
                print("⏳ Waiting for all cameras to initialize...")
                camera_manager.ready.wait()
                print("📸 All cameras are active. Proceeding...")
            else:
                print("📸 CameraManager already initialized. Proceeding...")

            from .qr_scanner import scan_qr_and_open_door, start_qr_scanners
            from django.db.utils import OperationalError
            from .models import Device

            try:
                devices = Device.objects.all()
            except OperationalError:
                return

            print("🔍 Starting QR Code Scanner in Background...")
            start_qr_scanners()
            for device in devices:
                threading.Thread(
                    target=scan_qr_and_open_door,
                    args=(device.id,),
                    daemon=True
                ).start()

        threading.Thread(target=delayed_start, daemon=True).start()
