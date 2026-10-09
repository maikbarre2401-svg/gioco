[app]
title = Maik Subs
package.name = maiksubs
package.domain = com.maik
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,json
source.exclude_dirs = bin, .buildozer, __pycache__, tests
source.exclude_patterns = test_*.py
version = 1.0.0

# python3 + Kivy (interfaccia e OpenGL 3D), plyer (notifiche, vibrazione), android (permessi)
requirements = python3,kivy==2.3.1,plyer,android

icon.filename = %(source.dir)s/assets/icon.png
presplash.filename = %(source.dir)s/assets/presplash.png
android.presplash_color = #6A4BFA
orientation = portrait
fullscreen = 0

android.permissions = POST_NOTIFICATIONS, VIBRATE
# Google Play richiede un target recente: aggiorna android.api quando Google alza il minimo.
android.api = 35
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.enable_androidx = True
# APK per installarlo a mano; per Google Play usa "buildozer android release" con aab.
android.release_artifact = aab
android.debug_artifact = apk

[buildozer]
log_level = 2
warn_on_root = 1
