package app.veriface.door

import android.app.Activity
import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.view.inputmethod.EditorInfo
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import kotlin.concurrent.thread

/** First-run screen: find the VeriFace server on the Wi-Fi, or type its address. */
class ConnectActivity : Activity() {

    private lateinit var status: TextView
    private lateinit var results: LinearLayout
    private lateinit var scanBtn: Button
    private lateinit var input: EditText
    private lateinit var connectBtn: Button

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    private fun pill(color: Int, stroke: Int? = null) = GradientDrawable().apply {
        cornerRadius = dp(12).toFloat()
        setColor(color)
        if (stroke != null) setStroke(dp(1), stroke)
    }

    private fun styledButton(text: String, primary: Boolean) = Button(this).apply {
        this.text = text.uppercase()
        typeface = Typeface.MONOSPACE
        letterSpacing = 0.08f
        setTextColor(if (primary) Color.parseColor("#06101A") else Color.parseColor("#00D4FF"))
        background = if (primary) pill(Color.parseColor("#5BD6FF"))
                     else pill(Color.TRANSPARENT, Color.parseColor("#2A4060"))
        stateListAnimator = null
        layoutParams = LinearLayout.LayoutParams(-1, dp(52)).apply { topMargin = dp(12) }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.parseColor("#080C12"))
            setPadding(dp(24), dp(56), dp(24), dp(24))
        }

        root.addView(TextView(this).apply {
            text = "VERIFACE"
            setTextColor(Color.WHITE)
            textSize = 30f
            typeface = Typeface.create("sans-serif-black", Typeface.NORMAL)
            letterSpacing = 0.12f
            gravity = Gravity.CENTER
        })
        root.addView(TextView(this).apply {
            text = "CONNECT TO YOUR DOOR"
            setTextColor(Color.parseColor("#5A7A94"))
            typeface = Typeface.MONOSPACE
            textSize = 12f
            letterSpacing = 0.15f
            gravity = Gravity.CENTER
            setPadding(0, dp(6), 0, dp(36))
        })

        scanBtn = styledButton("Find my VeriFace", primary = true)
        scanBtn.setOnClickListener { scan() }
        root.addView(scanBtn)

        status = TextView(this).apply {
            setTextColor(Color.parseColor("#8FA6BA"))
            typeface = Typeface.MONOSPACE
            textSize = 12f
            setPadding(0, dp(14), 0, dp(6))
        }
        root.addView(status)

        results = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        root.addView(results)

        root.addView(TextView(this).apply {
            text = "OR ENTER THE ADDRESS"
            setTextColor(Color.parseColor("#5A7A94"))
            typeface = Typeface.MONOSPACE
            textSize = 11f
            letterSpacing = 0.12f
            setPadding(0, dp(28), 0, dp(8))
        })

        input = EditText(this).apply {
            hint = "192.168.1.50:8000  or  https://….trycloudflare.com"
            setHintTextColor(Color.parseColor("#3A5068"))
            setTextColor(Color.WHITE)
            textSize = 14f
            inputType = InputType.TYPE_TEXT_VARIATION_URI
            imeOptions = EditorInfo.IME_ACTION_GO
            isSingleLine = true
            setPadding(dp(16), 0, dp(16), 0)
            background = pill(Color.parseColor("#0F1722"), Color.parseColor("#1E2D40"))
            layoutParams = LinearLayout.LayoutParams(-1, dp(52))
            setText(Prefs.serverUrl(this@ConnectActivity) ?: "")
            setOnEditorActionListener { _, _, _ -> connect(text.toString()); true }
        }
        root.addView(input)

        connectBtn = styledButton("Connect", primary = false)
        connectBtn.setOnClickListener { connect(input.text.toString()) }
        root.addView(connectBtn)

        root.addView(TextView(this).apply {
            text = "Don't have a server yet? Install VeriFace on a Raspberry Pi, old laptop or mini PC " +
                "with Docker — see the project README on GitHub."
            setTextColor(Color.parseColor("#3F5870"))
            textSize = 12f
            setPadding(0, dp(28), 0, 0)
        })

        setContentView(ScrollView(this).apply {
            setBackgroundColor(Color.parseColor("#080C12"))
            isFillViewport = true
            addView(root)
        })

        scan() // try automatically on open
    }

    private fun scan() {
        scanBtn.isEnabled = false
        results.removeAllViews()
        status.text = "Scanning your Wi-Fi…"
        thread {
            val found = try { Server.scanLocalNetwork() } catch (e: Exception) { emptyList() }
            runOnUiThread {
                scanBtn.isEnabled = true
                if (found.isEmpty()) {
                    status.text = "No server found on this Wi-Fi. Make sure the phone is on the same " +
                        "network as the VeriFace machine, or enter its address below."
                } else {
                    status.text = if (found.size == 1) "Found it:" else "Found ${found.size} servers:"
                    found.forEach { base ->
                        results.addView(styledButton(base.removePrefix("http://"), primary = false).apply {
                            setOnClickListener { save(base) }
                        })
                    }
                    if (found.size == 1) save(found[0])
                }
            }
        }
    }

    private fun connect(raw: String) {
        val base = Server.normalize(raw)
        if (base == null) { status.text = "Enter an address first."; return }
        status.text = "Checking $base …"
        connectBtn.isEnabled = false
        thread {
            val ok = Server.isVeriFace(base, 8000)
            runOnUiThread {
                connectBtn.isEnabled = true
                if (ok) save(base) else status.text =
                    "Couldn't reach a VeriFace server at $base. Check the address and that the server is running."
            }
        }
    }

    private fun save(base: String) {
        Prefs.setServerUrl(this, base)
        Prefs.setLastEventId(this, -1)
        startActivity(Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP))
        finish()
    }
}
