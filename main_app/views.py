from .models import *

import cv2
import time
from threading import Thread
from django.shortcuts import redirect, render
from django.http import HttpResponse, StreamingHttpResponse
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.core.cache import cache
from datetime import datetime, timedelta
from django.core.files.base import ContentFile

from .face_logs_module import *
from .arduino_control import *
from .qr_generator import generate_qr
from .face_utils import generate_face_embedding
from .camera_capture import camera_manager

#########################################################################################


##### # View for Controlling the Door # #####

def door_control(request):
    if request.method == "POST":
        current_status = arduino_instance.get_status()
        if current_status == "off":
            arduino_instance.send_command("open")
        else:
            arduino_instance.send_command("close")
        return redirect('control')

    # Always get actual door status from Arduino
    door_status = arduino_instance.get_status()
    return render(request, 'Base_UI/Base_Pages/door_control.html', {'door_status': door_status})

##### # # # #####

#
#
#
#
#

##### # View for Landing Page # #####

def landing_page(request):
    return render(request, 'Landing_Pages/landing_page.html')

##### # # # #####

#
#
#
#
#

##### # View for Logo Page # #####

def logo_page(request):
    return render(request, 'Landing_Pages/logo.html')

##### # # # #####

#
#
#
#
#

##### # Views for Authentication # #####

# Login View #
def login(request): 
    if request.method == 'POST':
        login_username = request.POST.get('login_username')
        login_password = request.POST.get('login_password')
        
        user = authenticate(username=login_username, password=login_password)

        if user is not None:
            auth_login(request, user)

            if not cache.get(f"recognition_started_for_user_{user.id}"):
                cache.set(f"recognition_started_for_user_{user.id}", True)
                start_face_recognition(user.id)

            return redirect('index')
        else:
            messages.error(request, "You have entered an invalid username or password!")

    return render(request, 'Authentication/login.html')


# Logout View # 
def custom_logout(request):
    user_id = request.user.id
    stop_face_recognition(user_id)
    cache.delete(f"recognition_started_for_user_{user_id}")
    auth_logout(request)
    request.session.flush()
    return redirect('login')


# Verify Device #
def verify_device(request):
    if request.method == "POST":
        product_number = request.POST.get("product_number")
        try:
            device = Device.objects.get(product_number=product_number)
            request.session["verified_device_id"] = device.id  # ✅ fixed here
            return redirect(register)  # redirect to next step
        except Device.DoesNotExist:
            messages.error(request, "Product number not found.")
    return render(request, "Authentication/verify_device.html")


# Register View #
def register(request):
    device_id = request.session.get("verified_device_id")
    if not device_id:
        return redirect("verify_device")

    if request.method == "POST":
        username = request.POST["name"]
        email = request.POST["email"]
        password = request.POST["password"]

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return render(request, "Authentication/register.html")

        user = User.objects.create_user(username=username, email=email, password=password)
        device = Device.objects.get(id=device_id)

        site_user = Site_Users.objects.create(user=user, email=email, device=device)
        request.session["user_id"] = user.id

        return redirect(upload_face)

    return render(request, "Authentication/register.html")


# Uploading Photo View #
def upload_face(request):
    user_id = request.session.get("user_id")
    if not user_id:
        return redirect(register)

    site_user = Site_Users.objects.get(user__id=user_id)

    if request.method == "POST":
        face_image = request.FILES.get("face_image")

        if not face_image:
            messages.error(request, "Please upload a face image.")
            return render(request, "Authentication/upload_face.html")

        site_user.face_image = face_image
        site_user.save()

        # 🔒 Double-check if file is really saved
        if not site_user.face_image or not site_user.face_image.path:
            messages.error(request, "Face image could not be saved. Try again.")
            return render(request, "Authentication/upload_face.html")

        try:
            # 💡 Lazy import DeepFace so TF doesn't load at server start
            from .face_utils import generate_face_embedding

            # 🔥 Generate embedding
            embedding_filename, embedding_path = generate_face_embedding(
                site_user.face_image.path, site_user.user.username
            )

            # 💾 Save embedding to model
            with open(embedding_path, "rb") as f:
                site_user.face_embedding_file.save(embedding_filename, ContentFile(f.read()))
            site_user.save()

            messages.success(request, "Registration completed successfully!")
            return redirect(login)

        except Exception as e:
            messages.error(request, f"Failed to process face image: {str(e)}")

    return render(request, "Authentication/upload_face.html")


##### # # # #####

#
#
#
#
#

##### # Views for Base_Pages # #####

# Index Page View #

def generate_frames(device_id):
    fps_limit = 30
    delay = 1 / fps_limit

    while True:
        start_time = time.time()
        frame = camera_manager.get_frame(device_id)
        if frame is None:
            time.sleep(0.1)
            continue

        _, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

        elapsed = time.time() - start_time
        sleep_time = delay - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)


def video_feed(request):
    # Get current user’s device
    try:
        site_user = Site_Users.objects.get(user=request.user)
        device = site_user.device

        # ✅ Check if camera is already running before trying to start it
        if device.id not in camera_manager.cameras:
            camera_manager.start_camera(device.id, device.ip_address)

        return StreamingHttpResponse(
            generate_frames(device.id),
            content_type='multipart/x-mixed-replace; boundary=frame'
        )

    except Site_Users.DoesNotExist:
        return HttpResponse("Unauthorized", status=401)

def index(request):
    return render(request, 'Base_UI/index.html', {"active_page": "live_feed"})



# Door Control Page View #
def door_page(request):
    return render(request, 'Base_UI/Base_Pages/door_control.html', {"active_page": "door_control"})



# QR Generator Page View #
def qr_generator(request):
    if request.method == "POST":
        guest_name = request.POST.get("guest_name")
        expiration_minutes_str = request.POST.get("expiration_time")  # Get time in minutes as a string

        print(expiration_minutes_str)

        if not guest_name or not expiration_minutes_str:
            return render(request, "Base_UI/Base_Pages/qr_generator.html", {
                "error": "All fields are required.", 
                "active_page": "qr_generator"
            })

        try:
            # ✅ Convert expiration time to an integer (minutes)
            expiration_minutes = int(expiration_minutes_str)

            if expiration_minutes <= 0:
                return render(request, "Base_UI/Base_Pages/qr_generator.html", {
                    "error": "Expiration time must be greater than 0 minutes.",
                    "active_page": "qr_generator"
                })

            # ✅ Get current time
            current_time = datetime.now()

            # ✅ Calculate expiration time by adding minutes
            expiration_time = current_time + timedelta(minutes=expiration_minutes)
            expiration_time_str = expiration_time.strftime("%I:%M %p")  # Format as "HH:MM AM/PM"

        except ValueError as e:
            return render(request, "Base_UI/Base_Pages/qr_generator.html", {
                "error": f"Invalid input: {e}. Please enter a valid number of minutes.", 
                "active_page": "qr_generator"
            })

        # ✅ Call the generate_qr function without passing session
        qr_code_url = generate_qr(request, guest_name, expiration_minutes)

        if qr_code_url:
            return render(request, "Base_UI/Base_Pages/qr_generator.html", {
                "success": "QR Code generated!", 
                "qr_code": qr_code_url, 
                "active_page": "qr_generator"
            })
        else:
            return render(request, "Base_UI/Base_Pages/qr_generator.html", {
                "error": "Error generating QR Code.", 
                "active_page": "qr_generator"
            })

    return render(request, "Base_UI/Base_Pages/qr_generator.html", {"active_page": "qr_generator"})



# Logs Page View #
def logs(request):
    try:
        site_user = Site_Users.objects.get(user=request.user)
        device = site_user.device

        # Get logs only for this user's device
        face_records = FaceRecord.objects.filter(device=device).order_by('-timestamp')

        return render(request, 'Base_UI/Base_Pages/logs.html', {
            'face_records': face_records,
            'device': device,
            "active_page": "logs"
        })

    except Site_Users.DoesNotExist:
        messages.error(request, "No device linked to your account.")
        return render(request, 'Base_UI/Base_Pages/logs.html', {
            'face_records': [],
            "active_page": "logs"
        })



# User Page View #

def user(request):
    site_user = Site_Users.objects.get(user=request.user)
    return render(request, 'Base_UI/Base_Pages/user.html', {'site_user': site_user, "active_page": "user"})

##### # # #####

#
#
#
#
#

##### # View for Recognition Thread when Logged In # #####

def start_recognition_for_user(request):
    if request.user.is_authenticated:
        Thread(target=process, args=(request.user.id,), daemon=True).start()
        return HttpResponse("✅ Face recognition started for user.")
    return redirect(login)

##### # # #####

















