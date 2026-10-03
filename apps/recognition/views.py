from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string

from apps.core.models import AccessLog

PER_PAGE = 10
FILTERS = {'all', 'granted', 'denied'}


@login_required
def logs(request):
    device = request.user.profile.device

    try:
        page = max(1, int(request.GET.get('page', 1)))
    except ValueError:
        page = 1
    active_filter = request.GET.get('filter', 'all')
    if active_filter not in FILTERS:
        active_filter = 'all'

    qs = AccessLog.objects.filter(device=device).select_related('profile', 'profile__user')
    if active_filter == 'granted':
        qs = qs.filter(access_granted=True)
    elif active_filter == 'denied':
        qs = qs.filter(access_granted=False)

    total = qs.count()
    offset = (page - 1) * PER_PAGE
    access_logs = qs[offset:offset + PER_PAGE]
    has_more = total > offset + PER_PAGE

    # "Load More" fetches the next page as a ready-made HTML fragment
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'html': render_to_string('app/partials/log_cards.html', {'access_logs': access_logs}, request),
            'has_more': has_more,
            'next_page': page + 1,
        })

    return render(request, 'app/logs.html', {
        'access_logs': access_logs,
        'active_page': 'logs',
        'active_filter': active_filter,
        'has_more': has_more,
        'next_page': page + 1,
        'total': total,
        'denied_count': AccessLog.objects.filter(device=device, access_granted=False).count(),
    })
