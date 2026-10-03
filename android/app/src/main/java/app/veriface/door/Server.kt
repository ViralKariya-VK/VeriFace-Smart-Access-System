package app.veriface.door

import java.net.HttpURLConnection
import java.net.Inet4Address
import java.net.NetworkInterface
import java.net.URL
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/** Finding and checking VeriFace servers. All functions block — call off the main thread. */
object Server {

    /** Turn whatever the user typed into a clean base URL. */
    fun normalize(input: String): String? {
        val s = input.trim().trimEnd('/')
        if (s.isEmpty()) return null
        if (s.startsWith("http://") || s.startsWith("https://")) return s

        val authority = s.substringBefore('/')
        val rest = s.removePrefix(authority)
        val host = authority.substringBefore(':')
        val isLocal = host.matches(Regex("""\d{1,3}(\.\d{1,3}){3}""")) ||
            host.endsWith(".local") || !host.contains('.')

        // A bare LAN address means plain HTTP on VeriFace's default port;
        // anything else (a tunnel / domain) is HTTPS.
        return when {
            !isLocal -> "https://$s"
            authority.contains(':') -> "http://$s"
            else -> "http://$authority:8000$rest"
        }
    }

    /** True if [base] answers like a VeriFace server. */
    fun isVeriFace(base: String, timeoutMs: Int = 4000): Boolean = try {
        val c = URL("$base/healthz").openConnection() as HttpURLConnection
        c.connectTimeout = timeoutMs
        c.readTimeout = timeoutMs
        c.instanceFollowRedirects = false
        try {
            c.responseCode == 200 && c.inputStream.bufferedReader().readText().contains("veriface")
        } finally {
            c.disconnect()
        }
    } catch (e: Exception) {
        false
    }

    /** This phone's Wi-Fi/LAN IPv4 address, e.g. 192.168.1.42 */
    private fun localAddress(): String? =
        NetworkInterface.getNetworkInterfaces().toList()
            .filter { it.isUp && !it.isLoopback }
            .flatMap { it.inetAddresses.toList() }
            .filterIsInstance<Inet4Address>()
            .firstOrNull { it.isSiteLocalAddress }
            ?.hostAddress

    /**
     * Probe every address on the phone's /24 for a VeriFace server on [port].
     * Needs no server-side setup (mDNS doesn't pass through Docker's bridge network).
     */
    fun scanLocalNetwork(port: Int = 8000): List<String> {
        val ip = localAddress() ?: return emptyList()
        val prefix = ip.substringBeforeLast('.')
        val pool = Executors.newFixedThreadPool(64)
        val found = java.util.Collections.synchronizedList(mutableListOf<String>())
        for (i in 1..254) {
            pool.execute {
                val base = "http://$prefix.$i:$port"
                if (isVeriFace(base, 700)) found.add(base)
            }
        }
        pool.shutdown()
        pool.awaitTermination(30, TimeUnit.SECONDS)
        return found.toList()
    }
}
