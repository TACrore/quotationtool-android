[app]
title = 报价单工具
package.name = quotationtool
package.domain = cn.wzshenyi
version = 1.6.16
source.dir = .
source.include_exts = py,png,jpg,jpeg,ttf,json
source.exclude_dirs = bin,.buildozer,__pycache__,data,.github,.gitcode
source.exclude_patterns = test_*.py,*_shot*.py,*.pyc,*.log,crash.log

requirements = python3,kivy==2.3.1,certifi

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,REQUEST_INSTALL_PACKAGES
android.api = 33
android.minapi = 24
android.ndk_api = 24
android.archs = arm64-v8a
android.allow_backup = True
android.add_assets = sy-cjk.ttf,feishu_android.json,assets/logo.png,assets/seal.png
icon.filename = %(source.dir)s/assets/icon.png
presplash.filename = %(source.dir)s/assets/presplash.png
android.accept_sdk_license = True
p4a.source_dir = /home/runner/p4a

[buildozer]
log_level = 2
warn_on_root = 1
