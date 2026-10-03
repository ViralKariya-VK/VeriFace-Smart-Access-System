"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.views.static import serve as static_serve
from django.http import FileResponse, Http404, JsonResponse
import os
from apps.core import views as core_views

def healthz(request):
    # The Android app scans the local network for this signature to find the server
    return JsonResponse({'app': 'veriface', 'status': 'ok'})


def serve_sw(request):
    sw_path = os.path.join(settings.BASE_DIR, 'static', 'js', 'sw.js')
    return FileResponse(open(sw_path, 'rb'), content_type='application/javascript')

urlpatterns = [
    path('setup/', core_views.setup, name='setup'),
    path('setup/test-camera/', core_views.setup_test_camera, name='setup_test_camera'),
    path('manage/', core_views.manage, name='manage'),
    path('manage/test-camera/', core_views.manage_test_camera, name='manage_test_camera'),
    path('healthz', healthz, name='healthz'),
    path('sw.js', serve_sw, name='sw'),
    path('admin/', admin.site.urls),
    path('', include('apps.auth_app.urls')),
    path('', include('apps.door.urls')),
    path('', include('apps.camera.urls')),
    path('', include('apps.guest.urls')),
    path('', include('apps.recognition.urls')),
    path('', include('apps.notifications.urls')),
]

# Face photos, access-log snapshots and QR codes are private: only signed-in
# household members may fetch them. (Django's static() helper would serve them
# publicly, and only when DEBUG=True.) Static assets are served by WhiteNoise.
@login_required
def serve_media(request, path):
    # Face embeddings are biometric data — never expose them over HTTP
    if path.startswith('face_embeddings/'):
        raise Http404
    return static_serve(request, path, document_root=settings.MEDIA_ROOT)


urlpatterns += [path('media/<path:path>', serve_media)]
