import json
from django.conf import settings


def send_push_to_subscription(subscription, message):
    """
    Send a Web Push notification to a single subscription.
    
    Args:
        subscription: PushSubscription model instance
        message: string to show in notification
    
    Why pywebpush?
    It handles the VAPID signing and payload encryption for us.
    Alternative: send raw HTTP request to endpoint manually —
    but VAPID signing + payload encryption is complex crypto,
    not worth implementing from scratch.
    """
    try:
        from pywebpush import webpush, WebPushException
        from django.conf import settings
        import base64

        def fix_padding(b64_string):
            # Add padding if missing — base64 strings must be multiple of 4
            padding = 4 - len(b64_string) % 4
            if padding != 4:
                b64_string += '=' * padding
            return b64_string

        private_key = settings.VAPID_PRIVATE_KEY.replace('\\n', '\n')

        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {
                    "p256dh": fix_padding(subscription.p256dh),
                    "auth": fix_padding(subscription.auth),
                }
            },
            data=json.dumps({
                "title": "VeriFace Alert",
                "body": message,
                "icon": "/static/icons/icon-192x192.png",
            }),
            vapid_private_key=private_key,
            vapid_claims={
                "sub": f"mailto:{settings.VAPID_CLAIMS_EMAIL}"
            }
        )
        print(f"📲 Push sent to {subscription.profile.user.username}")

    except Exception as e:
        print(f"❌ Push failed for {subscription.profile.user.username}: {e}")


def send_push_to_device(device_id, message):
    """
    Send push notification to ALL profiles linked to a device.
    Used for camera blocked/offline alerts.
    
    Why notify all members and not just the owner?
    If the camera is blocked, every family member should know —
    not just the owner. It's a shared security concern.
    """
    from apps.core.models import PushSubscription

    subscriptions = PushSubscription.objects.filter(
        profile__device__device_id=device_id
    )

    if not subscriptions.exists():
        print(f"No push subscriptions found for device {device_id}")
        return

    for sub in subscriptions:
        send_push_to_subscription(sub, message)


def send_door_opened_notification(device_id, opened_by):
    """
    Notify all family members when door is opened by face recognition.
    
    Why notify everyone when door opens?
    Security awareness — if someone opens your door and you're
    inside, you should know. Also useful for parents tracking kids.
    
    opened_by: username string of the matched profile
    """
    message = f"Door opened by {opened_by}"
    send_push_to_device(device_id, message)