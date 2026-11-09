[app]
title = 报价单工具
package.name = quotationtool
package.domain = cn.wzshenyi
version = 1.6.7
source.dir = .
source.include_exts = py,png,jpg,jpeg,ttf,json
source.exclude_dirs = bin,.buildozer,__pycache__,data,.github

requirements = python3,kivy==2.3.1

orientation = portrait
fullscreen = 0

android.permissions = INTERNET
android.api = 33
android.minapi = 24
android.ndk_api = 24
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True
android.add_assets = sy-cjk.ttf
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
