[app]
title = Gioco
package.name = gioco
package.domain = org.maikbarre
source.dir = .
source.include_exts = py
source.exclude_dirs = tests, bin, .buildozer, .venv, .git
version = 0.1.0
requirements = python3,kivy==2.3.0,pyjnius==1.6.1
orientation = portrait
fullscreen = 1

android.permissions = CAMERA, RECORD_AUDIO
android.api = 34
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a
android.accept_sdk_license = True
android.allow_backup = False

p4a.branch = v2024.01.21
p4a.bootstrap = sdl2

[buildozer]
log_level = 2
warn_on_root = 1
