// ── Camera Status Polling ─────────────────────
function pollCameraStatus() {
    fetch('/api/camera-status/')
        .then(r => r.json())
        .then(data => {
            const banner = document.getElementById('camera-alert');
            const text = document.getElementById('camera-alert-text');
            if (!banner) return;

            if (data.status === 'blocked') {
                banner.className = 'alert-banner warning show';
                text.textContent = '⚠ Camera appears to be blocked';
            } else if (data.status === 'offline') {
                banner.className = 'alert-banner danger show';
                text.textContent = '⚠ Camera is offline';
            } else {
                banner.className = 'alert-banner';
            }
        })
        .catch(() => {});
}

// Poll every 10 seconds
pollCameraStatus();
setInterval(pollCameraStatus, 10000);


// ── Push Notification Setup ───────────────────
function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding)
        .replace(/-/g, '+')
        .replace(/_/g, '/');
    const rawData = window.atob(base64);
    return Uint8Array.from([...rawData].map(c => c.charCodeAt(0)));
}

async function setupPushNotifications() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;

    try {
        const keyRes = await fetch('/api/push/vapid-key/');
        const { public_key } = await keyRes.json();

        const reg = await navigator.serviceWorker.ready;

        const permission = await Notification.requestPermission();
        if (permission !== 'granted') return;

        // Always unsubscribe old and create fresh
        // This handles ngrok URL changes automatically
        const existing = await reg.pushManager.getSubscription();
        if (existing) await existing.unsubscribe();

        const subscription = await reg.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(public_key)
        });

        await fetch('/api/push/subscribe/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(subscription.toJSON())
        });

        console.log('✅ Push subscription refreshed');

    } catch(e) {
        console.error('Push setup failed:', e.message);
    }
}