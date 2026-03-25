[app]

# App metadata
title = Expense Tracker
package.name = expensetracker
package.domain = org.example

# Source configuration
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,txt,md
source.exclude_dirs = env,.venv,venv,.git,__pycache__,bin,.buildozer,.github

# Versioning
version = 0.1

# Dependencies
requirements = python3,kivy==2.3.1

# Orientation and UI
orientation = portrait
fullscreen = 0

# Android settings
android.api = 34
android.minapi = 24
android.archs = arm64-v8a
android.accept_sdk_license = True

# Permissions
android.permissions =

# Entry point
presplash.filename =
icon.filename =

# Packaging
log_level = 2
warn_on_root = 0

[buildozer]

log_level = 2
build_dir = .buildozer
