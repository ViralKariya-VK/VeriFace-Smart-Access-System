from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('verify-device/', views.verify_device, name='verify_device'),
    path('register/', views.register, name='register'),
    path('upload-face/', views.upload_face, name='upload_face'),
    path('profile/', views.user_profile, name='user_profile'),
]