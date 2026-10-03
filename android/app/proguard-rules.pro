# The WebView JavaScript bridge is looked up by reflection
-keepclassmembers class app.veriface.door.MainActivity$Bridge {
    @android.webkit.JavascriptInterface <methods>;
}
