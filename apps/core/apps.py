import threading
import time
from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'

    def ready(self):
        """
        Called once when Django finishes loading.
        We start background threads here.
        
        Why the 5 second delay?
        Django's ready() fires before the DB connection pool is fully
        initialized. Without the delay, Device.objects.all() can fail
        with "connection refused" on startup.
        Alternative: use post_migrate signal — but that only fires
        after migrations, not on every startup.
        """
        # Avoid running twice in development (Django reloader starts two processes)
        import os
        if os.environ.get('RUN_MAIN') != 'true':
            return

        threading.Thread(target=self._delayed_start, daemon=True).start()

    def _delayed_start(self):
        time.sleep(3)
        print("🚀 Starting VeriFace background services...")

        # Run startup cleanup first
        from django.core.management import call_command
        call_command('startup_cleanup')

        from apps.camera.manager import camera_manager
        from apps.guest.scanner import start_qr_scanners

        camera_manager.start_all_cameras()
        camera_manager.ready.wait(timeout=30)
        print("📸 Cameras initialized")

        start_qr_scanners()
        print("🔍 QR scanners started")

        # No need to auto-restart pipelines anymore
        # Users will log in fresh and pipelines start on login
        print("✅ All background services running")