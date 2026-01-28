# your_app/middleware.py
from django.utils.deprecation import MiddlewareMixin
from .views import landing_page
from django.shortcuts import redirect
from django.urls import reverse

class DisableCSRFCheck(MiddlewareMixin):
    def process_request(self, request):
        setattr(request, '_dont_enforce_csrf_checks', True)


class RedirectToLandingPageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        landing_url = reverse(landing_page)  # Replace with your landing page URL name

        # Allow landing page, admin, static/media, and AJAX/API paths
        allowed_paths = [
            landing_url,
            '/admin/',
            '/static/',
            '/media/',
        ]
        if not any(request.path.startswith(path) for path in allowed_paths):
            return redirect(landing_page)  # Or redirect(landing_url)

        response = self.get_response(request)
        return response