package app.veriface.door

import android.content.Context

/** Everything the app remembers: where the server is and whether to watch for alerts. */
object Prefs {
    private const val FILE = "veriface"

    private fun sp(c: Context) = c.getSharedPreferences(FILE, Context.MODE_PRIVATE)

    fun serverUrl(c: Context): String? = sp(c).getString("server_url", null)
    fun setServerUrl(c: Context, url: String?) = sp(c).edit().putString("server_url", url).apply()

    fun notificationsEnabled(c: Context) = sp(c).getBoolean("notifications", true)
    fun setNotificationsEnabled(c: Context, on: Boolean) =
        sp(c).edit().putBoolean("notifications", on).apply()

    /** Last alert id already shown; -1 means "unknown, sync to the server's latest first". */
    fun lastEventId(c: Context): Long = sp(c).getLong("last_event", -1)
    fun setLastEventId(c: Context, id: Long) = sp(c).edit().putLong("last_event", id).apply()
}
