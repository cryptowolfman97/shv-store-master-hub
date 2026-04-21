[app]

title = SHV Store Master Hub
package.name = shvmasterhub
package.domain = com.shvertex

source.dir = .
# ADDED ttf here so the font gets packed into the APK
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,txt,csv,wav,ogg,ttf
version = 2

# CLEANED UP and ADDED openssl
requirements = python3,kivy,openssl,pyjnius

orientation = portrait
fullscreen = 0

# ADDED MANAGE_EXTERNAL_STORAGE for downloading APKs
android.permissions = INTERNET, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE, REQUEST_INSTALL_PACKAGES, MANAGE_EXTERNAL_STORAGE
android.api = 33
android.minapi = 21
android.ndk_api = 21
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.enable_androidx = True
android.gradle_dependencies = androidx.core:core:1.9.0
android.add_providers = androidx.core.content.FileProvider:fileprovider:res/xml/file_paths.xml
android.allow_backup = True

[buildozer]

log_level = 2
warn_on_root = 1
