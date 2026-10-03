package app.veriface.door

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** Restart alert watching after the phone reboots. */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED) EventService.syncWithPrefs(context)
    }
}
