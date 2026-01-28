# face_logs_module.py
import cv2
import face_recognition
import numpy as np
from datetime import datetime
from django.core.files.base import ContentFile
from .models import FaceRecord, Site_Users
from .camera_capture import camera_manager
from .arduino_control import arduino_instance
import time
from threading import Thread, Event

running_processes = {}  # Stores user_id -> stop_event

def start_face_recognition(user_id):
    if user_id in running_processes:
        print(f"🟡 Recognition already running for user {user_id}")
        return

    stop_event = Event()
    thread = Thread(target=process, args=(user_id, stop_event), daemon=True)
    running_processes[user_id] = stop_event
    thread.start()

def stop_face_recognition(user_id):
    stop_event = running_processes.get(user_id)
    if stop_event:
        stop_event.set()
        del running_processes[user_id]
        print(f"🛑 Stopped recognition for user {user_id}")

def process(user_id, stop_event):
    print(f"🔐 Starting face recognition for user ID: {user_id}")

    try:
        site_user = Site_Users.objects.get(user__id=user_id)
        device = site_user.device
        if not site_user.face_embedding_file:
            print("❌ No face embedding file for this user.")
            return

        embedding_path = site_user.face_embedding_file.path
        reference_face_embeddings = np.load(embedding_path, allow_pickle=True)
        if reference_face_embeddings.ndim == 1:
            reference_face_embeddings = reference_face_embeddings.reshape(1, -1)

    except Site_Users.DoesNotExist:
        print("❌ Site_Users entry not found.")
        return
    except Exception as e:
        print(f"❌ Error loading embeddings: {e}")
        return

    print("📷 Face Recognition Started...")
    last_detected_faces = []
    re_capture_duration = 10
    frame_interval = 1
    tolerance = 0.9
    last_comparison_time = 0
    comparison_interval = 2
    last_processed_time = time.time()

    while not stop_event.is_set():
        if time.time() - last_processed_time < frame_interval:
            time.sleep(0.1)
            continue

        frame = None
        retry_attempts = 5  # Try for up to 5 seconds
        for _ in range(retry_attempts):
            frame = camera_manager.get_frame(device.id)
            if frame is not None:
                break
            print(f"⏳ Waiting for camera {device.id} to become available...")
            time.sleep(1)

        if frame is None:
            print(f"❌ Camera {device.id} not available after retries.")
            continue

        last_processed_time = time.time()
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_frame)
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

        for face_encoding, face_location in zip(face_encodings, face_locations):
            now = datetime.now()

            is_duplicate = False
            for prev_encoding, prev_time in last_detected_faces:
                if (now - prev_time).total_seconds() < re_capture_duration:
                    match = face_recognition.compare_faces([prev_encoding], face_encoding, tolerance=tolerance)
                    if match[0]:
                        is_duplicate = True
                        break

            if is_duplicate:
                continue

            last_detected_faces.append((face_encoding, now))

            top, right, bottom, left = face_location
            top = max(0, top - 150)
            bottom = min(frame.shape[0], bottom + 150)
            left = max(0, left - 150)
            right = min(frame.shape[1], right + 150)

            face_image = frame[top:bottom, left:right]
            if face_image.size == 0:
                continue

            _, buffer = cv2.imencode('.jpg', face_image)
            face_file = ContentFile(buffer.tobytes(), name=f"face_{now.strftime('%Y%m%d%H%M%S')}.jpg")

            FaceRecord.objects.create(
                device=device,
                image=face_file,
                face_encoding=buffer.tobytes(),
                timestamp=now
            )

            print(f"🧠 Detected {len(face_encodings)} faces in frame")
            if time.time() - last_comparison_time > comparison_interval:
                if face_encoding.ndim == 1:
                    face_encoding = face_encoding.reshape(1, -1)

                distances = np.linalg.norm(reference_face_embeddings - face_encoding, axis=1)
                if np.any(distances < 0.6):
                    print("🔓 Match found! Opening door.")
                    arduino_instance.send_command("open")
                    time.sleep(5)
                    arduino_instance.send_command("close")

                last_comparison_time = time.time()

        time.sleep(0.1)

    print(f"🛑 Face recognition stopped for user {user_id}")
