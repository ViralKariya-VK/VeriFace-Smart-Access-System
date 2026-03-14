from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from apps.core.models import AccessLog


@login_required
def logs(request):
    device = request.user.profile.device
    
    page = int(request.GET.get('page', 1))
    per_page = 10
    offset = (page - 1) * per_page

    all_logs = AccessLog.objects.filter(
        device=device
    ).select_related('profile', 'profile__user')

    total = all_logs.count()
    access_logs = all_logs[offset:offset + per_page]
    has_more = total > (offset + per_page)

    return render(request, 'app/logs.html', {
        'access_logs': access_logs,
        'active_page': 'logs',
        'has_more': has_more,
        'next_page': page + 1,
        'total': total,
    })