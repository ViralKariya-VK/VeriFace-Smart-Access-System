plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// CI passes these; locally they default so `./gradlew assembleDebug` just works.
val appVersionName = (project.findProperty("versionName") as String?) ?: "1.0.0"
val appVersionCode = ((project.findProperty("versionCode") as String?) ?: "1").toInt()

android {
    namespace = "app.veriface.door"
    compileSdk = 34

    defaultConfig {
        applicationId = "app.veriface.door"
        minSdk = 24
        targetSdk = 34
        versionCode = appVersionCode
        versionName = appVersionName
    }

    // Release signing comes from environment variables so no secret is ever
    // committed. Without them the release build falls back to the debug key —
    // installable, but it can't be updated by an APK signed with a different key.
    val keystorePath = System.getenv("KEYSTORE_FILE")
    signingConfigs {
        if (keystorePath != null) {
            create("release") {
                storeFile = file(keystorePath)
                storePassword = System.getenv("KEYSTORE_PASSWORD")
                keyAlias = System.getenv("KEY_ALIAS")
                keyPassword = System.getenv("KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = if (keystorePath != null) signingConfigs.getByName("release")
                            else signingConfigs.getByName("debug")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
}
