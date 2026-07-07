#!/usr/bin/env python3
"""
ARIA Mobile — Builder COMPLETO v4.0 (Android, Kotlin) con build automatica
===========================================================================
Genera l'intero progetto Android Studio per ARIA Mobile in
Desktop/AriaMobile e tenta la compilazione (gradlew assembleDebug)
usando il JDK e l'Android SDK già presenti sul sistema (Android Studio
installato).

NOVITÀ v4.0:
- SFERA 3D VIVA NELLA CHAT (stile Jarvis, ma meglio): nucleo luminoso
  che respira, sfera di 150 particelle in rotazione con prospettiva
  reale, 3 anelli orbitali inclinati che precedono nello spazio con
  elettroni luminosi. La sfera FLUTTUA nella chat ed è VIVA: cambia
  colore e velocità in base a quello che fa l'AI —
    * azzurra e calma quando ascolta
    * viola e velocissima quando sta pensando
    * verde quando parla a voce
    * rossa se c'è un errore
- TOCCA LA SFERA per attivare il microfono e parlarle a voce.

NOVITÀ v3.0:
- VOCE CHE PARLA DAVVERO: voce attiva di default, pulsante altoparlante
  nella barra per accenderla/spegnerla al volo, icona 🔊 su ogni
  risposta per riascoltarla, fallback automatico alla lingua di sistema
  se manca la voce italiana, pulizia dei simboli markdown prima della
  lettura.
- 10 STRUMENTI: il pulsante ✨ accanto alla chat apre un pannello con
  Traduttore, Riassunto, Correttore, Matematica, Email, Idee, Chef,
  Coach fitness, Quiz e Barzellette.
- PERSONALITÀ: scegli come si comporta l'AI (Amichevole, Professionale,
  Divertente, Sarcastica, Motivazionale).
- PROVA CONNESSIONE: nelle impostazioni testi la API key con un tocco.
- SCELTA MODELLO RAPIDA: 3 pulsanti per i modelli Groq più usati.
- CONDIVIDI CHAT: esporta la conversazione su WhatsApp/Telegram/ecc.
- Menu ordinato (cronologia, condividi, svuota) e altre rifiniture.

NOVITÀ v2.0:
- SPLASH SCREEN 3D: all'avvio una sfera di particelle 3D vera (proiezione
  prospettica, rotazione continua) con logo ARIA pulsante e la scritta
  "Creator: MaikGost".
- PULSANTE IMPOSTAZIONI IN CHAT (fix del bug segnalato): nella barra in
  alto ora ci sono le icone Impostazioni, Cronologia e Svuota chat.
- NOME ASSISTENTE PERSONALIZZABILE: nelle impostazioni puoi cambiare
  "ARIA" in qualsiasi nome — appare nella barra e l'AI risponde con
  quella identità.
- IL TUO NOME: l'AI ti chiama per nome se lo imposti.
- INPUT VOCALE: pulsante microfono, detti il messaggio e parte da solo.
- RISPOSTE A VOCE (TTS): attivabile dalle impostazioni, l'AI legge le
  risposte in italiano.
- CHAT PERSISTENTE: riaprendo l'app ritrovi la conversazione.
- MEMORIA ATTIVABILE/DISATTIVABILE dalle impostazioni.
- UI SUPER: sfondo sfumato, bolle con gradiente e orari, indicatore
  "sta scrivendo..." con puntini animati, suggerimenti rapidi al primo
  avvio, tieni premuto un messaggio per copiarlo, dialogo di conferma
  per svuotare la chat.

FIX ereditati dalla v1.1:
- GroqClient su API OkHttp 4.x (toMediaType(), toRequestBody(), ecc.)
- @OptIn(ExperimentalMaterial3Api::class) dove serve.
"""

import os, sys, shutil, subprocess, platform, urllib.request, time
from pathlib import Path

class C:
    OK="\033[92m"; WARN="\033[93m"; ERR="\033[91m"
    BOLD="\033[1m"; CYAN="\033[96m"; RESET="\033[0m"

def ok(m):    print(f"{C.OK}  [OK]  {m}{C.RESET}")
def warn(m):  print(f"{C.WARN}  [!]  {m}{C.RESET}")
def err(m):   print(f"{C.ERR}  [X]  {m}{C.RESET}")
def info(m):  print(f"     {m}")
def title(m): print(f"\n{C.BOLD}{C.CYAN}{'-'*64}\n  {m}\n{'-'*64}{C.RESET}")
def step(n, total, m): print(f"{C.CYAN}  [{n}/{total}] {m}{C.RESET}")

DESKTOP     = Path.home() / "Desktop"
PROJECT_DIR = DESKTOP / "AriaMobile"
PKG_ROOT    = "com/aria/mobile"
PKG_UI      = f"{PKG_ROOT}/ui"
PKG_CORE    = f"{PKG_ROOT}/core"
PKG_DATA    = f"{PKG_ROOT}/data"
PKG_NET     = f"{PKG_ROOT}/net"
PKG_VOICE   = f"{PKG_ROOT}/voice"

# ============================================================
#  GRADLE / BUILD FILES
# ============================================================
BUILD_GRADLE_PROJECT = """\
buildscript {
    repositories { google(); mavenCentral() }
    dependencies {
        classpath 'com.android.tools.build:gradle:8.3.2'
        classpath 'org.jetbrains.kotlin:kotlin-gradle-plugin:1.9.23'
    }
}
task clean(type: Delete) { delete rootProject.buildDir }
"""

BUILD_GRADLE_APP = """\
plugins {
    id 'com.android.application'
    id 'org.jetbrains.kotlin.android'
    id 'kotlin-kapt'
}

android {
    namespace 'com.aria.mobile'
    compileSdk 34

    defaultConfig {
        applicationId "com.aria.mobile"
        minSdk 26
        targetSdk 34
        versionCode 4
        versionName "4.0.0"
        multiDexEnabled true
    }

    compileOptions {
        sourceCompatibility JavaVersion.VERSION_17
        targetCompatibility JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }

    buildFeatures { viewBinding true; buildConfig true; compose true }

    composeOptions { kotlinCompilerExtensionVersion "1.5.11" }

    buildTypes {
        debug   { minifyEnabled false; debuggable true }
        release {
            minifyEnabled true
            proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro'
        }
    }

    lint { abortOnError false; checkReleaseBuilds false }

    packagingOptions {
        resources { excludes += ['META-INF/*.kotlin_module', 'META-INF/DEPENDENCIES'] }
    }
}

dependencies {
    implementation 'androidx.core:core-ktx:1.13.1'
    implementation 'androidx.appcompat:appcompat:1.7.0'
    implementation 'com.google.android.material:material:1.12.0'
    implementation 'androidx.constraintlayout:constraintlayout:2.1.4'
    implementation 'androidx.multidex:multidex:2.0.1'

    def lifecycle_version = "2.8.0"
    implementation "androidx.lifecycle:lifecycle-viewmodel-ktx:$lifecycle_version"
    implementation "androidx.lifecycle:lifecycle-livedata-ktx:$lifecycle_version"
    implementation "androidx.lifecycle:lifecycle-runtime-ktx:$lifecycle_version"

    def compose_bom = "2024.05.00"
    implementation platform("androidx.compose:compose-bom:$compose_bom")
    implementation 'androidx.compose.ui:ui'
    implementation 'androidx.compose.ui:ui-tooling-preview'
    implementation 'androidx.compose.material3:material3'
    implementation 'androidx.compose.material:material-icons-extended'
    implementation 'androidx.activity:activity-compose:1.9.0'
    implementation 'androidx.lifecycle:lifecycle-viewmodel-compose:2.8.0'
    debugImplementation 'androidx.compose.ui:ui-tooling'

    def room_version = "2.6.1"
    implementation "androidx.room:room-runtime:$room_version"
    implementation "androidx.room:room-ktx:$room_version"
    kapt "androidx.room:room-compiler:$room_version"

    implementation 'com.squareup.okhttp3:okhttp:4.12.0'
    implementation 'com.squareup.retrofit2:retrofit:2.11.0'
    implementation 'com.squareup.retrofit2:converter-gson:2.11.0'
    implementation 'org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.0'

    implementation 'androidx.datastore:datastore-preferences:1.1.1'
}
"""

SETTINGS_GRADLE = """\
pluginManagement {
    repositories { google(); mavenCentral(); gradlePluginPortal() }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories { google(); mavenCentral() }
}
rootProject.name = "ARIA Mobile"
include ':app'
"""

GRADLE_WRAPPER_PROPS = r"""distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl=https\://services.gradle.org/distributions/gradle-8.6-bin.zip
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists
"""

PROGUARD_RULES = """\
-keep class com.aria.mobile.data.** { *; }
-keep @androidx.room.Entity class * { *; }
-keep @androidx.room.Dao interface * { *; }
-keepclassmembers class * extends androidx.room.RoomDatabase { *; }
-keepattributes *Annotation*
-keepattributes Signature
-dontwarn org.jetbrains.**
"""

MANIFEST = """\
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <uses-permission android:name="android.permission.INTERNET"/>
    <uses-permission android:name="android.permission.RECORD_AUDIO"/>
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS"/>
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE"/>

    <application
        android:name=".AriaApp"
        android:allowBackup="true"
        android:icon="@drawable/ic_aria"
        android:label="ARIA"
        android:roundIcon="@drawable/ic_aria"
        android:supportsRtl="true"
        android:theme="@style/Theme.Aria"
        android:usesCleartextTraffic="true">

        <activity android:name=".ui.SplashActivity" android:exported="true"
            android:theme="@style/Theme.Aria">
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>

        <activity android:name=".ui.MainActivity" android:exported="false"
            android:theme="@style/Theme.Aria"/>

        <activity android:name=".ui.SettingsActivity" android:exported="false"/>
        <activity android:name=".ui.HistoryActivity" android:exported="false"/>

    </application>
</manifest>
"""

# ============================================================
#  KOTLIN SOURCE FILES
# ============================================================
ARIA_APP = r"""package com.aria.mobile

import android.app.Application
import androidx.multidex.MultiDex
import android.content.Context

class AriaApp : Application() {
    override fun attachBaseContext(base: Context) {
        super.attachBaseContext(base)
        MultiDex.install(this)
    }

    override fun onCreate() {
        super.onCreate()
    }

    companion object {
        lateinit var instance: AriaApp
            private set
    }

    init {
        instance = this
    }
}
"""

APP_CONFIG = r"""package com.aria.mobile.core

object AppConfig {
    const val PREFS = "aria_prefs"
    const val PREF_API_KEY = "api_key"
    const val PREF_MODEL = "model_name"
    const val PREF_VOICE_ENABLED = "voice_enabled"
    const val PREF_MEMORY_ENABLED = "memory_enabled"
    const val PREF_ASSISTANT_NAME = "assistant_name"
    const val PREF_USER_NAME = "user_name"
    const val PREF_PERSONALITY = "personality"

    const val CREATOR = "MaikGost"
    const val VERSION = "4.0.0"

    const val COLOR_BG = 0xFF0A0E1A.toInt()
    const val COLOR_SURFACE = 0xFF121826.toInt()
    const val COLOR_PRIMARY = 0xFF7C4DFF.toInt()
    const val COLOR_PRIMARY_LIGHT = 0xFF9C6BFF.toInt()
    const val COLOR_ACCENT = 0xFF00E5FF.toInt()
    const val COLOR_TEXT = 0xFFE8F0FF.toInt()
    const val COLOR_TEXT_DIM = 0xFF5A7A99.toInt()
    const val COLOR_ERROR = 0xFFFF5252.toInt()

    const val DEFAULT_ASSISTANT_NAME = "ARIA"
    const val DEFAULT_PERSONALITY = "Amichevole"
    const val DEFAULT_MODEL = "llama-3.3-70b-versatile"
    const val GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
}
"""

MESSAGE_ENTITY = r"""package com.aria.mobile.data

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "messages")
data class MessageEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val role: String,
    val content: String,
    val timestamp: Long = System.currentTimeMillis(),
    val sessionId: Long = 0L
)
"""

MESSAGE_DAO = r"""package com.aria.mobile.data

import androidx.room.*
import kotlinx.coroutines.flow.Flow

@Dao
interface MessageDao {
    @Insert
    suspend fun insert(message: MessageEntity): Long

    @Query("SELECT * FROM messages ORDER BY timestamp ASC")
    fun getAllLive(): Flow<List<MessageEntity>>

    @Query("SELECT * FROM messages WHERE sessionId = :sid ORDER BY timestamp ASC")
    suspend fun getSession(sid: Long): List<MessageEntity>

    @Query("DELETE FROM messages")
    suspend fun clearAll()

    @Query("SELECT COUNT(*) FROM messages")
    suspend fun count(): Int
}
"""

ARIA_DATABASE = r"""package com.aria.mobile.data

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

@Database(entities = [MessageEntity::class], version = 1, exportSchema = false)
abstract class AriaDatabase : RoomDatabase() {
    abstract fun messageDao(): MessageDao

    companion object {
        @Volatile private var INSTANCE: AriaDatabase? = null

        fun getInstance(context: Context): AriaDatabase {
            return INSTANCE ?: synchronized(this) {
                INSTANCE ?: Room.databaseBuilder(
                    context.applicationContext,
                    AriaDatabase::class.java,
                    "aria_db"
                ).fallbackToDestructiveMigration().build().also { INSTANCE = it }
            }
        }
    }
}
"""

GROQ_CLIENT = r"""package com.aria.mobile.net

import okhttp3.Call
import okhttp3.Callback
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

class GroqClient(private val apiKey: String, private val model: String) {

    private val client = OkHttpClient.Builder()
        .connectTimeout(20, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .build()

    interface ResultCallback {
        fun onResult(text: String)
        fun onError(message: String)
    }

    fun sendMessage(history: List<Pair<String, String>>, cb: ResultCallback) {
        try {
            val messagesArray = JSONArray()
            for ((role, content) in history) {
                val m = JSONObject()
                m.put("role", role)
                m.put("content", content)
                messagesArray.put(m)
            }
            val body = JSONObject()
            body.put("model", model)
            body.put("messages", messagesArray)
            body.put("temperature", 0.7)

            val mediaType = "application/json; charset=utf-8".toMediaType()
            val reqBody = body.toString().toRequestBody(mediaType)

            val req = Request.Builder()
                .url("https://api.groq.com/openai/v1/chat/completions")
                .addHeader("Authorization", "Bearer $apiKey")
                .addHeader("Content-Type", "application/json")
                .post(reqBody)
                .build()

            client.newCall(req).enqueue(object : Callback {
                override fun onFailure(call: Call, e: IOException) {
                    cb.onError(e.message ?: "Errore di rete")
                }
                override fun onResponse(call: Call, response: Response) {
                    try {
                        val raw = response.body?.string() ?: ""
                        if (!response.isSuccessful) {
                            cb.onError("HTTP ${response.code}: $raw")
                            return
                        }
                        val json = JSONObject(raw)
                        val choices = json.getJSONArray("choices")
                        val text = choices.getJSONObject(0)
                            .getJSONObject("message").getString("content")
                        cb.onResult(text)
                    } catch (e: Exception) {
                        cb.onError("Parsing risposta: ${e.message}")
                    } finally {
                        response.close()
                    }
                }
            })
        } catch (e: Exception) {
            cb.onError("Errore invio: ${e.message}")
        }
    }
}
"""

ARIA_BRAIN = r"""package com.aria.mobile.core

import android.content.Context
import com.aria.mobile.data.AriaDatabase
import com.aria.mobile.data.MessageEntity
import com.aria.mobile.net.GroqClient
import kotlinx.coroutines.*

class AriaBrain(private val context: Context) {

    private val prefs = context.getSharedPreferences(AppConfig.PREFS, Context.MODE_PRIVATE)
    private val db = AriaDatabase.getInstance(context)
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    private fun buildSystemPrompt(): String {
        val assistantName = prefs.getString(AppConfig.PREF_ASSISTANT_NAME, AppConfig.DEFAULT_ASSISTANT_NAME)
            ?: AppConfig.DEFAULT_ASSISTANT_NAME
        val userName = prefs.getString(AppConfig.PREF_USER_NAME, "") ?: ""
        val personality = prefs.getString(AppConfig.PREF_PERSONALITY, AppConfig.DEFAULT_PERSONALITY)
            ?: AppConfig.DEFAULT_PERSONALITY
        val personalityDesc = when (personality) {
            "Professionale" -> "Mantieni un tono professionale, preciso e formale."
            "Divertente" -> "Sii spiritosa: usa humour e battute quando è appropriato."
            "Sarcastica" -> "Usa un tono ironico e sarcastico, ma mai offensivo."
            "Motivazionale" -> "Sii energica e motivazionale, incoraggia sempre l'utente."
            else -> "Sii calorosa e amichevole."
        }
        val sb = StringBuilder()
        sb.append("Sei $assistantName, un'assistente AI personale creata da ${AppConfig.CREATOR}. ")
        sb.append("Sei utile, diretta e concisa. $personalityDesc ")
        sb.append("Rispondi in italiano salvo richiesta diversa.")
        if (userName.isNotBlank()) {
            sb.append(" L'utente si chiama $userName: chiamalo per nome quando risulta naturale.")
        }
        return sb.toString()
    }

    fun sendMessage(text: String, onResult: (String) -> Unit, onError: (String) -> Unit) {
        val apiKey = prefs.getString(AppConfig.PREF_API_KEY, "") ?: ""
        val model = prefs.getString(AppConfig.PREF_MODEL, AppConfig.DEFAULT_MODEL) ?: AppConfig.DEFAULT_MODEL
        val memoryEnabled = prefs.getBoolean(AppConfig.PREF_MEMORY_ENABLED, true)

        if (apiKey.isBlank()) {
            onError("Nessuna API key impostata. Tocca l'ingranaggio in alto per aprire le Impostazioni.")
            return
        }

        scope.launch {
            try {
                db.messageDao().insert(MessageEntity(role = "user", content = text))

                val history = mutableListOf("system" to buildSystemPrompt())
                if (memoryEnabled) {
                    val past = db.messageDao().getSession(0L)
                    for (m in past.takeLast(20)) history.add(m.role to m.content)
                }
                history.add("user" to text)

                val client = GroqClient(apiKey, model)
                client.sendMessage(history, object : GroqClient.ResultCallback {
                    override fun onResult(response: String) {
                        scope.launch {
                            db.messageDao().insert(MessageEntity(role = "assistant", content = response))
                            withContext(Dispatchers.Main) { onResult(response) }
                        }
                    }
                    override fun onError(message: String) {
                        scope.launch(Dispatchers.Main) { onError(message) }
                    }
                })
            } catch (e: Exception) {
                withContext(Dispatchers.Main) { onError("Errore interno: ${e.message}") }
            }
        }
    }

    fun clearHistory(onDone: () -> Unit) {
        scope.launch {
            db.messageDao().clearAll()
            withContext(Dispatchers.Main) { onDone() }
        }
    }
}
"""

CHAT_MESSAGE_MODEL = r"""package com.aria.mobile.ui

data class ChatMessage(
    val role: String,
    val content: String,
    val timestamp: Long = System.currentTimeMillis()
) {
    fun isUser() = role == "user"
}
"""

ARIA_VIEWMODEL = r"""package com.aria.mobile.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.State
import com.aria.mobile.core.AriaBrain
import com.aria.mobile.data.AriaDatabase
import kotlinx.coroutines.launch

class AriaViewModel(app: Application) : AndroidViewModel(app) {

    private val brain = AriaBrain(app.applicationContext)

    private val _messages = mutableStateOf<List<ChatMessage>>(emptyList())
    val messages: State<List<ChatMessage>> get() = _messages

    private val _isLoading = mutableStateOf(false)
    val isLoading: State<Boolean> get() = _isLoading

    private val _errorMessage = mutableStateOf<String?>(null)
    val errorMessage: State<String?> get() = _errorMessage

    var onAssistantResponse: ((String) -> Unit)? = null

    init {
        // Ricarica la conversazione salvata all'avvio
        viewModelScope.launch {
            try {
                val past = AriaDatabase.getInstance(app.applicationContext)
                    .messageDao().getSession(0L)
                if (past.isNotEmpty()) {
                    _messages.value = past.map { ChatMessage(it.role, it.content, it.timestamp) }
                }
            } catch (_: Exception) {
            }
        }
    }

    fun sendMessage(text: String) {
        if (text.isBlank() || _isLoading.value) return
        _messages.value = _messages.value + ChatMessage("user", text)
        _isLoading.value = true
        _errorMessage.value = null

        brain.sendMessage(
            text = text,
            onResult = { response ->
                _messages.value = _messages.value + ChatMessage("assistant", response)
                _isLoading.value = false
                onAssistantResponse?.invoke(response)
            },
            onError = { error ->
                _errorMessage.value = error
                _isLoading.value = false
            }
        )
    }

    fun dismissError() {
        _errorMessage.value = null
    }

    fun clearChat() {
        viewModelScope.launch {
            brain.clearHistory {
                _messages.value = emptyList()
            }
        }
    }
}
"""

ARIA_ORB = r"""package com.aria.mobile.ui

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import com.aria.mobile.core.AppConfig
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.sqrt

/** Stato d'animo della sfera: cambia colori, velocità e intensità. */
enum class OrbMood { IDLE, THINKING, SPEAKING, ERROR }

private class OrbPoint(val x: Float, val y: Float, val z: Float)

private fun sphericalPoints(n: Int): List<OrbPoint> {
    val golden = PI * (3.0 - sqrt(5.0))
    return List(n) { i ->
        val y = 1f - 2f * (i + 0.5f) / n
        val r = sqrt(1f - y * y)
        val theta = (golden * i).toFloat()
        OrbPoint(r * cos(theta), y, r * sin(theta))
    }
}

/**
 * Sfera 3D "viva": nucleo che respira, particelle in rotazione con
 * prospettiva reale, anelli orbitali che precedono nello spazio con
 * elettroni luminosi. Fluttua e reagisce allo stato dell'AI.
 */
@Composable
fun AriaOrb3D(
    mood: OrbMood,
    modifier: Modifier = Modifier,
    onTap: () -> Unit = {}
) {
    val particles = remember { sphericalPoints(150) }

    var angle by remember { mutableStateOf(0f) }
    var time by remember { mutableStateOf(0f) }

    val speed by animateFloatAsState(
        targetValue = when (mood) {
            OrbMood.IDLE -> 35f
            OrbMood.THINKING -> 170f
            OrbMood.SPEAKING -> 90f
            OrbMood.ERROR -> 18f
        },
        animationSpec = tween(700), label = "orbSpeed"
    )
    val glow by animateFloatAsState(
        targetValue = when (mood) {
            OrbMood.IDLE -> 0.55f
            OrbMood.THINKING -> 1f
            OrbMood.SPEAKING -> 0.95f
            OrbMood.ERROR -> 0.75f
        },
        animationSpec = tween(600), label = "orbGlow"
    )
    val mainColor by animateColorAsState(
        targetValue = when (mood) {
            OrbMood.IDLE -> Color(AppConfig.COLOR_ACCENT)
            OrbMood.THINKING -> Color(AppConfig.COLOR_PRIMARY_LIGHT)
            OrbMood.SPEAKING -> Color(0xFF00FFB3)
            OrbMood.ERROR -> Color(AppConfig.COLOR_ERROR)
        },
        animationSpec = tween(600), label = "orbColor"
    )
    val ringColor by animateColorAsState(
        targetValue = when (mood) {
            OrbMood.IDLE -> Color(AppConfig.COLOR_PRIMARY)
            OrbMood.THINKING -> Color(AppConfig.COLOR_ACCENT)
            OrbMood.SPEAKING -> Color(AppConfig.COLOR_ACCENT)
            OrbMood.ERROR -> Color(0xFFFF8A80)
        },
        animationSpec = tween(600), label = "orbRing"
    )

    // motore dell'animazione: velocità continua, cambia fluidamente col mood
    LaunchedEffect(Unit) {
        var last = 0L
        while (true) {
            withFrameNanos { now ->
                if (last != 0L) {
                    val dt = (now - last) / 1_000_000_000f
                    angle = (angle + dt * speed) % 360f
                    time += dt
                }
                last = now
            }
        }
    }

    Canvas(
        modifier = modifier.pointerInput(Unit) {
            detectTapGestures(onTap = { onTap() })
        }
    ) {
        val cx = size.width / 2f
        // fluttua su e giù come sospesa nell'aria
        val cy = size.height / 2f + sin(time * 1.4f) * size.height * 0.06f
        // respira
        val breathe = 1f + 0.05f * sin(time * 2.3f)
        val r = size.minDimension * 0.30f * breathe
        val focal = r * 2.8f
        val aY = angle * PI.toFloat() / 180f
        val tiltX = 0.42f + 0.12f * sin(time * 0.7f)
        val ca = cos(aY)
        val sa = sin(aY)
        val ct = cos(tiltX)
        val st = sin(tiltX)

        // aura esterna
        for (k in 4 downTo 1) {
            drawCircle(
                color = mainColor,
                radius = r * (1f + k * 0.22f),
                center = Offset(cx, cy),
                alpha = (glow * 0.14f / k).coerceIn(0f, 1f)
            )
        }

        // nucleo luminoso che respira
        drawCircle(
            brush = Brush.radialGradient(
                colors = listOf(
                    Color.White.copy(alpha = (0.85f * glow).coerceIn(0f, 1f)),
                    mainColor.copy(alpha = (0.45f * glow).coerceIn(0f, 1f)),
                    Color.Transparent
                ),
                center = Offset(cx, cy),
                radius = r * 0.7f
            ),
            radius = r * 0.7f,
            center = Offset(cx, cy)
        )

        // particelle della sfera: rotazione Y + inclinazione, prospettiva reale
        for ((i, p) in particles.withIndex()) {
            val rx = p.x * ca + p.z * sa
            val rz = -p.x * sa + p.z * ca
            val ry = p.y * ct - rz * st
            val rz2 = p.y * st + rz * ct
            val persp = focal / (focal + rz2 * r)
            val px = cx + rx * r * persp
            val py = cy + ry * r * persp
            val depth = (1f - rz2) / 2f
            val alpha = (0.1f + depth * 0.9f) * (0.35f + glow * 0.65f)
            val col = if (i % 4 == 0) ringColor else mainColor
            drawCircle(
                color = col,
                radius = (1.1f + 1.7f * depth) * persp,
                center = Offset(px, py),
                alpha = alpha.coerceIn(0f, 1f)
            )
        }

        // anelli orbitali 3D che precedono nello spazio, ognuno col suo elettrone
        val rings = listOf(
            Triple(1.35f, 0.9f, 1.6f),    // raggio relativo, inclinazione, velocità
            Triple(1.55f, -0.6f, -1.1f),
            Triple(1.78f, 0.25f, 0.7f)
        )
        for ((ri, ring) in rings.withIndex()) {
            val (rr, tilt, speedFactor) = ring
            val ringR = r * rr
            val rc = cos(tilt)
            val rs = sin(tilt)
            val ph = aY * speedFactor
            val cph = cos(ph)
            val sph = sin(ph)

            fun ringPoint(aRad: Float): Triple<Float, Float, Float> {
                val x0 = cos(aRad) * ringR
                val z0 = sin(aRad) * ringR
                val y1 = -z0 * rs
                val z1 = z0 * rc
                val xr = x0 * cph + z1 * sph
                val zr = -x0 * sph + z1 * cph
                val y2 = y1 * ct - zr * st
                val z2 = y1 * st + zr * ct
                val persp = focal / (focal + z2)
                val depth = ((1f - z2 / ringR) / 2f).coerceIn(0f, 1f)
                return Triple(cx + xr * persp, cy + y2 * persp, depth)
            }

            val steps = 64
            for (sIdx in 0 until steps) {
                val (px, py, depth) = ringPoint(2f * PI.toFloat() * sIdx / steps)
                drawCircle(
                    color = ringColor,
                    radius = 0.8f + 1.6f * depth,
                    center = Offset(px, py),
                    alpha = ((0.08f + 0.45f * depth) * glow).coerceIn(0f, 1f)
                )
            }

            // elettrone luminoso che sfreccia sull'anello
            val dir = if (speedFactor < 0f) -1f else 1f
            val (ex, ey, ed) = ringPoint(time * (1.2f + ri * 0.7f) * dir)
            drawCircle(
                color = mainColor,
                radius = 5f + 3f * ed,
                center = Offset(ex, ey),
                alpha = (0.30f * glow).coerceIn(0f, 1f)
            )
            drawCircle(
                color = Color.White,
                radius = 2.2f + 1.5f * ed,
                center = Offset(ex, ey),
                alpha = (0.85f * glow).coerceIn(0f, 1f)
            )
        }
    }
}
"""

SPLASH_ACTIVITY = r"""package com.aria.mobile.ui

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.aria.mobile.core.AppConfig
import kotlinx.coroutines.delay
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.sqrt

class SplashActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            AriaTheme {
                SplashScreen(
                    onFinished = {
                        startActivity(Intent(this@SplashActivity, MainActivity::class.java))
                        finish()
                    }
                )
            }
        }
    }
}

private class Star3D(val x: Float, val y: Float, val z: Float, val big: Boolean)

@Composable
fun SplashScreen(onFinished: () -> Unit) {
    // Punti distribuiti uniformemente su una sfera (spirale aurea)
    val stars = remember {
        val n = 220
        val golden = PI * (3.0 - sqrt(5.0))
        List(n) { i ->
            val y = 1f - 2f * (i + 0.5f) / n
            val r = sqrt(1f - y * y)
            val theta = (golden * i).toFloat()
            Star3D(r * cos(theta), y, r * sin(theta), i % 7 == 0)
        }
    }

    val transition = rememberInfiniteTransition(label = "splash")
    val rotation by transition.animateFloat(
        initialValue = 0f, targetValue = 360f,
        animationSpec = infiniteRepeatable(tween(9000, easing = LinearEasing)),
        label = "rotation"
    )
    val pulse by transition.animateFloat(
        initialValue = 0.94f, targetValue = 1.06f,
        animationSpec = infiniteRepeatable(tween(900), RepeatMode.Reverse),
        label = "pulse"
    )

    var entered by remember { mutableStateOf(false) }
    val fade by animateFloatAsState(
        targetValue = if (entered) 1f else 0f,
        animationSpec = tween(1400),
        label = "fade"
    )
    LaunchedEffect(Unit) {
        entered = true
        delay(3200)
        onFinished()
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    listOf(Color(0xFF05070F), Color(AppConfig.COLOR_BG), Color(0xFF141034))
                )
            ),
        contentAlignment = Alignment.Center
    ) {
        // Sfera 3D di particelle: rotazione attorno all'asse Y + inclinazione,
        // proiezione prospettica reale (i punti vicini sono grandi e luminosi)
        Canvas(modifier = Modifier.fillMaxSize()) {
            val cx = size.width / 2f
            val cy = size.height / 2f
            val sphereR = size.minDimension * 0.34f
            val focal = sphereR * 2.6f
            val angle = rotation * PI.toFloat() / 180f
            val ca = cos(angle)
            val sa = sin(angle)
            val tilt = 0.35f
            val ct = cos(tilt)
            val st = sin(tilt)

            for ((i, s) in stars.withIndex()) {
                // rotazione attorno a Y
                val rx = s.x * ca + s.z * sa
                val rz = -s.x * sa + s.z * ca
                // inclinazione attorno a X
                val ry = s.y * ct - rz * st
                val rz2 = s.y * st + rz * ct
                // proiezione prospettica
                val persp = focal / (focal + rz2 * sphereR)
                val px = cx + rx * sphereR * persp
                val py = cy + ry * sphereR * persp
                val depth = (1f - rz2) / 2f  // 1 = davanti, 0 = dietro
                val alpha = ((0.15f + depth * 0.85f) * fade).coerceIn(0f, 1f)
                val radius = (if (s.big) 4.2f else 2.2f) * persp
                val color = if (i % 3 == 0) Color(AppConfig.COLOR_ACCENT) else Color(AppConfig.COLOR_PRIMARY)
                drawCircle(color = color, radius = radius, center = Offset(px, py), alpha = alpha)
            }

            drawCircle(
                color = Color(AppConfig.COLOR_ACCENT),
                radius = sphereR * 1.18f,
                center = Offset(cx, cy),
                alpha = 0.12f * fade,
                style = Stroke(width = 2f)
            )
        }

        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier.graphicsLayer(alpha = fade)
        ) {
            Text(
                text = "ARIA",
                fontSize = 62.sp,
                fontWeight = FontWeight.Black,
                letterSpacing = 14.sp,
                color = Color(AppConfig.COLOR_ACCENT),
                modifier = Modifier.graphicsLayer(scaleX = pulse, scaleY = pulse)
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = "Il tuo assistente AI personale",
                fontSize = 14.sp,
                color = Color(AppConfig.COLOR_TEXT)
            )
            Spacer(modifier = Modifier.height(150.dp))
            Text(
                text = "Creator: ${AppConfig.CREATOR}",
                fontSize = 17.sp,
                fontWeight = FontWeight.Bold,
                color = Color(AppConfig.COLOR_PRIMARY_LIGHT)
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = "v${AppConfig.VERSION}",
                fontSize = 12.sp,
                color = Color(AppConfig.COLOR_TEXT_DIM)
            )
        }
    }
}
"""

MAIN_ACTIVITY = r"""package com.aria.mobile.ui

import android.content.Intent
import android.os.Bundle
import android.speech.RecognizerIntent
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.StartOffset
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.automirrored.filled.VolumeOff
import androidx.compose.material.icons.automirrored.filled.VolumeUp
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.DeleteSweep
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.aria.mobile.core.AppConfig
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainActivity : ComponentActivity() {

    private val viewModel: AriaViewModel by viewModels()
    private var tts: TextToSpeech? = null
    private var ttsReady = false
    private val assistantName = mutableStateOf(AppConfig.DEFAULT_ASSISTANT_NAME)
    private val voiceEnabled = mutableStateOf(true)
    private val speaking = mutableStateOf(false)

    private val speechLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == RESULT_OK) {
            val spoken = result.data
                ?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
                ?.firstOrNull()
            if (!spoken.isNullOrBlank()) viewModel.sendMessage(spoken)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        tts = TextToSpeech(this) { status ->
            if (status == TextToSpeech.SUCCESS) {
                val res = tts?.setLanguage(Locale.ITALIAN) ?: TextToSpeech.LANG_MISSING_DATA
                if (res == TextToSpeech.LANG_MISSING_DATA || res == TextToSpeech.LANG_NOT_SUPPORTED) {
                    // niente voce italiana installata: usa la lingua di sistema
                    tts?.language = Locale.getDefault()
                }
                tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                    override fun onStart(utteranceId: String?) {
                        runOnUiThread { speaking.value = true }
                    }
                    override fun onDone(utteranceId: String?) {
                        runOnUiThread { speaking.value = false }
                    }
                    @Deprecated("deprecated in API level 21")
                    override fun onError(utteranceId: String?) {
                        runOnUiThread { speaking.value = false }
                    }
                    override fun onError(utteranceId: String?, errorCode: Int) {
                        runOnUiThread { speaking.value = false }
                    }
                })
                ttsReady = true
            } else {
                runOnUiThread {
                    Toast.makeText(
                        this,
                        "Sintesi vocale non disponibile: installa 'Sintesi vocale Google' dal Play Store",
                        Toast.LENGTH_LONG
                    ).show()
                }
            }
        }
        viewModel.onAssistantResponse = { text ->
            if (voiceEnabled.value) speak(text)
        }

        setContent {
            AriaTheme {
                ChatScreen(
                    viewModel = viewModel,
                    assistantName = assistantName.value,
                    voiceEnabled = voiceEnabled.value,
                    speaking = speaking.value,
                    onToggleVoice = { toggleVoice() },
                    onVoiceInput = { startVoiceInput() },
                    onSpeak = { speak(it) },
                    onShareChat = { shareConversation() },
                    onOpenSettings = {
                        startActivity(Intent(this, SettingsActivity::class.java))
                    },
                    onOpenHistory = {
                        startActivity(Intent(this, HistoryActivity::class.java))
                    }
                )
            }
        }
    }

    override fun onResume() {
        super.onResume()
        val prefs = getSharedPreferences(AppConfig.PREFS, MODE_PRIVATE)
        assistantName.value = prefs.getString(
            AppConfig.PREF_ASSISTANT_NAME, AppConfig.DEFAULT_ASSISTANT_NAME
        ) ?: AppConfig.DEFAULT_ASSISTANT_NAME
        voiceEnabled.value = prefs.getBoolean(AppConfig.PREF_VOICE_ENABLED, true)
    }

    override fun onDestroy() {
        tts?.stop()
        tts?.shutdown()
        super.onDestroy()
    }

    private fun speak(text: String) {
        if (!ttsReady) {
            Toast.makeText(this, "Voce in preparazione, riprova tra un attimo", Toast.LENGTH_SHORT).show()
            return
        }
        // toglie i simboli markdown per una lettura naturale
        val clean = text.replace(Regex("[*_#`~\\[\\]>]"), " ")
        tts?.speak(clean, TextToSpeech.QUEUE_FLUSH, null, "aria_tts")
    }

    private fun toggleVoice() {
        val enabled = !voiceEnabled.value
        voiceEnabled.value = enabled
        getSharedPreferences(AppConfig.PREFS, MODE_PRIVATE).edit()
            .putBoolean(AppConfig.PREF_VOICE_ENABLED, enabled)
            .apply()
        if (!enabled) {
            tts?.stop()
            speaking.value = false
        }
        Toast.makeText(
            this,
            if (enabled) "Voce attivata" else "Voce disattivata",
            Toast.LENGTH_SHORT
        ).show()
    }

    private fun shareConversation() {
        val msgs = viewModel.messages.value
        if (msgs.isEmpty()) {
            Toast.makeText(this, "Nessun messaggio da condividere", Toast.LENGTH_SHORT).show()
            return
        }
        val name = assistantName.value
        val text = msgs.joinToString("\n\n") {
            (if (it.isUser()) "Io: " else "$name: ") + it.content
        }
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_TEXT, text)
        }
        startActivity(Intent.createChooser(intent, "Condividi conversazione"))
    }

    private fun startVoiceInput() {
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "it-IT")
            putExtra(RecognizerIntent.EXTRA_PROMPT, "Parla ora...")
        }
        try {
            speechLauncher.launch(intent)
        } catch (e: Exception) {
            Toast.makeText(this, "Riconoscimento vocale non disponibile", Toast.LENGTH_SHORT).show()
        }
    }
}

@Composable
fun AriaTheme(content: @Composable () -> Unit) {
    val colors = darkColorScheme(
        primary = Color(AppConfig.COLOR_PRIMARY),
        secondary = Color(AppConfig.COLOR_ACCENT),
        background = Color(AppConfig.COLOR_BG),
        surface = Color(AppConfig.COLOR_SURFACE),
        onBackground = Color(AppConfig.COLOR_TEXT),
        onSurface = Color(AppConfig.COLOR_TEXT)
    )
    MaterialTheme(colorScheme = colors, content = content)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(
    viewModel: AriaViewModel,
    assistantName: String,
    voiceEnabled: Boolean,
    speaking: Boolean,
    onToggleVoice: () -> Unit,
    onVoiceInput: () -> Unit,
    onSpeak: (String) -> Unit,
    onShareChat: () -> Unit,
    onOpenSettings: () -> Unit,
    onOpenHistory: () -> Unit
) {
    var input by remember { mutableStateOf("") }
    var showClearDialog by remember { mutableStateOf(false) }
    var showTools by remember { mutableStateOf(false) }
    var menuOpen by remember { mutableStateOf(false) }
    val messages = viewModel.messages.value
    val isLoading = viewModel.isLoading.value
    val error = viewModel.errorMessage.value
    val listState = rememberLazyListState()
    val scope = rememberCoroutineScope()

    val orbMood = when {
        error != null -> OrbMood.ERROR
        isLoading -> OrbMood.THINKING
        speaking -> OrbMood.SPEAKING
        else -> OrbMood.IDLE
    }

    LaunchedEffect(messages.size, isLoading) {
        if (messages.isNotEmpty()) {
            scope.launch { listState.animateScrollToItem(messages.size - 1) }
        }
    }

    if (showClearDialog) {
        AlertDialog(
            onDismissRequest = { showClearDialog = false },
            containerColor = Color(AppConfig.COLOR_SURFACE),
            title = { Text("Svuotare la chat?", color = Color(AppConfig.COLOR_TEXT)) },
            text = {
                Text(
                    "Tutti i messaggi e la memoria di $assistantName verranno cancellati.",
                    color = Color(AppConfig.COLOR_TEXT_DIM)
                )
            },
            confirmButton = {
                TextButton(onClick = {
                    viewModel.clearChat()
                    showClearDialog = false
                }) { Text("Svuota", color = Color(AppConfig.COLOR_ERROR)) }
            },
            dismissButton = {
                TextButton(onClick = { showClearDialog = false }) {
                    Text("Annulla", color = Color(AppConfig.COLOR_ACCENT))
                }
            }
        )
    }

    if (showTools) {
        ModalBottomSheet(
            onDismissRequest = { showTools = false },
            containerColor = Color(AppConfig.COLOR_SURFACE)
        ) {
            ToolsSheetContent(onTool = { tool ->
                showTools = false
                if (tool.sendDirectly) {
                    viewModel.sendMessage(tool.prompt)
                } else {
                    input = tool.prompt
                }
            })
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(
                            modifier = Modifier
                                .size(10.dp)
                                .background(Color(AppConfig.COLOR_ACCENT), CircleShape)
                        )
                        Spacer(modifier = Modifier.width(10.dp))
                        Column {
                            Text(
                                assistantName,
                                color = Color(AppConfig.COLOR_ACCENT),
                                fontWeight = FontWeight.Bold
                            )
                            Text(
                                "by ${AppConfig.CREATOR}",
                                color = Color(AppConfig.COLOR_TEXT_DIM),
                                fontSize = 10.sp
                            )
                        }
                    }
                },
                actions = {
                    IconButton(onClick = onToggleVoice) {
                        Icon(
                            if (voiceEnabled) Icons.AutoMirrored.Filled.VolumeUp
                            else Icons.AutoMirrored.Filled.VolumeOff,
                            contentDescription = "Voce on/off",
                            tint = if (voiceEnabled) Color(AppConfig.COLOR_ACCENT)
                            else Color(AppConfig.COLOR_TEXT_DIM)
                        )
                    }
                    IconButton(onClick = onOpenSettings) {
                        Icon(
                            Icons.Filled.Settings,
                            contentDescription = "Impostazioni",
                            tint = Color(AppConfig.COLOR_ACCENT)
                        )
                    }
                    Box {
                        IconButton(onClick = { menuOpen = true }) {
                            Icon(
                                Icons.Filled.MoreVert,
                                contentDescription = "Menu",
                                tint = Color(AppConfig.COLOR_TEXT_DIM)
                            )
                        }
                        DropdownMenu(
                            expanded = menuOpen,
                            onDismissRequest = { menuOpen = false }
                        ) {
                            DropdownMenuItem(
                                text = { Text("Cronologia", color = Color(AppConfig.COLOR_TEXT)) },
                                leadingIcon = {
                                    Icon(
                                        Icons.Filled.History,
                                        contentDescription = null,
                                        tint = Color(AppConfig.COLOR_TEXT_DIM)
                                    )
                                },
                                onClick = {
                                    menuOpen = false
                                    onOpenHistory()
                                }
                            )
                            DropdownMenuItem(
                                text = { Text("Condividi chat", color = Color(AppConfig.COLOR_TEXT)) },
                                leadingIcon = {
                                    Icon(
                                        Icons.Filled.Share,
                                        contentDescription = null,
                                        tint = Color(AppConfig.COLOR_TEXT_DIM)
                                    )
                                },
                                onClick = {
                                    menuOpen = false
                                    onShareChat()
                                }
                            )
                            DropdownMenuItem(
                                text = { Text("Svuota chat", color = Color(AppConfig.COLOR_ERROR)) },
                                leadingIcon = {
                                    Icon(
                                        Icons.Filled.DeleteSweep,
                                        contentDescription = null,
                                        tint = Color(AppConfig.COLOR_ERROR)
                                    )
                                },
                                onClick = {
                                    menuOpen = false
                                    showClearDialog = true
                                }
                            )
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Color(AppConfig.COLOR_SURFACE)
                )
            )
        },
        containerColor = Color(AppConfig.COLOR_BG)
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .background(
                    Brush.verticalGradient(
                        listOf(Color(AppConfig.COLOR_BG), Color(0xFF0D1226), Color(0xFF10142A))
                    )
                )
        ) {
            // Sfera 3D viva che fluttua e reagisce all'AI. Toccala per parlare.
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(150.dp),
                contentAlignment = Alignment.Center
            ) {
                AriaOrb3D(
                    mood = orbMood,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(150.dp),
                    onTap = onVoiceInput
                )
                Text(
                    text = when (orbMood) {
                        OrbMood.THINKING -> "sto pensando..."
                        OrbMood.SPEAKING -> "sto parlando..."
                        OrbMood.ERROR -> "qualcosa è andato storto"
                        OrbMood.IDLE -> "tocca la sfera per parlarmi"
                    },
                    fontSize = 11.sp,
                    color = Color(AppConfig.COLOR_TEXT_DIM),
                    modifier = Modifier
                        .align(Alignment.BottomCenter)
                        .padding(bottom = 2.dp)
                )
            }
            LazyColumn(
                state = listState,
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .padding(horizontal = 12.dp, vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                if (messages.isEmpty() && !isLoading) {
                    item { WelcomeCard(assistantName) { viewModel.sendMessage(it) } }
                }
                items(messages) { msg ->
                    MessageBubble(msg, assistantName, onSpeak)
                }
                if (isLoading) {
                    item { TypingIndicator(assistantName) }
                }
                if (error != null) {
                    item {
                        Column(
                            modifier = Modifier
                                .fillMaxWidth()
                                .background(
                                    Color(AppConfig.COLOR_ERROR).copy(alpha = 0.12f),
                                    RoundedCornerShape(12.dp)
                                )
                                .clickable { viewModel.dismissError() }
                                .padding(12.dp)
                        ) {
                            Text(
                                "Errore: $error",
                                color = Color(AppConfig.COLOR_ERROR),
                                fontSize = 13.sp
                            )
                            Text(
                                "Tocca per chiudere",
                                color = Color(AppConfig.COLOR_TEXT_DIM),
                                fontSize = 10.sp
                            )
                        }
                    }
                }
            }

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 12.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                IconButton(
                    onClick = { showTools = true },
                    modifier = Modifier
                        .size(48.dp)
                        .background(Color(AppConfig.COLOR_SURFACE), CircleShape)
                ) {
                    Icon(
                        Icons.Filled.AutoAwesome,
                        contentDescription = "Strumenti",
                        tint = Color(AppConfig.COLOR_PRIMARY_LIGHT)
                    )
                }
                Spacer(modifier = Modifier.width(6.dp))
                IconButton(
                    onClick = onVoiceInput,
                    modifier = Modifier
                        .size(48.dp)
                        .background(Color(AppConfig.COLOR_SURFACE), CircleShape)
                ) {
                    Icon(
                        Icons.Filled.Mic,
                        contentDescription = "Messaggio vocale",
                        tint = Color(AppConfig.COLOR_ACCENT)
                    )
                }
                Spacer(modifier = Modifier.width(8.dp))
                OutlinedTextField(
                    value = input,
                    onValueChange = { input = it },
                    modifier = Modifier.weight(1f),
                    maxLines = 4,
                    placeholder = {
                        Text("Scrivi un messaggio...", color = Color(AppConfig.COLOR_TEXT_DIM))
                    },
                    shape = RoundedCornerShape(24.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = Color(AppConfig.COLOR_TEXT),
                        unfocusedTextColor = Color(AppConfig.COLOR_TEXT),
                        focusedBorderColor = Color(AppConfig.COLOR_ACCENT),
                        unfocusedBorderColor = Color(AppConfig.COLOR_SURFACE),
                        cursorColor = Color(AppConfig.COLOR_ACCENT)
                    )
                )
                Spacer(modifier = Modifier.width(8.dp))
                Button(
                    onClick = {
                        if (input.isNotBlank()) {
                            viewModel.sendMessage(input)
                            input = ""
                        }
                    },
                    shape = CircleShape,
                    contentPadding = PaddingValues(0.dp),
                    modifier = Modifier.size(52.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = Color(AppConfig.COLOR_PRIMARY)
                    )
                ) {
                    Icon(
                        Icons.AutoMirrored.Filled.Send,
                        contentDescription = "Invia",
                        tint = Color.White
                    )
                }
            }
        }
    }
}

@Composable
fun WelcomeCard(assistantName: String, onSuggestion: (String) -> Unit) {
    val suggestions = listOf(
        "Ciao! Chi sei?",
        "Dammi un'idea creativa",
        "Raccontami una curiosità",
        "Aiutami a scrivere un messaggio"
    )
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 40.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            "✦",
            fontSize = 42.sp,
            color = Color(AppConfig.COLOR_ACCENT)
        )
        Spacer(modifier = Modifier.height(12.dp))
        Text(
            "Ciao! Sono $assistantName",
            fontSize = 22.sp,
            fontWeight = FontWeight.Bold,
            color = Color(AppConfig.COLOR_TEXT)
        )
        Spacer(modifier = Modifier.height(4.dp))
        Text(
            "Creata da ${AppConfig.CREATOR} • Chiedimi qualsiasi cosa",
            fontSize = 13.sp,
            color = Color(AppConfig.COLOR_TEXT_DIM)
        )
        Spacer(modifier = Modifier.height(20.dp))
        for (s in suggestions) {
            AssistChip(
                onClick = { onSuggestion(s) },
                label = { Text(s, color = Color(AppConfig.COLOR_TEXT)) },
                modifier = Modifier.padding(vertical = 2.dp)
            )
        }
    }
}

@Composable
fun TypingIndicator(assistantName: String) {
    val transition = rememberInfiniteTransition(label = "typing")
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier
            .background(Color(AppConfig.COLOR_SURFACE), RoundedCornerShape(18.dp))
            .padding(horizontal = 14.dp, vertical = 10.dp)
    ) {
        Text(
            "$assistantName sta scrivendo",
            fontSize = 12.sp,
            color = Color(AppConfig.COLOR_TEXT_DIM)
        )
        Spacer(modifier = Modifier.width(8.dp))
        for (i in 0..2) {
            val dotAlpha by transition.animateFloat(
                initialValue = 0.2f,
                targetValue = 1f,
                animationSpec = infiniteRepeatable(
                    animation = tween(450),
                    repeatMode = RepeatMode.Reverse,
                    initialStartOffset = StartOffset(i * 150)
                ),
                label = "dot$i"
            )
            Box(
                modifier = Modifier
                    .padding(horizontal = 2.dp)
                    .size(7.dp)
                    .background(
                        Color(AppConfig.COLOR_ACCENT).copy(alpha = dotAlpha),
                        CircleShape
                    )
            )
        }
    }
}

@Composable
fun MessageBubble(msg: ChatMessage, assistantName: String, onSpeak: (String) -> Unit) {
    val clipboard = LocalClipboardManager.current
    val context = LocalContext.current
    val isUser = msg.isUser()
    val timeText = remember(msg.timestamp) {
        SimpleDateFormat("HH:mm", Locale.getDefault()).format(Date(msg.timestamp))
    }
    val bubbleShape = RoundedCornerShape(
        topStart = 18.dp,
        topEnd = 18.dp,
        bottomStart = if (isUser) 18.dp else 4.dp,
        bottomEnd = if (isUser) 4.dp else 18.dp
    )
    val bubbleBrush = if (isUser) {
        Brush.linearGradient(
            listOf(Color(AppConfig.COLOR_PRIMARY), Color(AppConfig.COLOR_PRIMARY_LIGHT))
        )
    } else {
        Brush.linearGradient(
            listOf(Color(AppConfig.COLOR_SURFACE), Color(0xFF1A2238))
        )
    }

    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = if (isUser) Alignment.End else Alignment.Start
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
        ) {
            Text(
                text = if (isUser) "Tu • $timeText" else "$assistantName • $timeText",
                fontSize = 10.sp,
                color = Color(AppConfig.COLOR_TEXT_DIM)
            )
            if (!isUser) {
                Spacer(modifier = Modifier.width(6.dp))
                Icon(
                    Icons.AutoMirrored.Filled.VolumeUp,
                    contentDescription = "Riascolta",
                    tint = Color(AppConfig.COLOR_ACCENT),
                    modifier = Modifier
                        .size(16.dp)
                        .clickable { onSpeak(msg.content) }
                )
            }
        }
        Box(
            modifier = Modifier
                .widthIn(max = 300.dp)
                .background(brush = bubbleBrush, shape = bubbleShape)
                .pointerInput(msg.content) {
                    detectTapGestures(onLongPress = {
                        clipboard.setText(AnnotatedString(msg.content))
                        Toast.makeText(context, "Messaggio copiato", Toast.LENGTH_SHORT).show()
                    })
                }
                .padding(horizontal = 14.dp, vertical = 10.dp)
        ) {
            Text(
                text = msg.content,
                color = Color(AppConfig.COLOR_TEXT),
                fontSize = 15.sp
            )
        }
    }
}

data class AriaTool(
    val emoji: String,
    val title: String,
    val description: String,
    val prompt: String,
    val sendDirectly: Boolean = false
)

private val ARIA_TOOLS = listOf(
    AriaTool("🌍", "Traduttore", "Traduci un testo in un'altra lingua",
        "Traduci in inglese questo testo: "),
    AriaTool("📝", "Riassunto", "Riassumi un testo lungo in pochi punti",
        "Riassumi in 3 punti questo testo: "),
    AriaTool("✍️", "Correttore", "Correggi grammatica e ortografia",
        "Correggi grammatica e ortografia di questo testo: "),
    AriaTool("🧮", "Matematica", "Risolvi calcoli ed espressioni passo passo",
        "Risolvi passo passo: "),
    AriaTool("📧", "Email", "Scrivi un'email professionale",
        "Scrivimi un'email professionale per: "),
    AriaTool("💡", "Idee", "Brainstorming di idee creative",
        "Dammi 5 idee creative su: "),
    AriaTool("🍝", "Chef", "Ricetta con gli ingredienti che hai in casa",
        "Dammi una ricetta usando questi ingredienti: "),
    AriaTool("💪", "Coach", "Allenamento rapido da fare a casa",
        "Creami un allenamento di 20 minuti da fare a casa senza attrezzi", true),
    AriaTool("🎲", "Quiz", "Gioca a un quiz con l'AI",
        "Facciamo un quiz! Fammi una domanda di cultura generale e aspetta la mia risposta", true),
    AriaTool("😂", "Barzelletta", "Una risata al volo",
        "Raccontami una barzelletta divertente", true)
)

@Composable
fun ToolsSheetContent(onTool: (AriaTool) -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp)
            .padding(bottom = 32.dp)
    ) {
        Text(
            "✨ Strumenti",
            fontSize = 20.sp,
            fontWeight = FontWeight.Bold,
            color = Color(AppConfig.COLOR_ACCENT),
            modifier = Modifier.padding(bottom = 4.dp)
        )
        Text(
            "Tocca uno strumento: alcuni partono subito, altri preparano il messaggio da completare.",
            fontSize = 12.sp,
            color = Color(AppConfig.COLOR_TEXT_DIM),
            modifier = Modifier.padding(bottom = 12.dp)
        )
        for (tool in ARIA_TOOLS) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 4.dp)
                    .background(Color(AppConfig.COLOR_BG), RoundedCornerShape(14.dp))
                    .clickable { onTool(tool) }
                    .padding(12.dp)
            ) {
                Text(tool.emoji, fontSize = 24.sp)
                Spacer(modifier = Modifier.width(12.dp))
                Column {
                    Text(
                        tool.title,
                        color = Color(AppConfig.COLOR_TEXT),
                        fontWeight = FontWeight.Bold,
                        fontSize = 15.sp
                    )
                    Text(
                        tool.description,
                        color = Color(AppConfig.COLOR_TEXT_DIM),
                        fontSize = 12.sp
                    )
                }
            }
        }
    }
}
"""

SETTINGS_ACTIVITY = r"""package com.aria.mobile.ui

import android.content.Context
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.RadioGroup
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.widget.SwitchCompat
import com.aria.mobile.R
import com.aria.mobile.core.AppConfig
import com.aria.mobile.net.GroqClient

class SettingsActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_settings)

        val prefs = getSharedPreferences(AppConfig.PREFS, Context.MODE_PRIVATE)
        val etAssistantName = findViewById<EditText>(R.id.et_assistant_name)
        val etUserName = findViewById<EditText>(R.id.et_user_name)
        val etKey = findViewById<EditText>(R.id.et_api_key)
        val etModel = findViewById<EditText>(R.id.et_model)
        val rgPersonality = findViewById<RadioGroup>(R.id.rg_personality)
        val swVoice = findViewById<SwitchCompat>(R.id.sw_voice)
        val swMemory = findViewById<SwitchCompat>(R.id.sw_memory)
        val btnSave = findViewById<Button>(R.id.btn_save_settings)
        val btnBack = findViewById<Button>(R.id.btn_settings_back)
        val btnTest = findViewById<Button>(R.id.btn_test_api)
        val btnModel70 = findViewById<Button>(R.id.btn_model_70b)
        val btnModel8 = findViewById<Button>(R.id.btn_model_8b)
        val btnModelScout = findViewById<Button>(R.id.btn_model_scout)

        val personalityIds = mapOf(
            "Amichevole" to R.id.rb_amichevole,
            "Professionale" to R.id.rb_professionale,
            "Divertente" to R.id.rb_divertente,
            "Sarcastica" to R.id.rb_sarcastica,
            "Motivazionale" to R.id.rb_motivazionale
        )

        etAssistantName.setText(
            prefs.getString(AppConfig.PREF_ASSISTANT_NAME, AppConfig.DEFAULT_ASSISTANT_NAME)
        )
        etUserName.setText(prefs.getString(AppConfig.PREF_USER_NAME, ""))
        etKey.setText(prefs.getString(AppConfig.PREF_API_KEY, ""))
        etModel.setText(prefs.getString(AppConfig.PREF_MODEL, AppConfig.DEFAULT_MODEL))
        swVoice.isChecked = prefs.getBoolean(AppConfig.PREF_VOICE_ENABLED, true)
        swMemory.isChecked = prefs.getBoolean(AppConfig.PREF_MEMORY_ENABLED, true)
        val savedPersonality = prefs.getString(
            AppConfig.PREF_PERSONALITY, AppConfig.DEFAULT_PERSONALITY
        )
        rgPersonality.check(personalityIds[savedPersonality] ?: R.id.rb_amichevole)

        btnModel70.setOnClickListener { etModel.setText("llama-3.3-70b-versatile") }
        btnModel8.setOnClickListener { etModel.setText("llama-3.1-8b-instant") }
        btnModelScout.setOnClickListener {
            etModel.setText("meta-llama/llama-4-scout-17b-16e-instruct")
        }

        btnTest.setOnClickListener {
            val key = etKey.text.toString().trim()
            val model = etModel.text.toString().trim().ifBlank { AppConfig.DEFAULT_MODEL }
            if (key.isBlank()) {
                Toast.makeText(this, "Inserisci prima la API key", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            Toast.makeText(this, "Test in corso...", Toast.LENGTH_SHORT).show()
            GroqClient(key, model).sendMessage(
                listOf("user" to "Rispondi solo: OK"),
                object : GroqClient.ResultCallback {
                    override fun onResult(text: String) {
                        runOnUiThread {
                            Toast.makeText(
                                this@SettingsActivity,
                                "Connessione OK! Modello: $model",
                                Toast.LENGTH_LONG
                            ).show()
                        }
                    }
                    override fun onError(message: String) {
                        runOnUiThread {
                            Toast.makeText(
                                this@SettingsActivity,
                                "Errore: ${message.take(200)}",
                                Toast.LENGTH_LONG
                            ).show()
                        }
                    }
                }
            )
        }

        btnSave.setOnClickListener {
            val assistantName = etAssistantName.text.toString().trim()
                .ifBlank { AppConfig.DEFAULT_ASSISTANT_NAME }
            val model = etModel.text.toString().trim()
                .ifBlank { AppConfig.DEFAULT_MODEL }
            val checkedId = rgPersonality.checkedRadioButtonId
            val personality = personalityIds.entries
                .firstOrNull { it.value == checkedId }?.key
                ?: AppConfig.DEFAULT_PERSONALITY
            prefs.edit()
                .putString(AppConfig.PREF_ASSISTANT_NAME, assistantName)
                .putString(AppConfig.PREF_USER_NAME, etUserName.text.toString().trim())
                .putString(AppConfig.PREF_API_KEY, etKey.text.toString().trim())
                .putString(AppConfig.PREF_MODEL, model)
                .putString(AppConfig.PREF_PERSONALITY, personality)
                .putBoolean(AppConfig.PREF_VOICE_ENABLED, swVoice.isChecked)
                .putBoolean(AppConfig.PREF_MEMORY_ENABLED, swMemory.isChecked)
                .apply()
            Toast.makeText(this, "Impostazioni salvate", Toast.LENGTH_SHORT).show()
            finish()
        }
        btnBack.setOnClickListener { finish() }
    }
}
"""

HISTORY_ACTIVITY = r"""package com.aria.mobile.ui

import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.aria.mobile.R
import com.aria.mobile.data.AriaDatabase
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class HistoryActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_history)

        val tv = findViewById<TextView>(R.id.tv_history_content)
        val btnBack = findViewById<Button>(R.id.btn_history_back)
        val btnClear = findViewById<Button>(R.id.btn_history_clear)
        val fmt = SimpleDateFormat("dd/MM HH:mm", Locale.getDefault())

        btnBack.setOnClickListener { finish() }

        val db = AriaDatabase.getInstance(this)
        btnClear.setOnClickListener {
            lifecycleScope.launch {
                db.messageDao().clearAll()
                tv.text = "Cronologia svuotata."
            }
        }

        lifecycleScope.launch {
            val msgs = db.messageDao().getSession(0L)
            tv.text = if (msgs.isEmpty()) "Nessun messaggio salvato."
                else "Messaggi salvati: ${msgs.size}\n\n" + msgs.joinToString("\n\n") {
                    val who = if (it.role == "user") "TU" else "AI"
                    "[${fmt.format(Date(it.timestamp))}] $who:\n${it.content}"
                }
        }
    }
}
"""

# ============================================================
#  LAYOUT XML
# ============================================================
STRINGS_XML = '<resources><string name="app_name">ARIA</string></resources>'

THEMES_XML = """\
<resources>
    <style name="Theme.Aria" parent="Theme.Material3.DayNight.NoActionBar">
        <item name="colorPrimary">#7C4DFF</item>
        <item name="colorSecondary">#00E5FF</item>
        <item name="android:windowBackground">#0A0E1A</item>
        <item name="android:statusBarColor">#0A0E1A</item>
        <item name="android:navigationBarColor">#121826</item>
    </style>
</resources>"""

IC_ARIA_XML = """\
<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp" android:height="108dp"
    android:viewportWidth="108" android:viewportHeight="108">
  <path android:fillColor="#0A0E1A" android:pathData="M0,0h108v108h-108z"/>
  <path android:fillColor="#7C4DFF"
    android:pathData="M54,20 L74,88 L62,88 L57,72 L51,72 L46,88 L34,88 Z"/>
  <path android:fillColor="#00E5FF"
    android:pathData="M54,40 m-6,0 a6,6 0 1,0 12,0 a6,6 0 1,0 -12,0"/>
</vector>"""

LAYOUT_SETTINGS = """\
<?xml version="1.0" encoding="utf-8"?>
<ScrollView xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent" android:layout_height="match_parent"
    android:background="#0A0E1A">
<LinearLayout
    android:layout_width="match_parent" android:layout_height="wrap_content"
    android:orientation="vertical" android:padding="20dp">

    <Button android:id="@+id/btn_settings_back"
        android:layout_width="wrap_content" android:layout_height="wrap_content"
        android:text="&lt; Indietro" android:backgroundTint="#121826" android:textColor="#00E5FF"
        android:layout_marginBottom="20dp"/>

    <TextView android:layout_width="wrap_content" android:layout_height="wrap_content"
        android:text="IMPOSTAZIONI" android:textColor="#7C4DFF"
        android:textSize="22sp" android:textStyle="bold" android:layout_marginBottom="20dp"/>

    <TextView android:layout_width="wrap_content" android:layout_height="wrap_content"
        android:text="Nome assistente" android:textColor="#5A7A99" android:textSize="12sp"/>
    <EditText android:id="@+id/et_assistant_name"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:hint="ARIA" android:textColor="#E8F0FF" android:textColorHint="#5A7A99"
        android:backgroundTint="#7C4DFF" android:layout_marginBottom="16dp"/>

    <TextView android:layout_width="wrap_content" android:layout_height="wrap_content"
        android:text="Il tuo nome (opzionale)" android:textColor="#5A7A99" android:textSize="12sp"/>
    <EditText android:id="@+id/et_user_name"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:hint="Come ti chiami?" android:textColor="#E8F0FF" android:textColorHint="#5A7A99"
        android:backgroundTint="#7C4DFF" android:layout_marginBottom="16dp"/>

    <TextView android:layout_width="wrap_content" android:layout_height="wrap_content"
        android:text="Groq API Key" android:textColor="#5A7A99" android:textSize="12sp"/>
    <EditText android:id="@+id/et_api_key"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:hint="gsk_..." android:textColor="#E8F0FF" android:textColorHint="#5A7A99"
        android:backgroundTint="#7C4DFF" android:layout_marginBottom="8dp"/>

    <Button android:id="@+id/btn_test_api"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:text="Prova connessione" android:backgroundTint="#121826"
        android:textColor="#00E5FF" android:layout_marginBottom="16dp"/>

    <TextView android:layout_width="wrap_content" android:layout_height="wrap_content"
        android:text="Modello" android:textColor="#5A7A99" android:textSize="12sp"/>
    <EditText android:id="@+id/et_model"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:hint="llama-3.3-70b-versatile" android:textColor="#E8F0FF" android:textColorHint="#5A7A99"
        android:backgroundTint="#7C4DFF" android:layout_marginBottom="8dp"/>

    <LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content"
        android:orientation="horizontal" android:layout_marginBottom="20dp">
        <Button android:id="@+id/btn_model_70b"
            android:layout_width="0dp" android:layout_height="wrap_content"
            android:layout_weight="1" android:layout_marginEnd="6dp"
            android:text="70B top" android:textSize="11sp"
            android:backgroundTint="#121826" android:textColor="#00E5FF"/>
        <Button android:id="@+id/btn_model_8b"
            android:layout_width="0dp" android:layout_height="wrap_content"
            android:layout_weight="1" android:layout_marginEnd="6dp"
            android:text="8B veloce" android:textSize="11sp"
            android:backgroundTint="#121826" android:textColor="#00E5FF"/>
        <Button android:id="@+id/btn_model_scout"
            android:layout_width="0dp" android:layout_height="wrap_content"
            android:layout_weight="1"
            android:text="Llama 4" android:textSize="11sp"
            android:backgroundTint="#121826" android:textColor="#00E5FF"/>
    </LinearLayout>

    <TextView android:layout_width="wrap_content" android:layout_height="wrap_content"
        android:text="Personalità" android:textColor="#5A7A99" android:textSize="12sp"/>
    <RadioGroup android:id="@+id/rg_personality"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:layout_marginBottom="20dp">
        <RadioButton android:id="@+id/rb_amichevole"
            android:layout_width="wrap_content" android:layout_height="wrap_content"
            android:text="Amichevole" android:textColor="#E8F0FF"
            android:buttonTint="#7C4DFF" android:checked="true"/>
        <RadioButton android:id="@+id/rb_professionale"
            android:layout_width="wrap_content" android:layout_height="wrap_content"
            android:text="Professionale" android:textColor="#E8F0FF"
            android:buttonTint="#7C4DFF"/>
        <RadioButton android:id="@+id/rb_divertente"
            android:layout_width="wrap_content" android:layout_height="wrap_content"
            android:text="Divertente" android:textColor="#E8F0FF"
            android:buttonTint="#7C4DFF"/>
        <RadioButton android:id="@+id/rb_sarcastica"
            android:layout_width="wrap_content" android:layout_height="wrap_content"
            android:text="Sarcastica" android:textColor="#E8F0FF"
            android:buttonTint="#7C4DFF"/>
        <RadioButton android:id="@+id/rb_motivazionale"
            android:layout_width="wrap_content" android:layout_height="wrap_content"
            android:text="Motivazionale" android:textColor="#E8F0FF"
            android:buttonTint="#7C4DFF"/>
    </RadioGroup>

    <androidx.appcompat.widget.SwitchCompat android:id="@+id/sw_voice"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:text="Risposte a voce (TTS)" android:textColor="#E8F0FF"
        android:layout_marginBottom="12dp"/>

    <androidx.appcompat.widget.SwitchCompat android:id="@+id/sw_memory"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:text="Memoria conversazione" android:textColor="#E8F0FF"
        android:layout_marginBottom="24dp"/>

    <Button android:id="@+id/btn_save_settings"
        android:layout_width="match_parent" android:layout_height="52dp"
        android:text="SALVA" android:backgroundTint="#7C4DFF" android:textColor="#FFFFFF"
        android:textStyle="bold"/>

    <TextView android:layout_width="match_parent" android:layout_height="wrap_content"
        android:text="Creator: MaikGost  •  ARIA Mobile v4.0"
        android:textColor="#5A7A99" android:textSize="12sp"
        android:gravity="center" android:layout_marginTop="24dp"/>
</LinearLayout>
</ScrollView>"""

LAYOUT_HISTORY = """\
<?xml version="1.0" encoding="utf-8"?>
<ScrollView xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent" android:layout_height="match_parent"
    android:background="#0A0E1A">
<LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content"
    android:orientation="vertical" android:padding="20dp">

    <LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content"
        android:orientation="horizontal" android:layout_marginBottom="20dp">
        <Button android:id="@+id/btn_history_back"
            android:layout_width="wrap_content" android:layout_height="wrap_content"
            android:text="&lt; Indietro" android:backgroundTint="#121826" android:textColor="#00E5FF"
            android:layout_marginEnd="10dp"/>
        <Button android:id="@+id/btn_history_clear"
            android:layout_width="wrap_content" android:layout_height="wrap_content"
            android:text="Svuota" android:backgroundTint="#FF5252" android:textColor="#FFFFFF"/>
    </LinearLayout>

    <TextView android:id="@+id/tv_history_content"
        android:layout_width="match_parent" android:layout_height="wrap_content"
        android:textColor="#E8F0FF" android:textSize="13sp" android:fontFamily="monospace"/>
</LinearLayout></ScrollView>"""

# ============================================================
#  TOOLCHAIN DISCOVERY (JDK + Android SDK)
# ============================================================
def find_java():
    bases = [
        Path("C:/Program Files/Android/Android Studio/jbr"),
        Path("C:/Program Files/Android/Android Studio/jre"),
        Path("C:/Program Files/Eclipse Adoptium"),
        Path("C:/Program Files/Java"),
        Path("C:/Program Files/Microsoft"),
        Path("C:/Program Files/Amazon Corretto"),
    ]
    for base in bases:
        if base.exists() and (base / "bin" / "java.exe").exists():
            return base
    for v in ("21", "17"):
        for base in [Path("C:/Program Files/Eclipse Adoptium"),
                     Path("C:/Program Files/Java"),
                     Path("C:/Program Files/Microsoft"),
                     Path("C:/Program Files/Amazon Corretto")]:
            if not base.exists(): continue
            try: candidates = sorted(base.iterdir(), reverse=True)
            except: continue
            for d in candidates:
                if d.is_dir() and v in d.name.lower() and (d/"bin"/"java.exe").exists():
                    return d
    jh = os.environ.get("JAVA_HOME")
    if jh and (Path(jh)/"bin"/"java.exe").exists(): return Path(jh)
    jb = shutil.which("java")
    if jb: return Path(jb).parent.parent
    return None

def find_android_sdk():
    candidates = [
        Path(os.environ.get("ANDROID_HOME", "_")),
        Path(os.environ.get("ANDROID_SDK_ROOT", "_")),
        Path(os.environ.get("LOCALAPPDATA", "_")) / "Android" / "Sdk",
        Path.home() / "AppData" / "Local" / "Android" / "Sdk",
        Path("C:/Android"), Path("C:/android-sdk"),
    ]
    for p in candidates:
        try:
            if p.exists() and (p / "platform-tools").exists(): return p
        except: continue
    return None

def download_with_retry(url, dest, attempts=3):
    for i in range(attempts):
        try:
            urllib.request.urlretrieve(url, dest)
            return True
        except Exception as e:
            warn(f"  Fallito: {e}")
            if i < attempts - 1: time.sleep(2 ** i)
    return False

def write_file(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

# ============================================================
#  PROJECT CREATION
# ============================================================
def build_kotlin_file_map():
    return {
        f"{PKG_ROOT}/AriaApp.kt":                     ARIA_APP,
        f"{PKG_CORE}/AppConfig.kt":                   APP_CONFIG,
        f"{PKG_DATA}/MessageEntity.kt":                MESSAGE_ENTITY,
        f"{PKG_DATA}/MessageDao.kt":                   MESSAGE_DAO,
        f"{PKG_DATA}/AriaDatabase.kt":                 ARIA_DATABASE,
        f"{PKG_NET}/GroqClient.kt":                    GROQ_CLIENT,
        f"{PKG_CORE}/AriaBrain.kt":                    ARIA_BRAIN,
        f"{PKG_UI}/ChatMessage.kt":                    CHAT_MESSAGE_MODEL,
        f"{PKG_UI}/AriaViewModel.kt":                  ARIA_VIEWMODEL,
        f"{PKG_UI}/AriaOrb.kt":                         ARIA_ORB,
        f"{PKG_UI}/SplashActivity.kt":                 SPLASH_ACTIVITY,
        f"{PKG_UI}/MainActivity.kt":                   MAIN_ACTIVITY,
        f"{PKG_UI}/SettingsActivity.kt":                SETTINGS_ACTIVITY,
        f"{PKG_UI}/HistoryActivity.kt":                 HISTORY_ACTIVITY,
    }

def create_project(java_path):
    title("STEP 1 - Creazione progetto ARIA Mobile v4.0")
    if PROJECT_DIR.exists():
        answer = input(f"\n  Directory {PROJECT_DIR.name} esiste. Sovrascrivere? (y/N): ").strip().lower()
        if answer == "y":
            shutil.rmtree(PROJECT_DIR)
            ok("Directory rimossa")
        else:
            ok("Uso directory esistente (i file verranno aggiornati)")

    app_src  = PROJECT_DIR / "app" / "src" / "main"
    kt_src   = app_src / "kotlin"
    res_dir  = app_src / "res"

    step(1, 8, "Gradle build files")
    write_file(PROJECT_DIR / "build.gradle",               BUILD_GRADLE_PROJECT)
    write_file(PROJECT_DIR / "settings.gradle",            SETTINGS_GRADLE)
    write_file(PROJECT_DIR / "app" / "build.gradle",       BUILD_GRADLE_APP)
    write_file(PROJECT_DIR / "app" / "proguard-rules.pro", PROGUARD_RULES)
    write_file(PROJECT_DIR / "gradle" / "wrapper" / "gradle-wrapper.properties", GRADLE_WRAPPER_PROPS)
    ok("Gradle files scritti")

    step(2, 8, "gradlew.bat")
    bat = (f"@echo off\r\nset JAVA_HOME={java_path}\r\nset PATH=%JAVA_HOME%\\bin;%PATH%\r\n"
           f"\"%JAVA_HOME%\\bin\\java.exe\" -classpath \"%~dp0gradle\\wrapper\\gradle-wrapper.jar\" "
           f"org.gradle.wrapper.GradleWrapperMain %*\r\n")
    (PROJECT_DIR / "gradlew.bat").write_text(bat, encoding="utf-8")
    ok("gradlew.bat scritto")

    step(3, 8, "Gradle wrapper JAR")
    jar = PROJECT_DIR / "gradle" / "wrapper" / "gradle-wrapper.jar"
    jar.parent.mkdir(parents=True, exist_ok=True)
    if not jar.exists():
        url = "https://raw.githubusercontent.com/gradle/gradle/v8.6.0/gradle/wrapper/gradle-wrapper.jar"
        if download_with_retry(url, jar):
            ok("Wrapper JAR scaricato")
        else:
            warn("JAR mancante - apri il progetto in Android Studio per generarlo")
    else:
        ok("Wrapper JAR presente")

    step(4, 8, "AndroidManifest.xml")
    write_file(app_src / "AndroidManifest.xml", MANIFEST)
    ok("Manifest scritto (launcher = SplashActivity)")

    step(5, 8, "Kotlin source files")
    kt_files = build_kotlin_file_map()
    for rel, content in kt_files.items():
        write_file(kt_src / rel, content)
    ok(f"{len(kt_files)} file Kotlin scritti")

    step(6, 8, "Layout XML e resources")
    layouts = {
        "activity_settings.xml": LAYOUT_SETTINGS,
        "activity_history.xml":  LAYOUT_HISTORY,
    }
    for name, content in layouts.items():
        write_file(res_dir / "layout" / name, content)
    write_file(res_dir / "values" / "strings.xml", STRINGS_XML)
    write_file(res_dir / "values" / "themes.xml", THEMES_XML)
    write_file(res_dir / "drawable" / "ic_aria.xml", IC_ARIA_XML)
    ok("Layout e resources scritti")

    step(7, 8, "gradle.properties + local.properties")
    java_esc = str(java_path).replace("\\", "\\\\")
    sdk = find_android_sdk()
    write_file(PROJECT_DIR / "gradle.properties",
        "org.gradle.jvmargs=-Xmx3072m -XX:MaxMetaspaceSize=512m\n"
        "android.useAndroidX=true\n"
        "kotlin.code.style=official\n"
        f"org.gradle.java.home={java_esc}\n"
        "org.gradle.parallel=true\n"
        "org.gradle.configuration-cache=false\n"
        "android.suppressUnsupportedCompileSdk=34\n")
    if sdk:
        write_file(PROJECT_DIR / "local.properties",
            f"sdk.dir={str(sdk).replace(chr(92), '/')}\n")
        ok(f"SDK: {sdk}")
    else:
        warn("SDK non trovato - configura local.properties manualmente")

    step(8, 8, ".gitignore")
    write_file(PROJECT_DIR / ".gitignore",
        ".gradle/\nbuild/\napp/build/\nlocal.properties\n*.jks\n.idea/\n*.iml\n")
    ok(".gitignore scritto")

    kc = sum(1 for _ in kt_src.rglob("*.kt"))
    rc = sum(1 for _ in res_dir.rglob("*") if _.is_file())
    ok(f"Progetto creato: {kc} Kotlin, {rc} resource files")
    ok(f"Location: {PROJECT_DIR}")

# ============================================================
#  BUILD
# ============================================================
def build_apk(java_path):
    title("STEP 2 - Compilazione APK")
    env = os.environ.copy()
    env["JAVA_HOME"] = str(java_path)
    env["PATH"] = str(java_path / "bin") + os.pathsep + env.get("PATH", "")
    sdk = find_android_sdk()
    if sdk:
        env["ANDROID_HOME"] = str(sdk)
        env["ANDROID_SDK_ROOT"] = str(sdk)
    info("Prima volta: Gradle scarica le dipendenze (Compose, Room, Retrofit) - 5-15 min con internet")
    try:
        subprocess.run(
            "gradlew.bat assembleDebug --no-daemon --stacktrace",
            shell=True, cwd=PROJECT_DIR, env=env, check=True
        )
        ok("BUILD SUCCESSFUL")
    except subprocess.CalledProcessError:
        err("Build fallita - vedi log sopra")
        return None
    apk = PROJECT_DIR / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
    return apk if apk.exists() else None

def summarise(apk):
    title("STEP 3 - Output")
    dest = DESKTOP / "ARIA-Mobile-v4.0.apk"
    if apk and apk.exists():
        shutil.copy2(apk, dest)
        print(f"\n{C.BOLD}{'='*60}")
        print(f"  APK: {dest}")
        print(f"  Dimensione: {dest.stat().st_size/1_048_576:.1f} MB")
        print(f"{'='*60}{C.RESET}")
        ok("APK pronto!")
    else:
        warn("Compila in Android Studio se il builder da riga di comando fallisce")
        info(str(PROJECT_DIR))

    print(f"\n{C.BOLD}SETUP:{C.RESET}")
    info("1. Installa ARIA-Mobile-v4.0.apk sul telefono")
    info("2. All'avvio vedrai la splash 3D con 'Creator: MaikGost'")
    info("3. In chat tocca l'INGRANAGGIO in alto -> inserisci la Groq API key")
    info("   (usa 'Prova connessione' per verificare che funzioni)")
    info("4. Cambia nome assistente, il tuo nome e la personalita' dell'AI")
    info("5. LA VOCE E' GIA' ATTIVA: l'altoparlante in alto la accende/spegne,")
    info("   l'icona 🔊 sotto ogni risposta la fa riascoltare")
    info("   (se non senti nulla: alza il volume media e controlla che sul")
    info("   telefono sia installata 'Sintesi vocale Google')")
    info("6. Il pulsante ✨ apre i 10 STRUMENTI, il microfono detta i messaggi")
    info("7. In alto nella chat c'e' la SFERA 3D VIVA: cambia colore quando")
    info("   pensa/parla e TOCCANDOLA attivi il microfono per parlarle")
    print()

def main():
    if platform.system() == "Windows":
        os.system("color")
    print(f"\n{C.BOLD}{C.CYAN}{'='*60}")
    print("  ARIA Mobile v4.0 - Builder Android (Kotlin + Compose)")
    print("  Creator: MaikGost")
    print(f"{'='*60}{C.RESET}\n")

    title("Prerequisiti")
    java = find_java()
    if not java:
        err("JDK 17/21 non trovato -> https://adoptium.net")
        sys.exit(1)
    ok(f"JDK: {java}")
    sdk = find_android_sdk()
    if sdk:
        ok(f"Android SDK: {sdk}")
    else:
        warn("Android SDK non trovato (serve per compilare)")
    ok(f"Python {sys.version_info.major}.{sys.version_info.minor}")

    try:
        create_project(java)
        apk = build_apk(java)
        summarise(apk)
        print(f"{C.OK}{C.BOLD}ARIA Mobile v4.0 - Completato!{C.RESET}\n")
    except KeyboardInterrupt:
        print(f"\n{C.WARN}Interrotto.{C.RESET}")
        sys.exit(0)
    except Exception as e:
        err(f"Errore: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
