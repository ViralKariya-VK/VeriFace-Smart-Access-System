from django.shortcuts import render, redirect
from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.files.base import ContentFile
from django.conf import settings
from django.contrib.auth.decorators import login_required


def landing(request):
    return render(request, 'landing.html')


def login(request):
    # If already logged in, skip login page entirely
    if request.user.is_authenticated:
        return redirect('live_feed')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        if not username or not password:
            messages.error(request, "Please enter both username and password.")
            return render(request, 'auth/login.html')

        user = authenticate(request, username=username, password=password)

        if user is None:
            messages.error(request, "Invalid username or password.")
            return render(request, 'auth/login.html')

        auth_login(request, user)

        # Start face recognition pipeline for this user's device
        # We do this here — not in AppConfig — because pipeline should
        # only run when someone is actually logged in
        try:
            from apps.recognition.pipeline import start_pipeline
            device_id = user.profile.device.device_id
            start_pipeline(device_id)
        except Exception as e:
            print(f"⚠️  Could not start pipeline: {e}")

        return redirect('live_feed')

    return render(request, 'auth/login.html')


def logout(request):
    if request.user.is_authenticated:
        try:
            from apps.recognition.pipeline import stop_pipeline
            from apps.core.models import Profile

            device_id = request.user.profile.device.device_id

            # Only stop pipeline if no other family members are logged in
            # How do we check? Count active sessions for this device.
            # Alternative: Django signals on session expiry — complex
            # We use a simpler approach: check if any other user from
            # the same device has an active session
            from django.contrib.sessions.models import Session
            from django.utils import timezone
            import json

            active_sessions = Session.objects.filter(
                expire_date__gt=timezone.now()
            )

            other_users_active = False
            current_user_id = str(request.user.id)

            for session in active_sessions:
                data = session.get_decoded()
                session_user_id = data.get('_auth_user_id')
                if session_user_id and session_user_id != current_user_id:
                    # Check if this user belongs to same device
                    try:
                        other_profile = Profile.objects.get(
                            user__id=session_user_id,
                            device__device_id=device_id
                        )
                        other_users_active = True
                        break
                    except Profile.DoesNotExist:
                        continue

            if not other_users_active:
                stop_pipeline(device_id)
                print(f"🛑 No other users active — pipeline stopped")
            else:
                print(f"👥 Other users still active — pipeline kept running")

        except Exception as e:
            print(f"⚠️  Logout pipeline check failed: {e}")

    auth_logout(request)
    return redirect('login')


def verify_device(request):
    """
    Step 1 of registration — verify product key exists.
    Stores device_id in session for next step.

    Why session and not a hidden form field?
    Hidden form fields can be tampered with by the user.
    Session is server-side — user can't forge a device_id
    they didn't legitimately verify.
    """
    if request.method == 'POST':
        product_key = request.POST.get('product_key', '').strip()

        try:
            from apps.core.models import Device
            device = Device.objects.get(device_id=product_key, is_active=True)

            # Check if device is full (max family members)
            if device.is_full():
                messages.error(
                    request,
                    f"This device already has the maximum of "
                    f"{settings.MAX_FAMILY_MEMBERS} members registered."
                )
                return render(request, 'auth/verify_device.html')

            request.session['verified_device_id'] = device.device_id
            return redirect('register')

        except Exception:
            messages.error(request, "Invalid product key. Please check and try again.")

    return render(request, 'auth/verify_device.html')


def register(request):
    """
    Step 2 of registration — create user account.
    Requires verified_device_id in session from previous step.
    """
    device_id = request.session.get('verified_device_id')
    if not device_id:
        # Someone tried to access register directly without verifying device
        return redirect('verify_device')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()

        if not all([username, email, password]):
            messages.error(request, "All fields are required.")
            return render(request, 'auth/register.html')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken.")
            return render(request, 'auth/register.html')

        if len(password) < 8:
            messages.error(request, "Password must be at least 8 characters.")
            return render(request, 'auth/register.html')

        # Create Django user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        # Determine role — first member of device is owner
        from apps.core.models import Device, Profile
        device = Device.objects.get(device_id=device_id)

        role = 'owner' if device.member_count() == 0 else 'member'

        Profile.objects.create(
            user=user,
            device=device,
            role=role,
        )

        # Store user_id for face upload step
        request.session['registering_user_id'] = user.id
        return redirect('upload_face')

    return render(request, 'auth/register.html')


def upload_face(request):
    """
    Step 3 of registration — upload face photo and generate embedding.

    Why a separate step and not part of register?
    Face processing takes 2-3 seconds — showing a loading state
    is much better UX than a form that hangs for 3 seconds after submit.
    Separate step also means if face upload fails, account isn't lost.
    """
    user_id = request.session.get('registering_user_id')
    if not user_id:
        return redirect('register')

    if request.method == 'POST':
        face_image = request.FILES.get('face_image')

        if not face_image:
            messages.error(request, "Please upload a photo.")
            return render(request, 'auth/upload_face.html')

        # Validate file type
        allowed_types = ['image/jpeg', 'image/png', 'image/jpg']
        if face_image.content_type not in allowed_types:
            messages.error(request, "Please upload a JPG or PNG image.")
            return render(request, 'auth/upload_face.html')

        # Validate file size — max 5MB
        if face_image.size > 5 * 1024 * 1024:
            messages.error(request, "Image must be under 5MB.")
            return render(request, 'auth/upload_face.html')

        try:
            from apps.core.models import Profile
            from apps.recognition.engine import face_engine

            profile = Profile.objects.get(user__id=user_id)

            # Save face image first
            profile.face_image = face_image
            profile.save()

            # Generate embedding
            filename, path = face_engine.enroll_face(
                profile.face_image.path,
                profile.user.username
            )

            # Save embedding reference to profile
            with open(path, 'rb') as f:
                profile.face_embedding.save(filename, ContentFile(f.read()))
            profile.save()

            # Clean up session
            del request.session['registering_user_id']
            del request.session['verified_device_id']

            messages.success(request, "Registration complete! Please login.")
            return redirect('login')

        except ValueError as e:
            # Face not detected in image
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f"Something went wrong: {str(e)}")

    return render(request, 'auth/upload_face.html')

@login_required
def user_profile(request):
    return render(request, 'app/user.html')