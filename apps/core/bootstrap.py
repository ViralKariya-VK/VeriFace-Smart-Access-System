"""Helpers for creating a Device without touching the Django admin."""
import os
import secrets

from django.conf import settings


def generate_product_key():
    # Unambiguous characters only (no 0/O, 1/I) — people type this on a phone
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return 'DOOR-' + ''.join(secrets.choice(alphabet) for _ in range(6))


def create_device(name, camera_source, device_id=None):
    from apps.core.models import Device

    device = Device.objects.create(
        device_id=device_id or generate_product_key(),
        name=name or 'Front Door',
        ip_address='0.0.0.0',  # legacy required field; camera_source is what matters
        camera_source=camera_source,
        is_active=True,
    )
    _start_services_for(device)
    return device


def _start_services_for(device):
    """Bring a brand-new device live immediately — no restart needed."""
    from apps.camera.manager import camera_manager
    from apps.guest.scanner import _start_scanner_for_device
    from apps.recognition.pipeline import start_pipeline

    camera_manager.start_camera(device.device_id, device.camera_source)
    _start_scanner_for_device(device.device_id)
    start_pipeline(device.device_id)


def bootstrap_device_from_env():
    """
    Optional headless setup: if CAMERA_SOURCE is set and no device exists yet,
    create one. Lets people configure everything from docker-compose / .env.
    """
    from apps.core.models import Device

    source = os.environ.get('CAMERA_SOURCE', '').strip()
    if not source or Device.objects.exists():
        return None
    device = Device.objects.create(
        device_id=os.environ.get('DEVICE_ID', '').strip() or generate_product_key(),
        name=os.environ.get('DEVICE_NAME', 'Front Door'),
        ip_address='0.0.0.0',
        camera_source=source,
        is_active=True,
    )
    print(f"🆕 Created device {device.device_id} from environment")
    return device
