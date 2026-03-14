from django.urls import path
from . import views

urlpatterns = [
    path('door/', views.door_control, name='door_control'),
    path('api/door-status/', views.door_status_api, name='door_status_api'),
]