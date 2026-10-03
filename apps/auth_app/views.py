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
    from apps.core.models import Device
    # Fresh install: send the owner straight into setup
    if not Device.objects.exists():
        return redirect('setup')
    return render(request, 'landing.html')


# --- Login throttling -------------------------------------------------------
# The app can be exposed to the internet through a tunnel, so passwords must
# not be guessable by brute force. Per username+IP, in-memory (single process).
MAX_LOGIN_FAILURES = 5
LOGIN_LOCKOUT_SECONDS = 15 * 60


def _client_ip(request):
    forwarded = request.META.get('HTTP_CF_CONNECTING_IP') or request.META.get('HTTP_X_FORWARDED_FOR', '')
    return forwarded.split(',')[0].strip() or request.META.get('REMOTE_ADDR', '')


def _throttle_key(request, username):
    return f"login-fail:{username.lower()}:{_client_ip(request)}"


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

        from django.core.cache import cache
        key = _throttle_key(request, username)
        if cache.get(key, 0) >= MAX_LOGIN_FAILURES:
            messages.error(request, "Too many failed attempts. Try again in 15 minutes.")
            return render(request, 'auth/login.html', status=429)

        user = authenticate(request, username=username, password=password)

        if user is None:
            cache.set(key, cache.get(key, 0) + 1, LOGIN_LOCKOUT_SECONDS)
            messages.error(request, "Invalid username or password.")
            return render(request, 'auth/login.html')

        cache.delete(key)
        auth_login(request, user)

        # Safety net: make sure recognition is running (it normally starts at boot)
        try:
            from apps.recognition.pipeline import start_pipeline
            device_id = user.profile.device.device_id
            start_pipeline(device_id)
        except Exception as e:
            print(f"⚠️  Could not start pipeline: {e}")

        return redirect('live_feed')

    return render(request, 'auth/login.html')


def logout(request):
    # The recognition pipeline is a property of the device, not of a login
    # session — the door must keep working while everyone is logged out.
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

        # Validate file size — max 15MB (phone photos are big; they are downscaled)
        if face_image.size > 15 * 1024 * 1024:
            messages.error(request, "Image must be under 15MB.")
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

            # The engine's scratch copy is now redundant — don't leave a second
            # copy of someone's biometric data lying around
            import os
            if os.path.exists(path) and os.path.abspath(path) != os.path.abspath(profile.face_embedding.path):
                os.remove(path)

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