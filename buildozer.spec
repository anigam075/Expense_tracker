[app]

# App metadata
title = SpendSutra
package.name = spendsutra
package.domain = org.example

# Source configuration
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,txt,md
source.exclude_dirs = env,.venv,venv,.git,__pycache__,bin,.buildozer,.github

# Versioning
version = 0.1

# Dependencies
requirements = python3,kivy==2.3.1,filetype,pyjnius,pypdf,plyer

# Orientation and UI
orientation = portrait
fullscreen = 0

# Android settings
android.api = 34
android.minapi = 24
android.archs = arm64-v8a
android.accept_sdk_license = True
android.add_src = android_src

# Permissions
android.permissions =
p4a.hook = p4a/hook.py

# Entry point
presplash.filename = assets/presplash.png
icon.filename = assets/logo.png

# Packaging
log_level = 2
warn_on_root = 0

[buildozer]

log_level = 2
build_dir = .buildozer
