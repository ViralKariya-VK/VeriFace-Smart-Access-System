package app.veriface.door

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.MediaStore
import android.view.Gravity
import android.view.View
import android.webkit.CookieManager
import android.webkit.JavascriptInterface
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import java.io.File

/** Hosts the VeriFace web app. The server does all the work; this is the phone-side shell. */
class MainActivity : Activity() {

    private lateinit var web: WebView
    private lateinit var errorView: LinearLayout
    private lateinit var errorText: TextView
    private var serverUrl: String = ""

    private var filePathCallback: ValueCallback<Array<Uri>>? = null
    private var cameraOutput: Uri? = null

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val saved = Prefs.serverUrl(this)
        if (saved == null) {
            startActivity(Intent(this, ConnectActivity::class.java))
            finish()
            return
        }
        serverUrl = saved

        web = WebView(this).apply {
            setBackgroundColor(Color.parseColor("#080C12"))
            settings.apply {
                javaScriptEnabled = true
                domStorageEnabled = true
                mediaPlaybackRequiresUserGesture = false
                mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
                // Lets the web app know it's inside the Android app (see user.html)
                userAgentString = "$userAgentString VeriFaceApp/${BuildConfigVersion.name(this@MainActivity)}"
            }
            val wv = this
            CookieManager.getInstance().apply {
                setAcceptCookie(true)
                setAcceptThirdPartyCookies(wv, false)
            }
            addJavascriptInterface(Bridge(), "VeriFaceApp")
            webViewClient = Client()
            webChromeClient = Chrome()
        }

        errorText = TextView(this).apply {
            setTextColor(Color.parseColor("#8FA6BA")); textSize = 14f; gravity = Gravity.CENTER
            setPadding(48, 0, 48, 32)
        }
        fun errBtn(label: String, onClick: () -> Unit) = Button(this).apply {
            text = label; setOnClickListener { onClick() }
        }
        errorView = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setBackgroundColor(Color.parseColor("#080C12"))
            visibility = View.GONE
            addView(TextView(this@MainActivity).apply {
                text = "Can't reach your door"
                setTextColor(Color.WHITE); textSize = 20f; gravity = Gravity.CENTER
                setPadding(0, 0, 0, 16)
            })
            addView(errorText)
            addView(errBtn("Retry") { errorView.visibility = View.GONE; web.reload() })
            addView(errBtn("Change server") {
                startActivity(Intent(this@MainActivity, ConnectActivity::class.java))
            })
        }

        setContentView(FrameLayout(this).apply {
            setBackgroundColor(Color.parseColor("#080C12"))
            addView(web, FrameLayout.LayoutParams(-1, -1))
            addView(errorView, FrameLayout.LayoutParams(-1, -1))
        })

        if (savedInstanceState != null) web.restoreState(savedInstanceState) else web.loadUrl(serverUrl)

        askNotificationPermission()
    }

    override fun onResume() {
        super.onResume()
        if (!::web.isInitialized) return
        // The server may have been changed from Settings
        val current = Prefs.serverUrl(this)
        if (current != null && current != serverUrl) {
            serverUrl = current
            web.loadUrl(serverUrl)
        }
        web.onResume()
        EventService.syncWithPrefs(this)
    }

    override fun onPause() {
        super.onPause()
        if (::web.isInitialized) {
            web.onPause()
            CookieManager.getInstance().flush() // the alert service reuses this login
        }
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        if (::web.isInitialized) web.saveState(outState)
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (::web.isInitialized && web.canGoBack()) web.goBack() else super.onBackPressed()
    }

    private fun askNotificationPermission() {
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
            != PackageManager.PERMISSION_GRANTED
        ) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
        }
    }

    override fun onRequestPermissionsResult(code: Int, perms: Array<out String>, results: IntArray) {
        super.onRequestPermissionsResult(code, perms, results)
        EventService.syncWithPrefs(this)
    }

    // ── JavaScript bridge ────────────────────────────────────────────────
    inner class Bridge {
        @JavascriptInterface
        fun openSettings() {
            runOnUiThread { startActivity(Intent(this@MainActivity, SettingsActivity::class.java)) }
        }
    }

    // ── Navigation / errors ──────────────────────────────────────────────
    private inner class Client : WebViewClient() {
        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
            val target = request.url
            val base = Uri.parse(serverUrl)
            if (target.host == base.host) return false
            // Anything off the server (links, mailto…) opens outside the app
            return try { startActivity(Intent(Intent.ACTION_VIEW, target)); true } catch (e: Exception) { true }
        }

        override fun onReceivedError(view: WebView, req: WebResourceRequest, err: WebResourceError) {
            if (req.isForMainFrame) {
                errorText.text = "$serverUrl\n\n${err.description}\n\nCheck you're on the same Wi-Fi as the server, " +
                    "or use your remote (tunnel) address in Settings."
                errorView.visibility = View.VISIBLE
            }
        }

        override fun onPageFinished(view: WebView, url: String) {
            if (errorView.visibility != View.VISIBLE) CookieManager.getInstance().flush()
        }
    }

    // ── File chooser: choose a photo or take a selfie (face enrolment) ───
    private inner class Chrome : WebChromeClient() {
        override fun onShowFileChooser(
            view: WebView, callback: ValueCallback<Array<Uri>>, params: FileChooserParams
        ): Boolean {
            filePathCallback?.onReceiveValue(null)
            filePathCallback = callback

            val pick = Intent(Intent.ACTION_GET_CONTENT).apply {
                addCategory(Intent.CATEGORY_OPENABLE)
                type = "image/*"
            }
            val extras = mutableListOf<Intent>()
            try {
                val dir = File(cacheDir, "camera").apply { mkdirs() }
                val photo = File(dir, "selfie_${System.currentTimeMillis()}.jpg")
                cameraOutput = FileProvider.getUriForFile(this@MainActivity, "$packageName.files", photo)
                extras += Intent(MediaStore.ACTION_IMAGE_CAPTURE).apply {
                    putExtra(MediaStore.EXTRA_OUTPUT, cameraOutput)
                    addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
                }
            } catch (e: Exception) { cameraOutput = null }

            val chooser = Intent(Intent.ACTION_CHOOSER).apply {
                putExtra(Intent.EXTRA_INTENT, pick)
                putExtra(Intent.EXTRA_TITLE, "Choose a photo")
                putExtra(Intent.EXTRA_INITIAL_INTENTS, extras.toTypedArray())
            }
            return try {
                startActivityForResult(chooser, REQ_FILE); true
            } catch (e: Exception) {
                filePathCallback = null; false
            }
        }
    }

    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != REQ_FILE) return
        val result: Array<Uri>? = if (resultCode == RESULT_OK) {
            // A camera capture returns no data — the photo is at our own output Uri
            val picked = data?.data
            when {
                picked != null -> arrayOf(picked)
                cameraOutput != null -> arrayOf(cameraOutput!!)
                else -> null
            }
        } else null
        filePathCallback?.onReceiveValue(result)
        filePathCallback = null
        cameraOutput = null
    }

    companion object { private const val REQ_FILE = 42 }
}

/** Version string for the user-agent without needing generated BuildConfig. */
object BuildConfigVersion {
    fun name(c: android.content.Context): String = try {
        c.packageManager.getPackageInfo(c.packageName, 0).versionName ?: "0"
    } catch (e: Exception) { "0" }
}
