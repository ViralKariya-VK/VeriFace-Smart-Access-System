import json
import time
import threading
import cv2
from django.utils import timezone
from django.db.models import F
from cryptography.fernet import Fernet, InvalidToken


# device_id -> thread
_scanner_threads = {}
_scanner_lock = threading.Lock()


def start_qr_scanners():
    """Start one QR scanner thread per active device."""
    from apps.core.models import Device
    devices = Device.objects.filter(is_active=True)
    for device in devices:
        _start_scanner_for_device(device.device_id)


def _start_scanner_for_device(device_id):
    with _scanner_lock:
        if device_id in _scanner_threads:
            return
        thread = threading.Thread(
            target=_scanner_loop,
            args=(device_id,),
            daemon=True
        )
        _scanner_threads[device_id] = thread
        thread.start()
        print(f"🔍 QR scanner started for device {device_id}")


def _validate_qr_data(qr_data_bytes, device_id):
    """
    Try to decrypt and validate a QR code against all active guests.
    Also checks use count limits.

    Why F() for use_count increment?
    F() updates the DB field directly without fetching first.
    Prevents race condition if two scans happen simultaneously —
    both would read use_count=0 and both set it to 1 without F().
    With F(), DB handles the increment atomically.
    """
    from apps.core.models import Guest

    active_guests = Guest.objects.filter(
        expires_at__gt=timezone.now(),
        created_by__device__device_id=device_id
    )

    for guest in active_guests:
        # Skip if count-limited and exhausted
        if guest.max_uses is not None and guest.use_count >= guest.max_uses:
            continue

        try:
            cipher = Fernet(guest.encryption_key.encode())
            decrypted = cipher.decrypt(qr_data_bytes).decode()
            payload = json.loads(decrypted)

            if payload.get('device_id') != device_id:
                continue

            if not payload.get('expires_at'):
                continue

            return guest

        except InvalidToken:
            continue
        except Exception as e:
            print(f"⚠️  QR validation error: {e}")
            continue

    return None


def _notify_qr_access(device_id, guest_name):
    """Notify all family members when guest uses QR code."""
    try:
        from apps.notifications.push import send_push_to_device
        send_push_to_device(
            device_id,
            f"🚪 Guest '{guest_name}' just entered using QR code"
        )
    except Exception as e:
        print(f"⚠️  QR notification failed: {e}")


def _scanner_loop(device_id):
    """
    Continuously scan camera frames for QR codes.

    10 FPS — QR detection is ~5ms per frame vs ~200ms for face recognition
    so we can afford to run it much faster without hurting CPU.
    """
    from apps.camera.manager import camera_manager
    from apps.door.arduino import door_controller
    from apps.core.models import AccessLog, Device, Guest

    detector = cv2.QRCodeDetector()
    last_open_time = 0
    cooldown = 5  # seconds

    print(f"QR scanner loop running for device {device_id}")

    while True:
        time.sleep(0.1)  # 10 FPS

        frame = camera_manager.get_frame(device_id)
        if frame is None or frame.size == 0:
            continue

        # Cooldown — don't process QR again too soon
        if time.time() - last_open_time < cooldown:
            continue

        try:
            data, points, _ = detector.detectAndDecode(frame)
        except cv2.error:
            continue

        if not data or points is None:
            continue

        try:
            qr_bytes = data.encode()
            guest = _validate_qr_data(qr_bytes, device_id)

            if guest:
                print(f"✅ Valid QR — opening door for guest: {guest.name}")
                last_open_time = time.time()

                # Increment use count atomically in DB
                Guest.objects.filter(id=guest.id).update(
                    use_count=F('use_count') + 1
                )

                # Check if exhausted after increment
                guest.refresh_from_db()
                if guest.max_uses is not None and guest.use_count >= guest.max_uses:
                    print(f"🗑️  QR for {guest.name} exhausted — deleting")
                    guest.delete()

                # Open door
                door_controller.open_door()

                # Log the access
                try:
                    device = Device.objects.get(device_id=device_id)
                    AccessLog.objects.create(
                        device=device,
                        profile=None,
                        access_type='qr',
                        access_granted=True,
                    )
                except Exception as e:
                    print(f"⚠️  Could not log QR access: {e}")

                # Push notification to all family members
                threading.Thread(
                    target=_notify_qr_access,
                    args=(device_id, guest.name),
                    daemon=True
                ).start()

            else:
                print("🚫 QR detected but invalid, expired, or exhausted")

        except Exception as e:
            print(f"❌ QR processing error: {e}")