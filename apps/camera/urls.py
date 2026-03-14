from django.urls import path
from . import views

urlpatterns = [
    path('feed/', views.live_feed, name='live_feed'),
    path('stream/', views.video_stream, name='video_stream'),
    path('api/camera-status/', views.camera_status_api, name='camera_status_api'),
]