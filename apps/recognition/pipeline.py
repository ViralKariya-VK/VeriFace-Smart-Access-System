# apps/recoginition/pipeline.py

import threading
import time
import cv2
import numpy as np
from django.utils import timezone
from django.core.files.base import ContentFile
from apps.notifications.push import send_door_opened_notification


# device_id -> threading.Event (used to stop the thread)
_running_pipelines = {}
_pipeline_lock = threading.Lock()


def start_pipeline(device_id):
    """
    Start recognition pipeline for a device.
    Called when any family member logs in.
    If pipeline already running for this device, does nothing.
    """
    with _pipeline_lock:
        if device_id in _running_pipelines:
            print(f"🟡 Pipeline already running for device {device_id}")
            return

        stop_event = threading.Event()
        _running_pipelines[device_id] = stop_event

        thread = threading.Thread(
            target=_pipeline_loop,
            args=(device_id, stop_event),
            daemon=True
        )
        thread.start()
        print(f"🚀 Recognition pipeline started for device {device_id}")


def start_all_pipelines():
    """
    Start recognition for every active device. Called once at boot so the door
    works after a power cut or reboot without anyone having to log in first.
    """
    from apps.core.models import Device
    for device in Device.objects.filter(is_active=True):
        start_pipeline(device.device_id)


def stop_pipeline(device_id):
    """
    Stop recognition pipeline for a device.
    Called when all family members of a device log out.
    
    Why 'all members'?
    If member A logs out but member B is still logged in,
    we should keep scanning — the door still needs to work for B.
    We check active sessions before stopping.
    """
    with _pipeline_lock:
        stop_event = _running_pipelines.get(device_id)
        if stop_event:
            stop_event.set()
            del _running_pipelines[device_id]
            print(f"🛑 Recognition pipeline stopped for device {device_id}")


def _load_device_embeddings(device_id, quiet=False):
    """
    Load all enrolled face embeddings for a device.
    Returns list of (profile_id, embedding_array) tuples.
    
    Why reload on each pipeline start instead of caching?
    New family members could enroll while the app is running.
    Loading fresh ensures we always have the latest embeddings.
    Alternative: Django signal on Profile save to hot-reload embeddings
    — good future improvement but adds complexity now.
    """
    from apps.core.models import Profile

    embeddings = []
    profiles = Profile.objects.filter(
        device__device_id=device_id,
        face_embedding__isnull=False
    ).exclude(face_embedding='')

    for profile in profiles:
        try:
            embedding = np.load(profile.face_embedding.path)
            embeddings.append((profile.id, embedding))
            if not quiet:
                print(f"📦 Loaded embedding for {profile.user.username}")
        except Exception as e:
            print(f"⚠️  Could not load embedding for {profile.user.username}: {e}")

    return embeddings


def _save_access_log(device_id, profile_id, access_granted, face_image_array):
    """
    Save an access attempt to the database.
    Both successful (granted) and failed (denied) attempts are logged.
    
    Why log denied attempts?
    Security audit trail — if someone is repeatedly trying to get in
    and failing, that's a pattern worth knowing about.
    """
    from apps.core.models import Device, Profile, AccessLog

    try:
        device = Device.objects.get(device_id=device_id)
        profile = Profile.objects.get(id=profile_id) if profile_id else None

        log = AccessLog(
            device=device,
            profile=profile,
            access_type='face',
            access_granted=access_granted,
        )

        # Save face image if we have one
        if face_image_array is not None and face_image_array.size > 0:
            _, buffer = cv2.imencode('.jpg', face_image_array)
            timestamp_str = timezone.now().strftime('%Y%m%d_%H%M%S')
            filename = f"face_{device_id}_{timestamp_str}.jpg"
            log.image.save(filename, ContentFile(buffer.tobytes()), save=False)

        log.save()

    except Exception as e:
        print(f"❌ Could not save access log: {e}")


def _send_camera_alert(device_id, status):
    """Alert every member of the device that the camera is blocked or offline."""
    from apps.notifications.push import send_push_to_device

    message = {
        'blocked': '⚠️ Your door camera appears to be blocked!',
        'offline': '⚠️ Your door camera is offline!'
    }.get(status, '⚠️ Camera issue detected')

    try:
        send_push_to_device(device_id, message)
    except Exception as e:
        print(f"❌ Could not send camera alert: {e}")


def _unknown_alerts_enabled(device_id):
    from apps.core.models import Device
    try:
        return Device.objects.get(device_id=device_id).alert_unknown
    except Exception:
        return False


def _send_unknown_alert(device_id):
    from apps.notifications.push import send_push_to_device
    try:
        send_push_to_device(device_id, "👤 Unknown person at your door")
    except Exception as e:
        print(f"❌ Could not send unknown-visitor alert: {e}")


def _pipeline_loop(device_id, stop_event):
    """
    Main recognition loop — runs in background thread.
    
    Timing design:
    - Frame grabbed every 0.5 seconds (2 FPS for recognition)
    - Why not 30 FPS? Face recognition is CPU heavy (~200ms per frame)
      Running it 30x per second would peg the CPU.
      2 FPS is enough — a person stands at the door for several seconds.
    - After a successful match, 10-second cooldown
      Prevents same person triggering multiple door opens
    """
    from apps.camera.manager import camera_manager
    from apps.recognition.engine import face_engine
    from apps.door.arduino import door_controller
    from django.conf import settings

    print(f"🔄 Pipeline loop running for device {device_id}")

    # Load all family embeddings for this device
    stored_embeddings = _load_device_embeddings(device_id)

    if not stored_embeddings:
        print(f"⚠️  No embeddings found for device {device_id} — pipeline idle")

    threshold = settings.FACE_SIMILARITY_THRESHOLD

    last_reload_time = time.time()
    reload_interval = 30      # Pick up newly enrolled family members without a restart
    last_open_time = 0        # Timestamp of last door open
    cooldown = 10             # Seconds before door can open again
    last_unknown_time = 0     # Throttle unknown-visitor alerts
    last_unknown_embedding = None
    unknown_cooldown = 20           # seconds between alerts for different faces
    unknown_same_person_window = 180  # a lingering visitor stays "the same visit"
    last_alert_time = 0       # Throttle camera alerts
    alert_cooldown = 60       # Only alert once per minute

    previous_camera_status = None

    while not stop_event.is_set():
        time.sleep(0.5)  # 2 FPS — intentional, see docstring above

        if time.time() - last_reload_time > reload_interval:
            last_reload_time = time.time()
            stored_embeddings = _load_device_embeddings(device_id, quiet=True)

        frame = camera_manager.get_frame(device_id)

        if frame is None:
            continue

        # Check camera status for alerts
        # We read from DB only every 5 seconds to avoid hammering it
        try:
            from apps.core.models import Device
            device_obj = Device.objects.get(device_id=device_id)
            current_status = device_obj.camera_status

            if current_status != previous_camera_status:
                previous_camera_status = current_status

                if current_status in ('blocked', 'offline'):
                    now = time.time()
                    if now - last_alert_time > alert_cooldown:
                        last_alert_time = now
                        threading.Thread(
                            target=_send_camera_alert,
                            args=(device_id, current_status),
                            daemon=True
                        ).start()
        except Exception:
            pass

        # Skip recognition if camera is blocked or offline
        # No point running expensive model on a useless frame
        if previous_camera_status in ('blocked', 'offline'):
            continue

        # Skip recognition if we're in cooldown
        now = time.time()
        if now - last_open_time < cooldown:
            continue

        # Run face recognition
        matched_profile_id, bbox, face_image, unknown = face_engine.recognize(
            frame,
            stored_embeddings,
            threshold=threshold
        )

        if matched_profile_id:
            print(f"🔓 Match found — opening door for profile {matched_profile_id}")
            last_open_time = time.time()

            # Get username for notification
            try:
                from apps.core.models import Profile
                profile = Profile.objects.get(id=matched_profile_id)
                username = profile.user.username
            except Exception:
                username = "Unknown"

            threading.Thread(
                target=door_controller.open_door,
                daemon=True
            ).start()

            threading.Thread(
                target=_save_access_log,
                args=(device_id, matched_profile_id, True, face_image),
                daemon=True
            ).start()

            # Notify all family members that door was opened
            threading.Thread(
                target=send_door_opened_notification,
                args=(device_id, username),
                daemon=True
            ).start()

        elif unknown is not None and stored_embeddings:
            # An unrecognised face. Log it and alert — but not on every frame:
            # the same person standing at the door must produce one alert, and
            # a busy doorway must not flood anyone's phone.
            now = time.time()
            u_image, u_embedding = unknown
            same_person = (
                last_unknown_embedding is not None
                and now - last_unknown_time < unknown_same_person_window
                and face_engine.compare(u_embedding, last_unknown_embedding) > 0.5
            )
            if not same_person and now - last_unknown_time >= unknown_cooldown:
                if _unknown_alerts_enabled(device_id):
                    last_unknown_time = now
                    last_unknown_embedding = u_embedding
                    print("❓ Unknown face at the door")
                    threading.Thread(
                        target=_save_access_log,
                        args=(device_id, None, False, u_image),
                        daemon=True
                    ).start()
                    threading.Thread(
                        target=_send_unknown_alert,
                        args=(device_id,),
                        daemon=True
                    ).start()
            elif same_person:
                last_unknown_time = now  # still standing there — keep the window open

    print(f"✅ Pipeline loop exited cleanly for device {device_id}")