import os
import sys
import threading
import time
from django.apps import AppConfig


def _should_autostart():
    """
    Background services run in the real server process only — never during
    migrate, collectstatic, tests or other management commands.

    - `runserver`: Django's reloader sets RUN_MAIN=true in the serving child.
    - Docker / gunicorn: set VERIFACE_AUTOSTART=1 (the image does this).
    """
    if os.environ.get('VERIFACE_AUTOSTART', '').lower() in ('1', 'true', 'yes'):
        return True
    return os.environ.get('RUN_MAIN') == 'true' and 'runserver' in sys.argv


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'

    def ready(self):
        if not _should_autostart():
            return
        threading.Thread(target=self._delayed_start, daemon=True).start()

    def _delayed_start(self):
        # Give Django a moment to finish loading before touching the DB
        time.sleep(3)
        print("🚀 Starting VeriFace background services...")

        from apps.core.bootstrap import bootstrap_device_from_env
        bootstrap_device_from_env()

        from apps.camera.manager import camera_manager
        from apps.guest.scanner import start_qr_scanners
        from apps.recognition.pipeline import start_all_pipelines

        camera_manager.start_all_cameras()
        camera_manager.ready.wait(timeout=30)
        print("📸 Cameras initialized")

        start_qr_scanners()
        print("🔍 QR scanners started")

        start_all_pipelines()
        print("✅ All background services running")
