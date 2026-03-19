from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Clear sessions and push subscriptions on server start'

    def handle(self, *args, **kwargs):
        from django.contrib.sessions.models import Session
        from apps.core.models import PushSubscription

        # Clear all sessions — forces everyone to log in fresh
        # Why? Recognition pipelines and push subscriptions are
        # tied to server process memory and browser state.
        # A server restart invalidates both — clean slate is safer
        # than trying to restore stale state.
        session_count = Session.objects.count()
        Session.objects.all().delete()
        self.stdout.write(f"🗑️  Cleared {session_count} sessions")

        # Clear push subscriptions — browser will resubscribe on next login
        # Why? ngrok URL may have changed, VAPID state may be different.
        # Resubscribing is cheap — takes 2 seconds on page load.
        # Keeping stale subscriptions causes silent push failures.
        sub_count = PushSubscription.objects.count()
        PushSubscription.objects.all().delete()
        self.stdout.write(f"🗑️  Cleared {sub_count} push subscriptions")

        self.stdout.write("✅ Startup cleanup complete — all users must re-login")