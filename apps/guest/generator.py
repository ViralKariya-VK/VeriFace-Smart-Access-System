import json
import qrcode
from io import BytesIO
from django.utils import timezone
from datetime import timedelta
from cryptography.fernet import Fernet
from django.core.files.base import ContentFile


def generate_guest_qr(profile, guest_name, days=0, hours=0, minutes=0, max_uses=None):
    """
    Generate encrypted QR code for guest access.

    Args:
        profile: Profile instance of the owner generating the QR
        guest_name: Display name for the guest
        days, hours, minutes: Expiry duration components
        max_uses: Max number of times QR can be used. None = unlimited.

    Why store use_count in DB and not in the QR payload?
    If we stored remaining uses in the QR, the guest could
    just screenshot and reuse the original QR indefinitely
    since the payload never changes. DB-side tracking is
    the only tamper-proof approach.
    """
    from apps.core.models import Guest

    total_minutes = (days * 24 * 60) + (hours * 60) + minutes
    if total_minutes <= 0:
        raise ValueError("Expiry duration must be greater than zero.")

    key = Fernet.generate_key()
    cipher = Fernet(key)

    expires_at = timezone.now() + timedelta(minutes=total_minutes)

    payload = json.dumps({
        "guest_name": guest_name,
        "expires_at": expires_at.isoformat(),
        "device_id": profile.device.device_id,
    })

    encrypted = cipher.encrypt(payload.encode())

    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(encrypted)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)

    guest = Guest(
        name=guest_name,
        expires_at=expires_at,
        encryption_key=key.decode(),
        created_by=profile,
        max_uses=max_uses,  # None = unlimited
        use_count=0,
    )

    filename = f"qr_{guest_name}_{expires_at.strftime('%Y%m%d%H%M%S')}.png"
    guest.qr_code.save(filename, ContentFile(buffer.getvalue()), save=False)
    guest.save()

    return guest