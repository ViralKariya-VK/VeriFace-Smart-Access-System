from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .generator import generate_guest_qr
from apps.core.models import Guest


@login_required
def qr_generator(request):
    """
    Only owners can generate guest QR codes.
    Members can view previously generated QRs but not create new ones.

    Why owner-only creation?
    You don't want a family member giving random people access
    without the owner knowing. Owner controls guest access.
    """
    profile = request.user.profile
    # All guests created by any member of this device
    guests = Guest.objects.filter(
        created_by__device=profile.device
    ).order_by('-created_at')

    if request.method == 'POST':
        if not profile.is_owner():
            messages.error(request, "Only the device owner can generate guest QR codes.")
            return redirect('qr_generator')

        guest_name = request.POST.get('guest_name', '').strip()

        # Quick mode — just minutes
        quick_minutes = request.POST.get('quick_minutes', '').strip()

        # Extended mode — days + hours + minutes
        days = int(request.POST.get('days', 0) or 0)
        hours = int(request.POST.get('hours', 0) or 0)
        minutes = int(request.POST.get('minutes', 0) or 0)

        # If quick_minutes provided, override extended
        if quick_minutes:
            try:
                minutes = int(quick_minutes)
                days = hours = 0
            except ValueError:
                pass

        # Count limit — empty means unlimited
        max_uses_str = request.POST.get('max_uses', '').strip()
        max_uses = int(max_uses_str) if max_uses_str else None

        if not guest_name:
            messages.error(request, "Please enter a guest name.")
            return render(request, 'app/qr_generator.html', {
                'guests': guests, 'profile': profile,
                'active_page': 'qr_generator'
            })

        total = (days * 24 * 60) + (hours * 60) + minutes
        if total <= 0:
            messages.error(request, "Please set a valid duration.")
            return render(request, 'app/qr_generator.html', {
                'guests': guests, 'profile': profile,
                'active_page': 'qr_generator'
            })

        try:
            guest = generate_guest_qr(
                profile, guest_name,
                days=days, hours=hours, minutes=minutes,
                max_uses=max_uses
            )
            messages.success(request, f"QR generated for {guest_name}!")
            guests = Guest.objects.filter(
                created_by__device=profile.device
            ).order_by('-created_at')
            return render(request, 'app/qr_generator.html', {
                'guests': guests,
                'profile': profile,
                'active_page': 'qr_generator',
                'new_guest': guest,
            })
        except Exception as e:
            messages.error(request, str(e))

    return render(request, 'app/qr_generator.html', {
        'guests': guests,
        'profile': profile,
        'active_page': 'qr_generator',
    })


@login_required
def delete_guest(request, guest_id):
    """
    Owner can revoke guest access by deleting their QR.
    Once deleted, the QR code won't decrypt against any active guest — invalid.
    """
    if not request.user.profile.is_owner():
        messages.error(request, "Only the owner can revoke guest access.")
        return redirect('qr_generator')

    try:
        guest = Guest.objects.get(
            id=guest_id,
            created_by__device=request.user.profile.device
        )
        guest.delete()
        messages.success(request, "Guest access revoked.")
    except Guest.DoesNotExist:
        messages.error(request, "Guest not found.")

    return redirect('qr_generator')