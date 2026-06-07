[app]
title = AgriCactus Trabajador
package.name = agricactus_trabajador
package.domain = mx.agricactus
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,json
version = 2.0
requirements = python3,kivy==2.3.0,kivymd==1.2.0,plyer,pillow,android,pyjnius
orientation = portrait
icon.filename = %(source.dir)s/icono_uva.png
presplash.filename = %(source.dir)s/logo_agricactus.png
android.api = 33
android.minapi = 26
android.ndk = 25b
android.archs = arm64-v8a
android.permissions = BLUETOOTH,BLUETOOTH_ADMIN,BLUETOOTH_SCAN,BLUETOOTH_ADVERTISE,BLUETOOTH_CONNECT,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,ACCESS_BACKGROUND_LOCATION,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,CAMERA,READ_MEDIA_IMAGES,INTERNET,ACCESS_WIFI_STATE,CHANGE_WIFI_STATE,ACCESS_NETWORK_STATE
android.features = android.hardware.bluetooth_le
android.gradle_dependencies = androidx.core:core:1.9.0
android.build_tools_version = 33.0.2
android.presplash_color = #2d4a1e
android.window_softinput_mode = adjustResize

[buildozer]
log_level = 2
warn_on_root = 0
