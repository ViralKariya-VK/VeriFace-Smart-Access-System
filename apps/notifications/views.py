import json
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from apps.core.models import PushSubscription


@login_required
@csrf_exempt
@login_required
@csrf_exempt
def save_push_subscription(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
        endpoint = data.get('endpoint')
        p256dh = data.get('keys', {}).get('p256dh')
        auth = data.get('keys', {}).get('auth')

        if not all([endpoint, p256dh, auth]):
            return JsonResponse({'error': 'Missing subscription data'}, status=400)

        # Delete all old subscriptions for this profile first
        # This handles ngrok URL changes — old endpoint is useless anyway
        # When ngrok changes, browser gets new endpoint, we clean up old ones
        PushSubscription.objects.filter(
            profile=request.user.profile
        ).delete()

        # Save fresh subscription
        PushSubscription.objects.create(
            endpoint=endpoint,
            profile=request.user.profile,
            p256dh=p256dh,
            auth=auth,
        )
        return JsonResponse({'status': 'saved'})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def vapid_public_key(request):
    from django.conf import settings
    return JsonResponse({'public_key': settings.VAPID_PUBLIC_KEY})


@login_required
def events_since(request):
    """
    Alerts for the signed-in user's device, newer than ?after=<id>.
    Polled by the Android app. Without ?after it returns no events, just the
    latest id, so a freshly installed app doesn't replay old history.
    """
    from apps.core.models import Event

    try:
        device = request.user.profile.device
    except Exception:
        return JsonResponse({'events': [], 'latest': 0})

    qs = Event.objects.filter(device=device)
    latest = qs.order_by('-id').values_list('id', flat=True).first() or 0

    after = request.GET.get('after')
    if after is None or not after.isdigit():
        return JsonResponse({'events': [], 'latest': latest})

    events = [
        {'id': e.id, 'message': e.message, 'at': e.created_at.isoformat()}
        for e in qs.filter(id__gt=int(after))[:50]
    ]
    return JsonResponse({'events': events, 'latest': latest})
