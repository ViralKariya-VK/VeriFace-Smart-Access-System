package app.veriface.door

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.webkit.CookieManager
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/**
 * Watches the VeriFace server for alerts (door opened, guest entered, camera blocked…).
 *
 * Web Push needs a browser service worker, which Android WebViews lack, so this
 * foreground service polls /api/events/ with the same login the WebView holds.
 */
class EventService : Service() {

    @Volatile private var running = false
    private var worker: Thread? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        createChannels()
        val ongoing = NotificationCompat.Builder(this, CH_SERVICE)
            .setSmallIcon(android.R.drawable.ic_lock_idle_lock)
            .setContentTitle("VeriFace is watching your door")
            .setContentText("Tap to open")
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_MIN)
            .setContentIntent(openApp())
            .build()
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(ID_SERVICE, ongoing, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
        } else {
            startForeground(ID_SERVICE, ongoing)
        }

        if (!running) {
            running = true
            worker = Thread(::loop, "veriface-events").also { it.isDaemon = true; it.start() }
        }
        return START_STICKY
    }

    override fun onDestroy() {
        running = false
        worker?.interrupt()
        super.onDestroy()
    }

    private fun loop() {
        var failures = 0
        while (running) {
            try {
                poll()
                failures = 0
            } catch (e: InterruptedException) {
                return
            } catch (e: Exception) {
                failures++ // server unreachable (off Wi-Fi, restarting…) — back off, keep trying
            }
            try { Thread.sleep(if (failures == 0) 5_000L else minOf(60_000L, 5_000L * failures)) }
            catch (e: InterruptedException) { return }
        }
    }

    private fun poll() {
        val base = Prefs.serverUrl(this) ?: return
        val cookie = CookieManager.getInstance().getCookie(base) ?: return // not signed in yet

        val last = Prefs.lastEventId(this)
        val url = if (last < 0) "$base/api/events/" else "$base/api/events/?after=$last"

        val c = URL(url).openConnection() as HttpURLConnection
        c.connectTimeout = 6000
        c.readTimeout = 8000
        c.instanceFollowRedirects = false // a redirect means "signed out" — don't follow to the login page
        c.setRequestProperty("Cookie", cookie)
        try {
            if (c.responseCode != 200) return
            val json = JSONObject(c.inputStream.bufferedReader().readText())
            val latest = json.optLong("latest", 0)
            if (last < 0) { Prefs.setLastEventId(this, latest); return } // first sync: no history replay

            val events = json.optJSONArray("events") ?: return
            for (i in 0 until events.length()) {
                val e = events.getJSONObject(i)
                notify(e.getLong("id").toInt(), e.getString("message"))
                Prefs.setLastEventId(this, e.getLong("id"))
            }
        } finally {
            c.disconnect()
        }
    }

    private fun notify(id: Int, message: String) {
        val n = NotificationCompat.Builder(this, CH_ALERTS)
            .setSmallIcon(android.R.drawable.ic_lock_idle_lock)
            .setContentTitle("VeriFace")
            .setContentText(message)
            .setStyle(NotificationCompat.BigTextStyle().bigText(message))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(Notification.CATEGORY_MESSAGE)
            .setAutoCancel(true)
            .setContentIntent(openApp())
            .build()
        (getSystemService(NOTIFICATION_SERVICE) as NotificationManager).notify(1000 + id, n)
    }

    private fun openApp() = PendingIntent.getActivity(
        this, 0, Intent(this, MainActivity::class.java),
        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
    )

    private fun createChannels() {
        if (Build.VERSION.SDK_INT < 26) return
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        nm.createNotificationChannel(
            NotificationChannel(CH_SERVICE, "Background watching", NotificationManager.IMPORTANCE_MIN)
        )
        nm.createNotificationChannel(
            NotificationChannel(CH_ALERTS, "Door alerts", NotificationManager.IMPORTANCE_HIGH)
        )
    }

    companion object {
        private const val CH_SERVICE = "service"
        private const val CH_ALERTS = "alerts"
        private const val ID_SERVICE = 1

        /** Start or stop the service so it matches the user's settings. */
        fun syncWithPrefs(c: Context) {
            val wanted = Prefs.notificationsEnabled(c) && Prefs.serverUrl(c) != null
            val intent = Intent(c, EventService::class.java)
            if (wanted && canNotify(c)) {
                try { ContextCompat.startForegroundService(c, intent) } catch (e: Exception) { /* background start blocked */ }
            } else {
                c.stopService(intent)
            }
        }

        private fun canNotify(c: Context) = Build.VERSION.SDK_INT < 33 ||
            ContextCompat.checkSelfPermission(c, android.Manifest.permission.POST_NOTIFICATIONS) ==
            PackageManager.PERMISSION_GRANTED
    }
}
