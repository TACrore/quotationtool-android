[app]
title = 报价单工具
package.name = quotationtool
package.domain = cn.wzshenyi
version = 1.6.7
source.dir = .
source.include_exts = py,png,jpg,jpeg,ttf,json
source.exclude_dirs = bin,.buildozer,__pycache__,data,.github,.gitcode

requirements = python3,kivy==2.3.1,fpdf2,certifi

orientation = portrait
fullscreen = 0

android.permissions = INTERNET
android.api = 33
android.minapi = 24
android.ndk_api = 24
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True
android.add_assets = sy-cjk.ttf,feishu_android.json
icon.filename = %(source.dir)s/assets/icon.png
presplash.filename = %(source.dir)s/assets/presplash.png
android.accept_sdk_license = True
p4a.source_dir = /home/runner/p4a

[buildozer]
log_level = 2
warn_on_root = 1
