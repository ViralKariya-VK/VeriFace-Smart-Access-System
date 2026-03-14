from django.urls import path
from . import views

urlpatterns = [
    path('api/push/subscribe/', views.save_push_subscription, name='push_subscribe'),
    path('api/push/vapid-key/', views.vapid_public_key, name='vapid_public_key'),
]