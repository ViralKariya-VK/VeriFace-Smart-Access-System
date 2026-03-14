import cv2
import time
from django.contrib.auth.decorators import login_required
from django.http import StreamingHttpResponse, HttpResponse, JsonResponse
from django.shortcuts import render
from .manager import camera_manager


def generate_frames(device_id):
    """
    Generator function that yields MJPEG frames.

    Why a generator and not a regular function?
    StreamingHttpResponse needs something it can iterate over.
    A generator yields one frame at a time — Django sends each
    frame to the browser as it's produced, keeping the connection open.
    This is the MJPEG streaming pattern — browser receives a continuous
    multipart HTTP response, each part being a JPEG frame.

    Why 30 FPS cap?
    Beyond 30 FPS, human eye sees no improvement for a door camera.
    Also prevents hammering the network on mobile connections.
    """
    fps_limit = 30
    frame_delay = 1 / fps_limit

    while True:
        start = time.time()

        frame = camera_manager.get_frame(device_id)
        if frame is None:
            time.sleep(0.1)
            continue

        # Encode frame as JPEG
        # Quality 85 — good balance between image quality and bandwidth
        # Alternative: Quality 95 — better image but ~2x the bandwidth
        # For a mobile PWA over WiFi, 85 is the right call
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ret:
            continue

        frame_bytes = buffer.tobytes()

        # MJPEG multipart format — browser knows where each frame starts/ends
        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n'
            + frame_bytes +
            b'\r\n'
        )

        # Throttle to fps_limit
        elapsed = time.time() - start
        sleep_time = frame_delay - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)


@login_required
def live_feed(request):
    return render(request, 'app/live_feed.html', {'active_page': 'live_feed'})


@login_required
def video_stream(request):
    """
    The actual streaming endpoint — src of <img> tag in live_feed.html.

    Why separate view from live_feed?
    live_feed renders the HTML page.
    video_stream is the continuous MJPEG response.
    The browser opens two connections — one for the page, one for the stream.
    Mixing them would make the page never finish loading.
    """
    try:
        profile = request.user.profile
        device = profile.device
        device_id = device.device_id

        if device_id not in camera_manager.cameras:
            camera_manager.start_camera(device_id, device.camera_source)

        return StreamingHttpResponse(
            generate_frames(device_id),
            content_type='multipart/x-mixed-replace; boundary=frame'
        )

    except Exception as e:
        print(f"❌ Stream error: {e}")
        return HttpResponse("Stream unavailable", status=503)


@login_required
def camera_status_api(request):
    """
    JSON endpoint returning current camera status.
    Polled by frontend to show blocked/offline alerts.

    This is what triggers the in-app banner notification.
    The push notification is sent by the pipeline thread.
    The banner is driven by this endpoint being polled every 10 seconds.
    Two notification channels, same underlying status field.
    """
    try:
        device = request.user.profile.device
        return JsonResponse({
            'status': device.camera_status,
            'updated_at': device.camera_status_updated_at.isoformat()
            if device.camera_status_updated_at else None,
        })
    except Exception as e:
        return JsonResponse({'status': 'unknown', 'error': str(e)})