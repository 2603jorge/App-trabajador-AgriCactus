# =============================================================================
#  AgriCactus - App del TRABAJADOR  (main.py)
#  v2.0 - Colores corporativos, WiFi Direct, validación por cuadrillero
#
#  COLORES AGRICACTUS:
#    Verde oscuro : #2d4a1e  (fondo encabezado, botones principales)
#    Verde medio  : #4a6741  (acentos, bordes)
#    Amarillo/oro : #f5a623  (highlights, iconos activos)
#    Blanco       : #ffffff  (texto sobre verde)
#    Gris claro   : #f5f5f0  (fondo de pantallas)
# =============================================================================

import datetime
import json
import os
import socket
import threading

from kivy.lang import Builder
from kivy.clock import Clock
from kivy.properties import StringProperty, BooleanProperty, ListProperty, NumericProperty
from kivy.uix.screenmanager import Screen, FadeTransition
from kivy.utils import platform
from kivymd.app import MDApp
from kivymd.uix.snackbar import Snackbar

# --- GPS (plyer) ---
try:
    from plyer import gps, filechooser
    GPS_DISPONIBLE = True
except Exception:
    GPS_DISPONIBLE = False

# --- BLE nativo Android ---
if platform == 'android':
    try:
        from jnius import autoclass, PythonJavaClass, java_method
        BluetoothAdapter  = autoclass('android.bluetooth.BluetoothAdapter')
        AdvertiseSettings = autoclass('android.bluetooth.le.AdvertiseSettings')
        AdvertiseData     = autoclass('android.bluetooth.le.AdvertiseData')
        ParcelUuid        = autoclass('android.os.ParcelUuid')
        UUID              = autoclass('java.util.UUID')

        class _AdvertiseCallback(PythonJavaClass):
            __javainterfaces__ = ['android/bluetooth/le/AdvertiseCallback']
            __javacontext__ = 'app'

            def __init__(self, on_inicio, on_falla):
                super().__init__()
                self._on_inicio = on_inicio
                self._on_falla  = on_falla

            @java_method('(Landroid/bluetooth/le/AdvertiseSettings;)V')
            def onStartSuccess(self, settings):
                Clock.schedule_once(lambda dt: self._on_inicio(), 0)

            @java_method('(I)V')
            def onStartFailure(self, errorCode):
                Clock.schedule_once(lambda dt: self._on_falla(errorCode), 0)

        BLE_DISPONIBLE = True
    except Exception:
        BLE_DISPONIBLE = False
else:
    BLE_DISPONIBLE = False

# =============================================================================
#  CONSTANTES
# =============================================================================
VERDE_OSCURO  = (0.18, 0.29, 0.12, 1)   # #2d4a1e
VERDE_MEDIO   = (0.29, 0.40, 0.25, 1)   # #4a6741
AMARILLO      = (0.96, 0.65, 0.14, 1)   # #f5a623
FONDO_GRIS    = (0.96, 0.96, 0.94, 1)   # #f5f5f0

ARCHIVO_DATOS  = "empleado_data.json"
PUERTO_WIFI    = 45678
MAX_FALTAS     = 3          # Faltas consecutivas antes de bloqueo
DIAS_LABORALES = {0,1,2,3,4}  # Lunes-Viernes

# =============================================================================
#  PERSISTENCIA
# =============================================================================
def guardar_datos(datos: dict):
    try:
        with open(ARCHIVO_DATOS, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[STORAGE] Error al guardar: {e}")

def cargar_datos() -> dict:
    if os.path.exists(ARCHIVO_DATOS):
        try:
            with open(ARCHIVO_DATOS, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

# =============================================================================
#  LOGICA DE FALTAS Y ASISTENCIA
# =============================================================================
def es_dia_laboral(fecha: datetime.date) -> bool:
    return fecha.weekday() in DIAS_LABORALES

def calcular_faltas_consecutivas(historial: list) -> int:
    """
    Cuenta dias laborales consecutivos SIN asistencia hacia atras desde ayer.
    Dias con estatus 'incapacidad' o 'vacaciones' NO cuentan como falta.
    """
    dias_ok = set()
    for entrada in historial:
        f_str   = entrada.get("fecha", "")
        estatus = entrada.get("estatus", "presente")
        if f_str and estatus in ("presente", "incapacidad", "vacaciones"):
            try:
                dias_ok.add(datetime.date.fromisoformat(f_str))
            except Exception:
                pass

    faltas = 0
    fecha  = datetime.date.today() - datetime.timedelta(days=1)
    for _ in range(60):
        if not es_dia_laboral(fecha):
            fecha -= datetime.timedelta(days=1)
            continue
        if fecha in dias_ok:
            break
        faltas += 1
        fecha -= datetime.timedelta(days=1)
    return faltas

def mes_actual_str() -> str:
    return datetime.date.today().strftime("%Y-%m")

def agregar_dia_historial(historial: list, estatus: str = "presente") -> list:
    """Agrega o actualiza el dia de hoy en el historial."""
    hoy     = datetime.date.today().isoformat()
    mes     = mes_actual_str()
    entrada = {"fecha": hoy, "estatus": estatus, "mes": mes}
    for i, e in enumerate(historial):
        if e.get("fecha") == hoy:
            historial[i] = entrada
            return historial
    historial.append(entrada)
    return historial

def contar_faltas_mes(historial: list) -> int:
    mes = mes_actual_str()
    return sum(
        1 for e in historial
        if e.get("mes") == mes and e.get("estatus") == "falta"
    )

# =============================================================================
#  INTERFAZ KV
# =============================================================================
KV = '''
#:import FadeTransition kivy.uix.screenmanager.FadeTransition
#:import FitImage kivymd.uix.fitimage.FitImage

ScreenManager:
    transition: FadeTransition()
    PantallaRegistro:
    PantallaActiva:
    PantallaInactiva:


# ═══════════════════════════════════════════════════════
#  PANTALLA 1: REGISTRO
# ═══════════════════════════════════════════════════════
<PantallaRegistro>:
    name: 'registro'

    MDFloatLayout:
        md_bg_color: 0.96, 0.96, 0.94, 1

        # ── Encabezado verde ──────────────────────────
        MDFloatLayout:
            size_hint_y: 0.18
            pos_hint: {'x': 0, 'top': 1}
            md_bg_color: 0.18, 0.29, 0.12, 1

            Image:
                source: "logo_agricactus.png"
                size_hint: (0.38, 0.80)
                allow_stretch: True
                keep_ratio: True
                pos_hint: {'center_x': 0.22, 'center_y': 0.5}

            MDLabel:
                text: "REGISTRO DE EMPLEADO"
                font_style: "H6"
                bold: True
                halign: "center"
                theme_text_color: "Custom"
                text_color: 1, 1, 1, 1
                pos_hint: {'center_x': 0.64, 'center_y': 0.5}
                size_hint: (0.6, 1)

        # ── Franja amarilla decorativa ────────────────
        MDBoxLayout:
            size_hint_y: 0.006
            pos_hint: {'x': 0, 'top': 0.82}
            md_bg_color: 0.96, 0.65, 0.14, 1

        # ── Campos de datos ───────────────────────────
        MDTextField:
            id: input_nombre
            hint_text: "Nombre Completo"
            helper_text: "Se convertira a MAYUSCULAS"
            helper_text_mode: "on_focus"
            line_color_focus: 0.18, 0.29, 0.12, 1
            pos_hint: {'center_x': 0.5, 'center_y': 0.73}
            size_hint_x: 0.88

        MDTextField:
            id: input_nss
            hint_text: "Numero de Seguro Social (NSS)"
            max_text_length: 11
            input_filter: "int"
            line_color_focus: 0.18, 0.29, 0.12, 1
            pos_hint: {'center_x': 0.5, 'center_y': 0.61}
            size_hint_x: 0.88

        MDTextField:
            id: input_credencial
            hint_text: "Numero de Credencial / Empleado"
            input_filter: "int"
            line_color_focus: 0.18, 0.29, 0.12, 1
            pos_hint: {'center_x': 0.5, 'center_y': 0.49}
            size_hint_x: 0.88

        MDTextField:
            id: input_cuadrilla
            hint_text: "Numero de Cuadrilla"
            input_filter: "int"
            line_color_focus: 0.18, 0.29, 0.12, 1
            pos_hint: {'center_x': 0.5, 'center_y': 0.38}
            size_hint_x: 0.88

        # ── Botón foto ────────────────────────────────
        MDRectangleFlatIconButton:
            icon: "camera"
            text: "SELECCIONAR FOTO DE GALERIA"
            theme_text_color: "Custom"
            text_color: 0.18, 0.29, 0.12, 1
            line_color: 0.18, 0.29, 0.12, 1
            pos_hint: {'center_x': 0.5, 'center_y': 0.28}
            size_hint_x: 0.88
            on_release: root.abrir_galeria()

        MDLabel:
            id: label_foto
            text: "Sin foto seleccionada"
            font_style: "Caption"
            halign: "center"
            theme_text_color: "Custom"
            text_color: 0.5, 0.5, 0.5, 1
            pos_hint: {'center_x': 0.5, 'center_y': 0.22}

        # ── Botón guardar ─────────────────────────────
        MDRaisedButton:
            text: "GENERAR CREDENCIAL DIGITAL"
            md_bg_color: 0.18, 0.29, 0.12, 1
            pos_hint: {'center_x': 0.5, 'center_y': 0.10}
            size_hint_x: 0.88
            elevation: 4
            on_release: root.guardar_registro()


# ═══════════════════════════════════════════════════════
#  PANTALLA 2: CREDENCIAL ACTIVA
# ═══════════════════════════════════════════════════════
<PantallaActiva>:
    name: 'activa'

    MDFloatLayout:
        md_bg_color: 0.96, 0.96, 0.94, 1

        # ── Franja lateral verde ──────────────────────
        MDFloatLayout:
            size_hint_x: 0.06
            pos_hint: {'x': 0, 'y': 0}
            md_bg_color: 0.18, 0.29, 0.12, 1

        # ── Tarjeta principal ─────────────────────────
        MDCard:
            size_hint: (0.92, 0.88)
            pos_hint: {'right': 0.99, 'center_y': 0.50}
            elevation: 3
            radius: [12, 12, 12, 12]
            md_bg_color: 1, 1, 1, 1

            MDFloatLayout:

                # Encabezado verde de tarjeta
                MDFloatLayout:
                    size_hint_y: 0.18
                    pos_hint: {'x': 0, 'top': 1}
                    md_bg_color: 0.18, 0.29, 0.12, 1

                    Image:
                        source: "logo_agricactus.png"
                        size_hint: (0.48, 0.82)
                        allow_stretch: True
                        keep_ratio: True
                        pos_hint: {'center_x': 0.28, 'center_y': 0.5}

                    MDLabel:
                        text: "CREDENCIAL DIGITAL"
                        font_style: "Caption"
                        bold: True
                        halign: "center"
                        theme_text_color: "Custom"
                        text_color: 0.96, 0.65, 0.14, 1
                        pos_hint: {'center_x': 0.74, 'center_y': 0.62}
                        size_hint: (0.5, 0.2)

                    MDLabel:
                        text: root.texto_vigencia
                        font_style: "Caption"
                        halign: "center"
                        theme_text_color: "Custom"
                        text_color: 0.8, 0.9, 0.8, 1
                        pos_hint: {'center_x': 0.74, 'center_y': 0.34}
                        size_hint: (0.5, 0.2)

                # Foto del empleado
                FitImage:
                    source: root.ruta_foto
                    size_hint: (0.34, 0.35)
                    pos_hint: {'x': 0.04, 'center_y': 0.56}
                    radius: [8, 8, 8, 8]

                # Nombre
                MDLabel:
                    text: root.nombre_empleado
                    markup: True
                    font_style: "H6"
                    bold: True
                    halign: "left"
                    valign: "center"
                    theme_text_color: "Custom"
                    text_color: 0.18, 0.29, 0.12, 1
                    text_size: self.size
                    pos_hint: {'x': 0.42, 'center_y': 0.62}
                    size_hint: (0.55, 0.18)

                # Fecha de ingreso
                MDLabel:
                    text: "Ingreso: " + root.fecha_ingreso
                    font_style: "Caption"
                    halign: "left"
                    theme_text_color: "Secondary"
                    pos_hint: {'x': 0.42, 'center_y': 0.52}
                    size_hint: (0.55, 0.06)

                # Cuadrilla
                MDLabel:
                    text: "Cuadrilla: " + root.num_cuadrilla
                    font_style: "Body2"
                    bold: True
                    halign: "left"
                    theme_text_color: "Custom"
                    text_color: 0.29, 0.40, 0.25, 1
                    pos_hint: {'x': 0.42, 'center_y': 0.46}
                    size_hint: (0.55, 0.06)

                # Linea separadora amarilla
                MDBoxLayout:
                    size_hint: (0.88, 0.005)
                    pos_hint: {'center_x': 0.5, 'center_y': 0.38}
                    md_bg_color: 0.96, 0.65, 0.14, 1

                # NSS
                MDLabel:
                    text: "NSS: " + root.nss
                    font_style: "Body2"
                    bold: True
                    halign: "left"
                    theme_text_color: "Custom"
                    text_color: 0.18, 0.29, 0.12, 1
                    pos_hint: {'x': 0.06, 'center_y': 0.33}
                    size_hint: (0.5, 0.06)

                # Numero credencial grande
                MDLabel:
                    text: "No. " + root.num_credencial
                    font_style: "H5"
                    bold: True
                    halign: "center"
                    theme_text_color: "Custom"
                    text_color: 0.18, 0.29, 0.12, 1
                    pos_hint: {'center_x': 0.5, 'center_y': 0.24}
                    size_hint: (0.88, 0.08)

                # Estado BLE / WiFi
                MDLabel:
                    text: root.texto_estado_conexion
                    font_style: "Caption"
                    halign: "center"
                    theme_text_color: "Custom"
                    text_color: root.color_estado
                    pos_hint: {'center_x': 0.5, 'center_y': 0.15}
                    size_hint: (0.88, 0.06)

                # Icono Bluetooth animado
                MDIcon:
                    id: icono_ble
                    icon: "bluetooth-connect"
                    theme_text_color: "Custom"
                    text_color: root.color_icono_ble
                    font_size: "32sp"
                    pos_hint: {'center_x': 0.14, 'center_y': 0.15}

                # GPS
                MDLabel:
                    text: root.texto_gps
                    font_style: "Caption"
                    halign: "center"
                    theme_text_color: "Secondary"
                    pos_hint: {'center_x': 0.5, 'center_y': 0.06}
                    size_hint: (0.88, 0.05)

                # Pie de tarjeta verde
                MDFloatLayout:
                    size_hint_y: 0.04
                    pos_hint: {'x': 0, 'y': 0}
                    md_bg_color: 0.18, 0.29, 0.12, 1
                    MDLabel:
                        text: "Blvd. Kino 309, Piso 6 - Hermosillo, Sonora"
                        font_style: "Caption"
                        halign: "center"
                        theme_text_color: "Custom"
                        text_color: 0.8, 0.9, 0.8, 1


# ═══════════════════════════════════════════════════════
#  PANTALLA 3: CREDENCIAL BLOQUEADA
# ═══════════════════════════════════════════════════════
<PantallaInactiva>:
    name: 'inactiva'

    MDFloatLayout:
        md_bg_color: 0.12, 0.08, 0.08, 1

        MDFloatLayout:
            size_hint_y: 0.20
            pos_hint: {'x': 0, 'top': 1}
            md_bg_color: 0.72, 0.10, 0.10, 1

            Image:
                source: "logo_agricactus.png"
                size_hint: (0.30, 0.68)
                allow_stretch: True
                keep_ratio: True
                pos_hint: {'center_x': 0.5, 'center_y': 0.5}
                opacity: 0.4

        MDIcon:
            icon: "lock-alert"
            theme_text_color: "Custom"
            text_color: 0.72, 0.10, 0.10, 1
            font_size: "56sp"
            pos_hint: {'center_x': 0.5, 'center_y': 0.74}

        MDLabel:
            text: "CREDENCIAL BLOQUEADA"
            font_style: "H5"
            bold: True
            halign: "center"
            theme_text_color: "Custom"
            text_color: 1, 1, 1, 1
            pos_hint: {'center_x': 0.5, 'center_y': 0.64}
            size_hint: (0.9, 0.07)

        MDLabel:
            text: root.motivo_bloqueo
            font_style: "Body2"
            halign: "center"
            theme_text_color: "Custom"
            text_color: 0.9, 0.7, 0.7, 1
            pos_hint: {'center_x': 0.5, 'center_y': 0.56}
            size_hint: (0.88, 0.08)

        MDLabel:
            text: root.texto_faltas
            font_style: "H6"
            bold: True
            halign: "center"
            theme_text_color: "Custom"
            text_color: 0.96, 0.65, 0.14, 1
            pos_hint: {'center_x': 0.5, 'center_y': 0.49}
            size_hint: (0.88, 0.06)

        MDBoxLayout:
            size_hint: (0.8, 0.003)
            pos_hint: {'center_x': 0.5, 'center_y': 0.43}
            md_bg_color: 0.4, 0.25, 0.25, 1

        # Aviso: solo RH puede desbloquear
        MDCard:
            size_hint: (0.88, 0.16)
            pos_hint: {'center_x': 0.5, 'center_y': 0.34}
            elevation: 2
            radius: [8, 8, 8, 8]
            md_bg_color: 0.20, 0.14, 0.14, 1

            MDBoxLayout:
                orientation: 'vertical'
                padding: '10dp'
                spacing: '4dp'

                MDIcon:
                    icon: "office-building"
                    theme_text_color: "Custom"
                    text_color: 0.96, 0.65, 0.14, 1
                    font_size: "24sp"
                    halign: "center"

                MDLabel:
                    text: "Presentate a Recursos Humanos"
                    font_style: "Body1"
                    bold: True
                    halign: "center"
                    theme_text_color: "Custom"
                    text_color: 0.96, 0.65, 0.14, 1

                MDLabel:
                    text: "RH evaluara tus faltas e incapacidades\\ny desbloqueara tu credencial si procede."
                    font_style: "Caption"
                    halign: "center"
                    theme_text_color: "Custom"
                    text_color: 0.75, 0.60, 0.60, 1

        MDBoxLayout:
            size_hint: (0.8, 0.003)
            pos_hint: {'center_x': 0.5, 'center_y': 0.23}
            md_bg_color: 0.4, 0.25, 0.25, 1

        # Selector de tipo de desbloqueo (RH elige al estar presente)
        MDLabel:
            text: "Desbloqueo autorizado por RH:"
            font_style: "Caption"
            halign: "center"
            theme_text_color: "Custom"
            text_color: 0.65, 0.65, 0.65, 1
            pos_hint: {'center_x': 0.5, 'center_y': 0.19}
            size_hint: (0.88, 0.04)

        MDBoxLayout:
            orientation: 'horizontal'
            size_hint: (0.88, 0.07)
            pos_hint: {'center_x': 0.5, 'center_y': 0.13}
            spacing: '6dp'

            MDRaisedButton:
                id: btn_tipo_falta
                text: "FALTAS"
                md_bg_color: 0.50, 0.15, 0.15, 1
                size_hint_x: 0.33
                on_release: root.seleccionar_tipo('falta')

            MDRaisedButton:
                id: btn_tipo_incapacidad
                text: "INCAPACIDAD"
                md_bg_color: 0.29, 0.40, 0.25, 1
                size_hint_x: 0.33
                on_release: root.seleccionar_tipo('incapacidad')

            MDRaisedButton:
                id: btn_tipo_vacaciones
                text: "VACACIONES"
                md_bg_color: 0.18, 0.29, 0.45, 1
                size_hint_x: 0.34
                on_release: root.seleccionar_tipo('vacaciones')

        # PIN RH + boton desbloquear
        MDBoxLayout:
            orientation: 'horizontal'
            size_hint: (0.88, 0.08)
            pos_hint: {'center_x': 0.5, 'center_y': 0.05}
            spacing: '8dp'

            MDTextField:
                id: pin_input
                hint_text: "PIN de RH"
                password: True
                line_color_focus: 0.96, 0.65, 0.14, 1
                hint_text_color_focus: 0.96, 0.65, 0.14, 1
                text_color_focus: 1, 1, 1, 1
                size_hint_x: 0.5
                halign: "center"

            MDRaisedButton:
                text: "APLICAR"
                md_bg_color: 0.96, 0.65, 0.14, 1
                text_color: 0.18, 0.29, 0.12, 1
                size_hint_x: 0.5
                elevation: 4
                on_release: root.intentar_reactivacion()
'''


# =============================================================================
#  CLASES DE PANTALLA
# =============================================================================
class PantallaRegistro(Screen):
    ruta_foto_seleccionada = ""

    def abrir_galeria(self):
        if GPS_DISPONIBLE:
            try:
                from plyer import filechooser as fc
                fc.open_file(
                    title="Selecciona tu foto de perfil",
                    filters=[("Imagenes", "*.jpg", "*.jpeg", "*.png")],
                    on_selection=self.al_seleccionar_foto
                )
            except Exception as e:
                self.ids.label_foto.text = f"Error al abrir galeria: {e}"
        else:
            self.ids.label_foto.text = "Galeria no disponible en escritorio"

    def al_seleccionar_foto(self, seleccion):
        if seleccion:
            self.ruta_foto_seleccionada = seleccion[0]
            nombre_archivo = os.path.basename(self.ruta_foto_seleccionada)
            self.ids.label_foto.text = f"OK: {nombre_archivo}"

    def guardar_registro(self):
        nombre     = self.ids.input_nombre.text.strip().upper()
        nss        = self.ids.input_nss.text.strip()
        credencial = self.ids.input_credencial.text.strip()
        cuadrilla  = self.ids.input_cuadrilla.text.strip()

        errores = []
        if not nombre:
            errores.append("nombre")
        if len(nss) < 10:
            errores.append("NSS valido (min 10 digitos)")
        if not credencial:
            errores.append("numero de credencial")
        if not cuadrilla:
            errores.append("numero de cuadrilla")
        if not self.ruta_foto_seleccionada:
            errores.append("foto")

        if errores:
            Snackbar(text=f"Falta: {', '.join(errores)}").open()
            return

        app = MDApp.get_running_app()
        pa  = app.root.get_screen('activa')

        # Formatear nombre en dos lineas
        palabras = nombre.split()
        if len(palabras) >= 3:
            nombre_fmt = f"{palabras[0]} {palabras[1]}\n{' '.join(palabras[2:])}"
        elif len(palabras) == 2:
            nombre_fmt = f"{palabras[0]}\n{palabras[1]}"
        else:
            nombre_fmt = nombre

        pa.nombre_empleado = nombre_fmt
        pa.nss             = nss
        pa.num_credencial  = credencial
        pa.num_cuadrilla   = cuadrilla
        pa.ruta_foto       = self.ruta_foto_seleccionada
        pa.fecha_ingreso   = datetime.date.today().strftime("%d/%m/%Y")

        datos = {
            "nombre":            nombre_fmt,
            "nss":               nss,
            "credencial":        credencial,
            "cuadrilla":         cuadrilla,
            "foto":              self.ruta_foto_seleccionada,
            "fecha_ingreso":     pa.fecha_ingreso,
            "ultima_asistencia": datetime.datetime.now().isoformat()
        }
        guardar_datos(datos)

        app.ultima_asistencia = datetime.datetime.now()
        app.encender_ble(credencial)
        app.iniciar_servidor_wifi(credencial, cuadrilla)
        app.iniciar_gps()
        app.root.current = 'activa'
        Snackbar(text="Credencial generada correctamente").open()


class PantallaActiva(Screen):
    nombre_empleado       = StringProperty("")
    fecha_ingreso         = StringProperty("")
    nss                   = StringProperty("")
    num_credencial        = StringProperty("")
    num_cuadrilla         = StringProperty("")
    texto_vigencia        = StringProperty("Vigencia: activa")
    ruta_foto             = StringProperty("")
    color_icono_ble       = ListProperty([0.96, 0.65, 0.14, 1])
    texto_gps             = StringProperty("GPS: sin senal")
    texto_estado_conexion = StringProperty("Esperando cuadrillero...")
    color_estado          = ListProperty([0.6, 0.6, 0.6, 1])


class PantallaInactiva(Screen):
    PIN_RH         = "RH2024"   # En produccion viene cifrado del servidor
    motivo_bloqueo = StringProperty("3 faltas consecutivas registradas.")
    texto_faltas   = StringProperty("Presentate a Recursos Humanos")
    _tipo_seleccionado = "falta"   # falta | incapacidad | vacaciones

    def seleccionar_tipo(self, tipo: str):
        """
        RH selecciona el tipo de ausencia antes de ingresar el PIN.
        Actualiza visualmente el boton activo.
        """
        self._tipo_seleccionado = tipo
        colores = {
            "falta":       [0.50, 0.15, 0.15, 1],
            "incapacidad": [0.29, 0.40, 0.25, 1],
            "vacaciones":  [0.18, 0.29, 0.45, 1],
        }
        apagado = [0.25, 0.25, 0.25, 1]

        self.ids.btn_tipo_falta.md_bg_color       = apagado
        self.ids.btn_tipo_incapacidad.md_bg_color = apagado
        self.ids.btn_tipo_vacaciones.md_bg_color  = apagado

        btn_map = {
            "falta":       "btn_tipo_falta",
            "incapacidad": "btn_tipo_incapacidad",
            "vacaciones":  "btn_tipo_vacaciones",
        }
        self.ids[btn_map[tipo]].md_bg_color = colores[tipo]
        Snackbar(text=f"Tipo seleccionado: {tipo.upper()}").open()

    def intentar_reactivacion(self):
        """
        Solo RH puede desbloquear ingresando su PIN.
        RH elige previamente el tipo:
          - falta:       acepta las faltas, resetea contador
          - incapacidad: justifica las ausencias como incapacidad IMSS
          - vacaciones:  justifica como dias de vacaciones autorizados
        """
        pin = self.ids.pin_input.text.strip()
        self.ids.pin_input.text = ""

        if pin != self.PIN_RH:
            Snackbar(text="PIN incorrecto. Solo RH puede desbloquear.").open()
            return

        tipo = self._tipo_seleccionado
        app  = MDApp.get_running_app()
        datos = cargar_datos()
        historial = datos.get("historial", [])

        # Justificar todos los dias de falta del mes actual con el tipo elegido
        mes_hoy = mes_actual_str()
        for i, entrada in enumerate(historial):
            if (entrada.get("mes") == mes_hoy and
                    entrada.get("estatus") == "falta"):
                historial[i]["estatus"] = tipo
                historial[i]["autorizado_rh"] = True

        # Agregar dia de hoy como presente
        historial = agregar_dia_historial(historial, estatus="presente")

        faltas = calcular_faltas_consecutivas(historial)
        datos["historial"]           = historial
        datos["faltas_consecutivas"] = faltas
        datos["ultimo_desbloqueo_rh"] = {
            "fecha": datetime.date.today().isoformat(),
            "tipo":  tipo
        }
        guardar_datos(datos)

        pa = app.root.get_screen('activa')
        pa.texto_vigencia = app._texto_vigencia(faltas)
        app.encender_ble(pa.num_credencial)
        app.iniciar_servidor_wifi(pa.num_credencial, pa.num_cuadrilla)
        app.root.current = 'activa'

        mensajes = {
            "falta":       "Faltas aceptadas. Credencial desbloqueada.",
            "incapacidad": "Incapacidad registrada por RH. Credencial activa.",
            "vacaciones":  "Vacaciones registradas. Credencial activa.",
        }
        Snackbar(text=mensajes.get(tipo, "Credencial desbloqueada")).open()
        print(f"[RH] Desbloqueo tipo '{tipo}'. Faltas restantes: {faltas}")


# =============================================================================
#  APLICACION PRINCIPAL
# =============================================================================
class CredencialAgriCactusApp(MDApp):
    estado_parpadeo = BooleanProperty(False)
    _ble_callback   = None
    _wifi_thread    = None
    _wifi_activo    = False

    def build(self):
        self.advertiser = None

        self.theme_cls.theme_style     = "Light"
        self.theme_cls.primary_palette = "Green"

        controlador = Builder.load_string(KV)
        Clock.schedule_interval(self.verificar_vigencia, 30)
        Clock.schedule_interval(self.parpadear_ble, 1)
        Clock.schedule_once(self._restaurar_sesion, 0.5)
        return controlador

    # ── Restaurar sesion ─────────────────────────────────────────────────────
    def _restaurar_sesion(self, dt):
        datos = cargar_datos()
        if not datos:
            return

        pa = self.root.get_screen('activa')
        pa.nombre_empleado = datos.get("nombre", "")
        pa.nss             = datos.get("nss", "")
        pa.num_credencial  = datos.get("credencial", "")
        pa.num_cuadrilla   = datos.get("cuadrilla", "")
        pa.ruta_foto       = datos.get("foto", "")
        pa.fecha_ingreso   = datos.get("fecha_ingreso", "")

        historial = datos.get("historial", [])
        faltas    = calcular_faltas_consecutivas(historial)
        pa.texto_vigencia = self._texto_vigencia(faltas)

        if faltas >= MAX_FALTAS:
            # Credencial bloqueada — mostrar pantalla de bloqueo
            pi = self.root.get_screen('inactiva')
            pi.motivo_bloqueo = (
                f"{faltas} faltas consecutivas registradas.\n"
                "Presentate a Recursos Humanos."
            )
            pi.texto_faltas = f"Faltas del mes: {contar_faltas_mes(historial)}"
            self.root.current = 'inactiva'
        else:
            self.encender_ble(pa.num_credencial)
            self.iniciar_servidor_wifi(pa.num_credencial, pa.num_cuadrilla)
            self.iniciar_gps()
            self.root.current = 'activa'


    # ── GPS ──────────────────────────────────────────────────────────────────
    def iniciar_gps(self):
        if not GPS_DISPONIBLE:
            return
        try:
            gps.configure(
                on_location=self._on_gps_location,
                on_status=self._on_gps_status
            )
            gps.start(minTime=60000, minDistance=100)
        except Exception as e:
            print(f"[GPS] No se pudo iniciar: {e}")

    def _on_gps_location(self, **kwargs):
        lat = kwargs.get('lat', 0)
        lon = kwargs.get('lon', 0)
        texto = f"GPS: {lat:.4f}, {lon:.4f}"

        def _actualizar(dt):
            pa = self.root.get_screen('activa')
            pa.texto_gps = texto
            datos = cargar_datos()
            datos["lat"] = lat
            datos["lon"] = lon
            guardar_datos(datos)

        Clock.schedule_once(_actualizar, 0)

    def _on_gps_status(self, stype, status):
        print(f"[GPS] {stype}: {status}")

    # ── BLE Advertiser ───────────────────────────────────────────────────────
    def encender_ble(self, numero_credencial):
        if not BLE_DISPONIBLE:
            print("[BLE] No disponible en este dispositivo")
            return
        try:
            adaptador = BluetoothAdapter.getDefaultAdapter()
            if not (adaptador and adaptador.isEnabled()):
                print("[BLE] Bluetooth apagado")
                return

            self.advertiser = adaptador.getBluetoothLeAdvertiser()
            if not self.advertiser:
                print("[BLE] Dispositivo no soporta BLE advertising")
                return

            sb = AdvertiseSettings.Builder()
            sb.setAdvertiseMode(AdvertiseSettings.ADVERTISE_MODE_LOW_LATENCY)
            sb.setTxPowerLevel(AdvertiseSettings.ADVERTISE_TX_POWER_HIGH)
            sb.setConnectable(False)
            sb.setTimeout(0)
            settings = sb.build()

            # UUID incluye cuadrilla (3 digitos) + credencial (9 digitos)
            # Formato: 0000ac10-0000-1000-8000-CCC000001001
            # Asi el cuadrillero solo detecta trabajadores de SU cuadrilla
            pa = self.root.get_screen('activa')
            cuadrilla_num = int(pa.num_cuadrilla) if str(pa.num_cuadrilla).isdigit() else 0
            credencial_num = int(numero_credencial) if str(numero_credencial).isdigit() else 9999
            uuid_str = f"0000ac10-0000-1000-8000-{cuadrilla_num:03d}{credencial_num:09d}"
            db = AdvertiseData.Builder()
            db.addServiceUuid(ParcelUuid(UUID.fromString(uuid_str)))
            db.setIncludeDeviceName(False)
            data = db.build()

            self._ble_callback = _AdvertiseCallback(
                on_inicio=lambda: print("[BLE] Señal activa"),
                on_falla=lambda code: print(f"[BLE] Error codigo: {code}")
            )
            self.advertiser.startAdvertising(settings, data, self._ble_callback)
        except Exception as e:
            print(f"[BLE] Error: {e}")

    def apagar_ble(self):
        if BLE_DISPONIBLE and self.advertiser and self._ble_callback:
            try:
                self.advertiser.stopAdvertising(self._ble_callback)
            except Exception as e:
                print(f"[BLE] Error al apagar: {e}")

    # ── Servidor WiFi local (escucha validaciones del cuadrillero) ────────────
    def iniciar_servidor_wifi(self, credencial, cuadrilla):
        """
        Escucha en red WiFi local (hotspot del cuadrillero).
        El cuadrillero envía: VALIDAR:<credencial>:<cuadrilla>:<fecha>
        Esta app responde: OK:<credencial>
        Al recibir validacion, renueva la asistencia por 24h.
        """
        if self._wifi_activo:
            return

        self._wifi_activo = True

        def _escuchar():
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.bind(('', PUERTO_WIFI))
                    sock.settimeout(2.0)
                    print(f"[WIFI] Escuchando en puerto {PUERTO_WIFI}")

                    while self._wifi_activo:
                        try:
                            datos_raw, addr = sock.recvfrom(1024)
                            mensaje = datos_raw.decode('utf-8').strip()
                            print(f"[WIFI] Recibido de {addr}: {mensaje}")

                            partes = mensaje.split(':')
                            if (len(partes) >= 3 and
                                    partes[0] == 'VALIDAR' and
                                    partes[1] == str(credencial)):

                                # Responder confirmacion
                                respuesta = f"OK:{credencial}".encode('utf-8')
                                sock.sendto(respuesta, addr)

                                # Actualizar asistencia en hilo principal
                                Clock.schedule_once(
                                    lambda dt: self._registrar_asistencia_wifi(), 0
                                )

                        except socket.timeout:
                            continue
                        except Exception as e:
                            print(f"[WIFI] Error recibiendo: {e}")

            except Exception as e:
                print(f"[WIFI] Error servidor: {e}")
            finally:
                self._wifi_activo = False

        self._wifi_thread = threading.Thread(target=_escuchar, daemon=True)
        self._wifi_thread.start()

    def _registrar_asistencia_wifi(self):
        """
        Llamado cuando el cuadrillero valida la asistencia.
        Marca HOY como 'presente' en el historial y recalcula faltas.
        """
        ahora    = datetime.datetime.now()
        datos    = cargar_datos()
        historial = datos.get("historial", [])
        historial = agregar_dia_historial(historial, estatus="presente")

        faltas = calcular_faltas_consecutivas(historial)
        datos["historial"]           = historial
        datos["faltas_consecutivas"] = faltas
        datos["ultima_asistencia"]   = ahora.isoformat()
        guardar_datos(datos)

        pa = self.root.get_screen('activa')
        pa.texto_estado_conexion = f"Asistencia validada: {ahora.strftime('%H:%M')}"
        pa.color_estado          = [0.18, 0.29, 0.12, 1]
        pa.texto_vigencia        = self._texto_vigencia(faltas)

        # Si estaba bloqueado y ahora tiene menos de 3 faltas, desbloquear
        if self.root.current == 'inactiva' and faltas < MAX_FALTAS:
            self.root.current = 'activa'

        Snackbar(text="Asistencia registrada correctamente").open()
        print(f"[WIFI] Asistencia OK. Faltas consecutivas: {faltas}")

    def detener_wifi(self):
        self._wifi_activo = False

    # ── Texto de vigencia legible ─────────────────────────────────────────────
    def _texto_vigencia(self, faltas: int) -> str:
        restantes = MAX_FALTAS - faltas
        if faltas == 0:
            return "Sin faltas consecutivas"
        elif restantes == 1:
            return f"Atencion: 1 falta mas = bloqueo"
        else:
            return f"Faltas consecutivas: {faltas}/{MAX_FALTAS}"

    # ── Animacion BLE ─────────────────────────────────────────────────────────
    def parpadear_ble(self, dt):
        if self.root and self.root.current == 'activa':
            pa = self.root.get_screen('activa')
            self.estado_parpadeo = not self.estado_parpadeo
            pa.color_icono_ble = (
                [0.96, 0.65, 0.14, 1] if self.estado_parpadeo
                else [0.29, 0.40, 0.25, 0.4]
            )

    # ── Verificar vigencia por faltas ─────────────────────────────────────────
    def verificar_vigencia(self, dt):
        """
        Revisa cada 30 seg si el trabajador acumulo 3 faltas consecutivas.
        Si es dia laboral y aun no hay asistencia hoy, lo registra como falta.
        """
        datos     = cargar_datos()
        historial = datos.get("historial", [])
        hoy       = datetime.date.today()

        # Si es dia laboral y no hay entrada de hoy, registrar falta provisional
        dias_ok = {e.get("fecha") for e in historial}
        if es_dia_laboral(hoy) and hoy.isoformat() not in dias_ok:
            # Solo marcar falta si ya paso la hora de entrada (ej: despues de 8am)
            if datetime.datetime.now().hour >= 8:
                historial = agregar_dia_historial(historial, estatus="falta")
                datos["historial"] = historial
                guardar_datos(datos)

        faltas = calcular_faltas_consecutivas(historial)
        pa     = self.root.get_screen('activa')

        if faltas >= MAX_FALTAS:
            self.apagar_ble()
            self.detener_wifi()
            if self.root.current != 'inactiva':
                pi = self.root.get_screen('inactiva')
                pi.motivo_bloqueo = (
                    f"{faltas} faltas consecutivas registradas este mes.\n"
                    "Presentate a Recursos Humanos para regularizar."
                )
                pi.texto_faltas = (
                    f"Faltas del mes: {contar_faltas_mes(historial)}"
                )
                self.root.current = 'inactiva'
        else:
            if self.root.current == 'activa':
                pa.texto_vigencia = self._texto_vigencia(faltas)

    def on_stop(self):
        self.apagar_ble()
        self.detener_wifi()


if __name__ == '__main__':
    CredencialAgriCactusApp().run()
