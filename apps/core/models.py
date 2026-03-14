# apps/core/models.py

from django.db import models
from django.contrib.auth.models import User
from django.conf import settings


class Device(models.Model):
    # CharField PK instead of AutoField — lets us use meaningful IDs like "DOOR-A1B2"
    # Alternative: use AutoField (integer) + a separate product_number field
    # We keep CharField PK because product_number IS the identity of the device
    device_id = models.CharField(max_length=100, primary_key=True)
    name = models.CharField(max_length=100)
    ip_address = models.GenericIPAddressField()
# Camera source — flexible field supporting both IP streams and local webcams
# Examples:
#   "0" or "1"                    → local webcam by index
#   "http://192.168.1.5:4747/video" → AirDroid / DroidCam IP stream
#   "http://192.168.1.5:8080/video" → IP Webcam app
# We keep ip_address separate for network/device identification purposes
# camera_source is purely about where to get the video feed from
    camera_source = models.CharField(
        max_length=255,
        default='0',
        help_text='Webcam index (0, 1) or full IP camera stream URL'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    CAMERA_STATUS_CHOICES = [
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('blocked', 'Blocked'),
    ]
    camera_status = models.CharField(
        max_length=10,
        choices=CAMERA_STATUS_CHOICES,
        default='offline'
    )
    camera_status_updated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.device_id})"

    def member_count(self):
        # Helper to check if device is full before allowing new registration
        return self.profiles.count()

    def is_full(self):
        return self.member_count() >= settings.MAX_FAMILY_MEMBERS


class Profile(models.Model):
    # OneToOneField means one User = one Profile, no more, no less
    # Alternative: AbstractUser (extend User model directly)
    # We avoid AbstractUser because it requires custom auth backend and
    # complicates things when Django's User model is already working fine
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('member', 'Member'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='profiles')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='member')
    face_image = models.ImageField(upload_to='user_faces/')
    # Embedding stored as .npy file — 512-d ArcFace vector
    # Alternative: store as BinaryField or JSONField (list of floats)
    # We use FileField because numpy's .npy format is the most efficient
    # for loading back with np.load() — no serialization overhead
    face_embedding = models.FileField(upload_to='face_embeddings/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({self.role}) — {self.device.name}"

    def is_owner(self):
        return self.role == 'owner'


class AccessLog(models.Model):
    # Renamed from FaceRecord — more descriptive of what it actually is
    ACCESS_TYPE_CHOICES = [
        ('face', 'Face Recognition'),
        ('qr', 'QR Code'),
        ('manual', 'Manual Control'),
    ]

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='access_logs')
    # Who was recognized — null if unrecognized face or QR guest
    profile = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, blank=True)
    access_type = models.CharField(max_length=10, choices=ACCESS_TYPE_CHOICES)
    # Was the door actually opened? False = face detected but not matched
    access_granted = models.BooleanField(default=False)
    image = models.ImageField(upload_to='access_logs/', null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        status = "Granted" if self.access_granted else "Denied"
        return f"{self.access_type} | {status} | {self.timestamp}"


class Guest(models.Model):
    name = models.CharField(max_length=100)
    qr_code = models.ImageField(upload_to='qr_codes/')
    # Fixed from original — was CharField storing formatted string
    # DateTimeField is timezone-aware, comparable, queryable
    # Original bug: string comparison for expiry could silently fail
    expires_at = models.DateTimeField()
    encryption_key = models.TextField()
    # None = unlimited uses, integer = max allowed uses

    # Why nullable instead of 0 for unlimited?
    # 0 would be ambiguous — does it mean unlimited or zero uses allowed?
    # None explicitly means "no limit set"
    max_uses = models.IntegerField(null=True, blank=True)
    use_count = models.IntegerField(default=0)
    created_by = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='guests')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} — expires {self.expires_at}"

    def is_expired(self):
        from django.utils import timezone
        if timezone.now() > self.expires_at:
            return True
        # Count-limited — expired if max uses reached
        if self.max_uses is not None and self.use_count >= self.max_uses:
            return True
        return False

    def uses_remaining(self):
        if self.max_uses is None:
            return None  # Unlimited
        return max(0, self.max_uses - self.use_count)

class PushSubscription(models.Model):
    # Stores browser push subscription per user
    # Each browser/device gets its own subscription endpoint
    # So one user on 2 phones = 2 PushSubscription rows — that's correct
    # Alternative: store as JSONField on Profile directly
    # We use a separate model because one profile can have multiple devices/browsers
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='push_subscriptions')
    # The endpoint URL that the browser's push service gave us
    endpoint = models.TextField(unique=True)
    # p256dh and auth are encryption keys the browser generated
    # We need both to encrypt the push payload
    p256dh = models.TextField()
    auth = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Push subscription for {self.profile.user.username}"