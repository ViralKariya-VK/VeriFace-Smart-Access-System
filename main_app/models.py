from django.db import models
from django.contrib.auth.models import User
import time


class Device(models.Model):
    id = models.CharField(max_length=100, primary_key=True)  # Now it's the primary key
    product_number = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=100)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)  # Owner of the device
    ip_address = models.GenericIPAddressField(protocol='both', unpack_ipv4=True)


    def __str__(self):
        return f"{self.name} ({self.id}) - {self.owner.username}"



class Site_Users(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    email = models.CharField(max_length=50)
    face_image = models.ImageField(upload_to="user_faces/")
    face_embedding_file = models.FileField(upload_to="face_embeddings/", null=True, blank=True)
    device = models.ForeignKey(Device, on_delete=models.CASCADE)

    def __str__(self):
        return self.user.username
    


class FaceRecord(models.Model):
    device = models.ForeignKey('Device', on_delete=models.CASCADE, related_name='face_records', null=True, blank=True)
    image = models.ImageField(upload_to="detected_faces/")
    face_encoding = models.BinaryField()  # Stores the face encoding as binary data
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"FaceRecord {self.id} - {self.timestamp}"
    


class Guest(models.Model):
    name = models.CharField(max_length=100)
    qr_code = models.ImageField(upload_to='qr_codes/')
    expiration_time = models.CharField(max_length=20)  # Store as string (HH:MM AM/PM)
    encryption_key = models.TextField()  # Store the key for future decryption

    created_by = models.ForeignKey(Site_Users, on_delete=models.CASCADE, related_name='guests')

    def __str__(self):
        return f"{self.name} - Expires at {self.expiration_time}"