from django.urls import path
from . import views

urlpatterns = [
    path('guests/', views.qr_generator, name='qr_generator'),
    path('guests/delete/<int:guest_id>/', views.delete_guest, name='delete_guest'),
]