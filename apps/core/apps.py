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
        time.sleep(5)
        print("Starting VeriFace background services...")

        from apps.camera.manager import camera_manager
        from apps.guest.scanner import start_qr_scanners

        camera_manager.start_all_cameras()
        camera_manager.ready.wait(timeout=30)
        print("Cameras initialized")

        start_qr_scanners()
        print("QR scanners started")

        # Auto-restart pipelines for devices that have active sessions
        # Why: if server restarts while users are logged in,
        # they shouldn't have to logout/login just to restart face recognition
        self._restart_active_pipelines()

        print("All background services running")

    def _restart_active_pipelines(self):
        """
        Find all devices that have logged-in users with active sessions
        and restart their recognition pipelines automatically.
        """
        try:
            from django.contrib.sessions.models import Session
            from django.utils import timezone
            from apps.core.models import Profile
            from apps.recognition.pipeline import start_pipeline

            active_sessions = Session.objects.filter(
                expire_date__gt=timezone.now()
            )

            device_ids_to_start = set()

            for session in active_sessions:
                data = session.get_decoded()
                user_id = data.get('_auth_user_id')
                if not user_id:
                    continue
                try:
                    profile = Profile.objects.get(user__id=user_id)
                    device_ids_to_start.add(profile.device.device_id)
                except Profile.DoesNotExist:
                    continue

            for device_id in device_ids_to_start:
                start_pipeline(device_id)
                print(f"Auto-restarted pipeline for device {device_id}")

            if not device_ids_to_start:
                print("No active sessions — pipelines idle")

        except Exception as e:
            print(f"⚠️Could not auto-restart pipelines: {e}")