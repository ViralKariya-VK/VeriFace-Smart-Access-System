const CACHE = 'veriface-v1';
const SHELL = [
    '/',
    '/static/css/style.css',
    '/static/js/app.js',
];

self.addEventListener('install', e => {
    e.waitUntil(
        caches.open(CACHE).then(c => c.addAll(SHELL))
    );
});

self.addEventListener('fetch', e => {
    // Network first — always get fresh data
    // Cache only as fallback for shell files
    e.respondWith(
        fetch(e.request).catch(() =>
            caches.match(e.request)
        )
    );
});

// Handle push notifications
self.addEventListener('push', e => {
    const data = e.data?.json() || {};
    e.waitUntil(
        self.registration.showNotification(data.title || 'VeriFace', {
            body: data.body,
            icon: data.icon || '/static/icons/icon-192x192.png',
            badge: '/static/icons/icon-192x192.png',
            vibrate: [200, 100, 200],
        })
    );
});