import ipaddress

import cv2
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .bootstrap import create_device
from .models import Device


def _is_local_request(request):
    """
    First-run setup is only allowed from the home network / the machine itself.
    Requests that arrived through a public tunnel carry the real client address
    in a forwarding header — if that address is public, refuse.
    """
    candidates = [request.META.get('REMOTE_ADDR', '')]
    for header in ('HTTP_CF_CONNECTING_IP', 'HTTP_X_FORWARDED_FOR', 'HTTP_X_REAL_IP'):
        value = request.META.get(header, '')
        if value:
            candidates.extend(v.strip() for v in value.split(','))
    for raw in candidates:
        try:
            ip = ipaddress.ip_address(raw)
        except ValueError:
            return False
        if not (ip.is_private or ip.is_loopback or ip.is_link_local):
            return False
    return True


def _setup_guard(request):
    """Returns a redirect/response if setup must not be shown, else None."""
    if Device.objects.exists():
        return redirect('landing')
    if not _is_local_request(request):
        return HttpResponse(
            "VeriFace has not been set up yet. Open it from a device on your "
            "home network to finish setup.", status=403)
    return None


def setup(request):
    blocked = _setup_guard(request)
    if blocked:
        return blocked

    if request.method == 'POST':
        name = request.POST.get('name', '').strip() or 'Front Door'
        source = request.POST.get('camera_source', '').strip()

        if not source:
            messages.error(request, "Enter a camera source.")
        else:
            device = create_device(name=name, camera_source=source)
            # Hand the owner straight into registration — they are the first member
            request.session['verified_device_id'] = device.device_id
            messages.success(request, f"Device created. Product key: {device.device_id}")
            return redirect('register')

    return render(request, 'auth/setup.html')


def _camera_snapshot(source):
    """Grab one frame from `source`: a JPEG response on success, JSON error otherwise."""
    if not source:
        return JsonResponse({'ok': False, 'error': 'Enter a camera source first.'}, status=400)

    from apps.camera.manager import CameraManager
    cap = CameraManager._open_capture(source)
    try:
        if not cap.isOpened():
            return JsonResponse({'ok': False, 'error': 'Could not open that camera source.'})
        frame = None
        for _ in range(5):  # first frames of RTSP streams are often grey/partial
            ok, frame = cap.read()
            if not ok:
                frame = None
        if frame is None:
            return JsonResponse({'ok': False, 'error': 'Connected, but no video frames received.'})
        ok, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        return HttpResponse(buf.tobytes(), content_type='image/jpeg')
    finally:
        cap.release()


@require_POST
def setup_test_camera(request):
    """Setup wizard camera test (only while setup is open, from the home network)."""
    blocked = _setup_guard(request)
    if blocked:
        return JsonResponse({'ok': False, 'error': 'Setup is closed.'}, status=403)
    return _camera_snapshot(request.POST.get('camera_source', '').strip())


# --- Owner management --------------------------------------------------------

def _owner_profile(request):
    profile = request.user.profile
    return profile if profile.is_owner() else None


@login_required
def manage(request):
    """Owner-only: camera, members, alerts and log housekeeping — no admin panel needed."""
    profile = _owner_profile(request)
    if profile is None:
        messages.error(request, "Only the owner can manage this door.")
        return redirect('user_profile')
    device = profile.device

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'camera':
            source = request.POST.get('camera_source', '').strip()
            if not source:
                messages.error(request, "Enter a camera source.")
            else:
                from apps.camera.manager import camera_manager
                device.camera_source = source
                device.save(update_fields=['camera_source'])
                camera_manager.restart_camera(device.device_id, source)
                messages.success(request, "Camera updated — reconnecting now.")

        elif action == 'alerts':
            device.alert_unknown = request.POST.get('alert_unknown') == 'on'
            device.save(update_fields=['alert_unknown'])
            messages.success(request, "Alert settings saved.")

        elif action == 'remove_member':
            target = device.profiles.filter(id=request.POST.get('profile_id')).select_related('user').first()
            if target is None:
                messages.error(request, "Member not found.")
            elif target.id == profile.id:
                messages.error(request, "You can't remove yourself — you're the owner.")
            else:
                name = target.user.username
                for f in (target.face_image, target.face_embedding):
                    if f:
                        f.delete(save=False)  # photo + biometric embedding go too
                # ...and any stray enrolment copies left by earlier versions
                import glob, os
                from django.conf import settings
                for stray in glob.glob(os.path.join(settings.MEDIA_ROOT, 'face_embeddings', f'{name}_embedding*.npy')):
                    os.remove(stray)
                target.user.delete()  # cascades to the profile
                messages.success(request, f"{name} was removed and can no longer open the door.")

        elif action == 'clear_logs':
            count = 0
            for log in device.access_logs.all():
                if log.image:
                    log.image.delete(save=False)
                log.delete()
                count += 1
            messages.success(request, f"Cleared {count} log entries.")

        return redirect('manage')

    return render(request, 'app/manage.html', {
        'device': device,
        'members': device.profiles.select_related('user').order_by('created_at'),
        'me': profile,
        'log_count': device.access_logs.count(),
        'active_page': '',
    })


@login_required
@require_POST
def manage_test_camera(request):
    if _owner_profile(request) is None:
        return JsonResponse({'ok': False, 'error': 'Owner only.'}, status=403)
    return _camera_snapshot(request.POST.get('camera_source', '').strip())
