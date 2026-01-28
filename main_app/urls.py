from django.urls import path
from .import views


urlpatterns = [


    ### URLs for UI_Pages ###
    path('live_feed', views.index, name='index'),
    path('video_feed/', views.video_feed, name='video_feed'),
    path('start-recognition', views.start_recognition_for_user, name='start_recognition'),

    path('door_control', views.door_page, name='door_page'),
    path('control', views.door_control, name='control'),
    
    path('qr_generator', views.qr_generator, name='qr_generator'),
    
    path('logs', views.logs, name='logs'),
    
    path('user', views.user, name='user'),

    
   

    ### Landing Page URL ###
    path('', views.landing_page, name='landing_page'),





    ### Logo Page URL ###
    path('logo_page', views.logo_page, name='logo_page'),





    ### URLs for Authentication Module ###
    path('login', views.login, name='login'),

    path('verify_device', views.verify_device, name='verify_device'),
    
    path('register', views.register, name='register'),

    path('upload_face', views.upload_face, name='upload_face'),

    path('custom_logout', views.custom_logout, name='custom_logout'),
]