[app]
title = AgriCactus Trabajador
package.name = agricactus_trabajador
package.domain = mx.agricactus
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,json
version = 2.0
requirements = python3,kivy,kivymd==1.1.1,plyer,pillow,android,pyjnius,qrcode,cryptography
orientation = portrait
icon.filename = %(source.dir)s/icono_uva.png
presplash.filename = %(source.dir)s/logo_agricactus.png
android.api = 33
android.minapi = 26
android.ndk = 28.2.13676358
android.archs = arm64-v8a
android.permissions = ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,ACCESS_BACKGROUND_LOCATION,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,CAMERA,READ_MEDIA_IMAGES,INTERNET,ACCESS_WIFI_STATE,CHANGE_WIFI_STATE,ACCESS_NETWORK_STATE
android.manifest.requestLegacyExternalStorage = True
android.build_tools_version = 33.0.2
android.presplash_color = #2d4a1e
android.window_softinput_mode = adjustResize

[buildozer]
log_level = 2
warn_on_root = 0
