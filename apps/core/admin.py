from django.contrib import admin
from .models import Device, Profile, AccessLog, Guest, PushSubscription


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ['device_id', 'name', 'ip_address', 'camera_status', 'is_active']
    # list_display controls which columns show in the admin list view
    # Alternative: just register with admin.site.register(Device) — but then
    # you get no control over what columns show, search, or filters


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'device', 'role', 'created_at']
    list_filter = ['role', 'device']
    # list_filter adds a sidebar filter — useful when you have many profiles


@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = ['device', 'profile', 'access_type', 'access_granted', 'timestamp']
    list_filter = ['access_type', 'access_granted', 'device']


@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_by', 'expires_at', 'created_at']


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['profile', 'created_at']