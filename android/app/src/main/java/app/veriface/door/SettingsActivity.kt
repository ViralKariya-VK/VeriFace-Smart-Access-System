package app.veriface.door

import android.app.Activity
import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.net.Uri
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.widget.Button
import android.widget.LinearLayout
import android.widget.Switch
import android.widget.TextView

/** Native app settings: which server, and whether to watch for alerts in the background. */
class SettingsActivity : Activity() {

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    private fun label(text: String, size: Float = 14f, color: String = "#8FA6BA") = TextView(this).apply {
        this.text = text; textSize = size; setTextColor(Color.parseColor(color))
        setPadding(0, dp(8), 0, dp(8))
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.parseColor("#080C12"))
            setPadding(dp(24), dp(48), dp(24), dp(24))
        }

        root.addView(label("Settings", 24f, "#FFFFFF").apply { typeface = Typeface.DEFAULT_BOLD })

        root.addView(label("SERVER", 11f, "#5A7A94").apply { setPadding(0, dp(24), 0, 0) })
        root.addView(label(Prefs.serverUrl(this) ?: "Not connected", 15f, "#FFFFFF"))
        root.addView(Button(this).apply {
            text = "Change server"
            setOnClickListener {
                startActivity(Intent(this@SettingsActivity, ConnectActivity::class.java))
                finish()
            }
        })

        root.addView(label("ALERTS", 11f, "#5A7A94").apply { setPadding(0, dp(24), 0, 0) })
        root.addView(Switch(this).apply {
            text = "Notify me when the door opens or the camera has a problem"
            setTextColor(Color.WHITE)
            isChecked = Prefs.notificationsEnabled(this@SettingsActivity)
            setOnCheckedChangeListener { _, on ->
                Prefs.setNotificationsEnabled(this@SettingsActivity, on)
                EventService.syncWithPrefs(this@SettingsActivity)
            }
        })
        root.addView(label(
            "Alerts work by keeping a small connection to your server open. If they stop arriving, " +
                "let VeriFace run without battery restrictions:", 12f, "#5A7A94"))
        root.addView(Button(this).apply {
            text = "Battery settings"
            setOnClickListener {
                val pm = getSystemService(POWER_SERVICE) as PowerManager
                val intent = if (!pm.isIgnoringBatteryOptimizations(packageName))
                    Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS)
                        .setData(Uri.parse("package:$packageName"))
                else Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)
                try { startActivity(intent) } catch (e: Exception) {
                    startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
                }
            }
        })

        root.addView(label("VeriFace Android ${BuildConfigVersion.name(this)}", 12f, "#3F5870").apply {
            setPadding(0, dp(32), 0, 0)
        })

        setContentView(root)
    }
}
