import shutil
import tempfile
from unittest import mock

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.core.models import AccessLog, Device, Event, Profile

TEST_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEST_MEDIA)
class DoorFixture(TestCase):
    """A device with an owner and a member, plus a second, unrelated device."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA, ignore_errors=True)

    def setUp(self):
        self.device = Device.objects.create(device_id='DOOR-T1', name='Front', ip_address='0.0.0.0', camera_source='0')
        self.other = Device.objects.create(device_id='DOOR-T2', name='Back', ip_address='0.0.0.0', camera_source='0')
        self.owner = self._user('owner', self.device, 'owner')
        self.member = self._user('member', self.device, 'member')
        self.stranger = self._user('stranger', self.other, 'owner')

    def _user(self, name, device, role):
        u = User.objects.create_user(name, f'{name}@x.com', 'pw-12345678')
        p = Profile.objects.create(user=u, device=device, role=role)
        p.face_image.save(f'{name}.jpg', ContentFile(b'jpg'), save=False)
        p.face_embedding.save(f'{name}_embedding.npy', ContentFile(b'npy'), save=False)
        p.save()
        return u

    def login(self, user):
        self.client.login(username=user.username, password='pw-12345678')


class ManageTests(DoorFixture):
    def test_member_cannot_manage(self):
        self.login(self.member)
        r = self.client.post(reverse('manage'), {'action': 'clear_logs'})
        self.assertRedirects(r, reverse('user_profile'), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse('manage')).status_code, 302)

    @mock.patch('apps.camera.manager.camera_manager.restart_camera')
    def test_owner_updates_camera(self, restart):
        self.login(self.owner)
        self.client.post(reverse('manage'), {'action': 'camera', 'camera_source': 'rtsp://cam/stream'})
        self.device.refresh_from_db()
        self.assertEqual(self.device.camera_source, 'rtsp://cam/stream')
        restart.assert_called_once_with('DOOR-T1', 'rtsp://cam/stream')  # live stream switches without a restart

    def test_owner_removes_member_and_their_biometrics(self):
        self.login(self.owner)
        pid = self.member.profile.id
        self.client.post(reverse('manage'), {'action': 'remove_member', 'profile_id': pid})
        self.assertFalse(User.objects.filter(username='member').exists())
        self.assertFalse(Profile.objects.filter(id=pid).exists())

    def test_owner_cannot_remove_self(self):
        self.login(self.owner)
        self.client.post(reverse('manage'), {'action': 'remove_member', 'profile_id': self.owner.profile.id})
        self.assertTrue(User.objects.filter(username='owner').exists())

    def test_cannot_remove_member_of_another_door(self):
        self.login(self.owner)
        self.client.post(reverse('manage'), {'action': 'remove_member', 'profile_id': self.stranger.profile.id})
        self.assertTrue(User.objects.filter(username='stranger').exists())

    def test_clear_logs_only_touches_own_door(self):
        AccessLog.objects.create(device=self.device, access_type='face', access_granted=True)
        AccessLog.objects.create(device=self.other, access_type='face', access_granted=True)
        self.login(self.owner)
        self.client.post(reverse('manage'), {'action': 'clear_logs'})
        self.assertEqual(AccessLog.objects.filter(device=self.device).count(), 0)
        self.assertEqual(AccessLog.objects.filter(device=self.other).count(), 1)

    def test_unknown_alert_toggle(self):
        self.login(self.owner)
        self.client.post(reverse('manage'), {'action': 'alerts'})  # checkbox absent = off
        self.device.refresh_from_db()
        self.assertFalse(self.device.alert_unknown)


class EventsApiTests(DoorFixture):
    def test_requires_login(self):
        self.assertEqual(self.client.get(reverse('events_since')).status_code, 302)

    def test_first_sync_returns_latest_without_history(self):
        Event.objects.create(device=self.device, message='old')
        self.login(self.owner)
        data = self.client.get(reverse('events_since')).json()
        self.assertEqual(data['events'], [])
        self.assertGreater(data['latest'], 0)

    def test_returns_only_newer_events_for_own_door(self):
        e1 = Event.objects.create(device=self.device, message='one')
        Event.objects.create(device=self.other, message='not mine')
        e2 = Event.objects.create(device=self.device, message='two')
        self.login(self.member)
        data = self.client.get(reverse('events_since'), {'after': e1.id}).json()
        self.assertEqual([e['message'] for e in data['events']], ['two'])
        self.assertEqual(data['latest'], e2.id)

    def test_alerts_create_events_without_any_push_subscription(self):
        from apps.notifications.push import send_push_to_device
        send_push_to_device(self.device.device_id, 'Door opened by owner')
        self.assertEqual(Event.objects.filter(device=self.device).count(), 1)


class LogsTests(DoorFixture):
    def setUp(self):
        super().setUp()
        AccessLog.objects.create(device=self.device, access_type='face', access_granted=True)
        AccessLog.objects.create(device=self.device, access_type='face', access_granted=False)
        self.login(self.owner)

    def test_filters(self):
        self.assertEqual(self.client.get(reverse('logs')).context['total'], 2)
        self.assertEqual(self.client.get(reverse('logs'), {'filter': 'granted'}).context['total'], 1)
        self.assertEqual(self.client.get(reverse('logs'), {'filter': 'denied'}).context['total'], 1)

    def test_ajax_load_more_returns_json_fragment(self):
        r = self.client.get(reverse('logs'), {'page': 1}, headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertIn('html', r.json())
        self.assertFalse(r.json()['has_more'])


class SetupGuardTests(TestCase):
    def test_setup_closed_once_a_device_exists(self):
        Device.objects.create(device_id='D', name='n', ip_address='0.0.0.0', camera_source='0')
        self.assertEqual(self.client.get(reverse('setup')).status_code, 302)

    def test_setup_refused_from_public_address(self):
        r = self.client.get(reverse('setup'), HTTP_CF_CONNECTING_IP='8.8.8.8')
        self.assertEqual(r.status_code, 403)

    def test_setup_open_from_home_network(self):
        r = self.client.get(reverse('setup'), REMOTE_ADDR='192.168.1.20')
        self.assertEqual(r.status_code, 200)
