from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .arduino import door_controller
from apps.core.models import AccessLog


@login_required
def door_control(request):
    """
    Main door control page.
    GET — show current door status
    POST — toggle door state

    Why login_required decorator?
    Any unauthenticated request gets redirected to login automatically.
    Alternative: middleware that checks authentication globally —
    but that's too broad, some pages (landing, login) should be public.
    Decorator is surgical — applied only where needed.
    """
    if request.method == 'POST':
        current_status = door_controller.get_status()

        if current_status == 'off':
            door_controller.send_command('OPEN')
            action = 'opened'
        else:
            door_controller.send_command('CLOSE')
            action = 'closed'

        # Log manual door control
        try:
            AccessLog.objects.create(
                device=request.user.profile.device,
                profile=request.user.profile,
                access_type='manual',
                access_granted=True,
            )
        except Exception as e:
            print(f"⚠️  Could not log manual access: {e}")

        return redirect('door_control')

    door_status = door_controller.get_status()
    return render(request, 'app/door_control.html', {
        'door_status': door_status,
        'active_page': 'door_control',
    })


@login_required
def door_status_api(request):
    """
    JSON endpoint for live door status polling.
    Called by frontend every few seconds to update UI without page reload.

    Why a separate API endpoint and not WebSocket?
    WebSocket is the "correct" solution for real-time updates but
    requires Django Channels + Redis — significant infrastructure.
    For a status that changes rarely (door open/close), polling every
    3 seconds is perfectly fine and much simpler to deploy.
    Alternative: Server-Sent Events (SSE) — one-way push, simpler than
    WebSocket but still needs async Django. Overkill here.
    """
    status = door_controller.get_status()
    return JsonResponse({
        'status': status,
        'label': 'Open' if status == 'on' else 'Closed',
    })