import qrcode
import json
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from django.core.files.base import ContentFile
from io import BytesIO
from .models import Guest, Site_Users

def generate_qr(request, guest_name, expiration_minutes):
    try:
        # ✅ Generate a new encryption key
        new_key = Fernet.generate_key().decode()  # Store as string
        key_bytes = new_key.encode()  # Convert back to bytes
        cipher_suite = Fernet(key_bytes)

        # ✅ Get system's current time and calculate expiration
        current_time = datetime.now()  # System local time
        expiration_time = current_time + timedelta(minutes=expiration_minutes)
        expiration_time_str = expiration_time.strftime("%m/%d/%Y %I:%M %p")  # Include both date and time

        # ✅ Create guest details
        guest_details = {
            "guest_name": guest_name,
            "expiration_time": expiration_time_str,
        }

        # ✅ Encrypt the guest details
        encoded_details = cipher_suite.encrypt(json.dumps(guest_details).encode())

        # ✅ Generate QR code
        qr = qrcode.make(encoded_details)

        # ✅ Save QR code to an in-memory file
        qr_io = BytesIO()
        qr.save(qr_io, format="PNG")
        qr_io.seek(0)

        site_user = Site_Users.objects.get(user=request.user)
        # ✅ Save guest info in the database with the encryption key
        guest = Guest.objects.create(
            name=guest_name,
            expiration_time=expiration_time_str,
            encryption_key=new_key,  # Save the key in the database
            created_by=site_user
        )
        guest.qr_code.save(f"{guest_name}_qr.png", ContentFile(qr_io.getvalue()), save=True)

        # ✅ Return QR code URL
        return guest.qr_code.url if guest.qr_code else None  # ✅ Return QR code URL

    except Exception as e:
        print("Error generating QR code:", e)
        return None