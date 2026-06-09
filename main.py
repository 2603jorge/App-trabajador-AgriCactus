# =============================================================================
#  AgriCactus - App del TRABAJADOR  (main.py)
#  v3.1 - Anuncio cada hora + GPS en mensaje
# =============================================================================

import datetime
import json
import os
import socket
import threading
import time

from kivy.lang import Builder
from kivy.clock import Clock
from kivy.properties import StringProperty, BooleanProperty, ListProperty
from kivy.uix.screenmanager import Screen, FadeTransition
from kivy.utils import platform
from kivymd.app import MDApp
from kivymd.uix.snackbar import Snackbar

try:
    from plyer import gps, filechooser
    GPS_DISPONIBLE = True
except Exception:
    GPS_DISPONIBLE = False

# =============================================================================
#  CONSTANTES
# =============================================================================
ARCHIVO_DATOS     = "empleado_data.json"
PUERTO_ANUNCIO    = 45678
PUERTO_VALIDACION = 45679
INTERVALO_ANUNCIO = 3600   # 1 hora en segundos
MAX_FALTAS        = 3
DIAS_LABORALES    = {0, 1, 2, 3, 4}
TOLERANCIA_HORAS  = 2
DIAS_GRACIA       = 3

# =============================================================================
#  PERSISTENCIA
# =============================================================================
def guardar_datos(datos: dict):
    try:
        with open(ARCHIVO_DATOS, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[STORAGE] Error: {e}")

def cargar_datos() -> dict:
    if os.path.exists(ARCHIVO_DATOS):
        try:
            with open(ARCHIVO_DATOS, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

# =============================================================================
#  LOGICA DE FALTAS
# =============================================================================
def es_dia_laboral(fecha: datetime.date) -> bool:
    return fecha.weekday() in DIAS_LABORALES

def calcular_faltas_consecutivas(historial: list) -> int:
    if not historial:
        return 0
    datos_guardados = cargar_datos()
    fecha_inicio_conteo = None
    fic_str = datos_guardados.get("fecha_inicio_conteo", "")
    if fic_str:
        try:
            fecha_inicio_conteo = datetime.date.fromisoformat(fic_str)
        except Exception:
            pass
    dias_ok = set()
    for entrada in historial:
        f_str   = entrada.get("fecha", "")
        estatus = entrada.get("estatus", "presente")
        if f_str and estatus in ("presente", "incapacidad", "vacaciones"):
            try:
                dias_ok.add(datetime.date.fromisoformat(f_str))
            except Exception:
                pass
    if not dias_ok:
        return 0
    faltas = 0
    fecha  = datetime.date.today() - datetime.timedelta(days=1)
    for _ in range(60):
        if fecha_inicio_conteo and fecha < fecha_inicio_conteo:
            break
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

def en_periodo_gracia(datos: dict) -> bool:
    fecha_ingreso_str = datos.get("fecha_ingreso", "")
    if not fecha_ingreso_str:
        return False
    try:
        fecha_ingreso = datetime.datetime.strptime(
            fecha_ingreso_str, "%d/%m/%Y"
        ).date()
        dias = (datetime.date.today() - fecha_ingreso).days
        return dias < DIAS_GRACIA
    except Exception:
        return False

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


<PantallaRegistro>:
    name: 'registro'

    MDFloatLayout:
        md_bg_color: 0.96, 0.96, 0.94, 1

        MDFloatLayout:
            size_hint_y: 0.15
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

        MDBoxLayout:
            size_hint_y: 0.006
            pos_hint: {'x': 0, 'top': 0.85}
            md_bg_color: 0.96, 0.65, 0.14, 1

        MDTextField:
            id: input_nombre
            hint_text: "Nombre Completo"
            helper_text: "Se convertira a MAYUSCULAS"
            helper_text_mode: "on_focus"
            line_color_focus: 0.18, 0.29, 0.12, 1
            pos_hint: {'center_x': 0.5, 'center_y': 0.76}
            size_hint_x: 0.88

        MDTextField:
            id: input_nss
            hint_text: "Numero de Seguro Social (NSS)"
            max_text_length: 11
            input_filter: "int"
            line_color_focus: 0.18, 0.29, 0.12, 1
            pos_hint: {'center_x': 0.5, 'center_y': 0.65}
            size_hint_x: 0.88

        MDTextField:
            id: input_credencial
            hint_text: "Numero de Credencial / Empleado"
            input_filter: "int"
            line_color_focus: 0.18, 0.29, 0.12, 1
            pos_hint: {'center_x': 0.5, 'center_y': 0.55}
            size_hint_x: 0.88

        MDTextField:
            id: input_cuadrilla
            hint_text: "Numero de Cuadrilla"
            input_filter: "int"
            line_color_focus: 0.18, 0.29, 0.12, 1
            pos_hint: {'center_x': 0.5, 'center_y': 0.45}
            size_hint_x: 0.88

        MDTextField:
            id: input_hora_entrada
            hint_text: "Hora de entrada (ej: 07:00)"
            helper_text: "Formato 24h"
            helper_text_mode: "on_focus"
            line_color_focus: 0.18, 0.29, 0.12, 1
            pos_hint: {'center_x': 0.5, 'center_y': 0.35}
            size_hint_x: 0.88

        MDBoxLayout:
            orientation: 'horizontal'
            size_hint: (0.88, 0.07)
            pos_hint: {'center_x': 0.5, 'center_y': 0.25}
            spacing: '8dp'

            MDRectangleFlatIconButton:
                icon: "camera"
                text: "CAMARA"
                theme_text_color: "Custom"
                text_color: 0.18, 0.29, 0.12, 1
                line_color: 0.18, 0.29, 0.12, 1
                size_hint_x: 0.5
                on_release: root.tomar_foto()

            MDRectangleFlatIconButton:
                icon: "image"
                text: "GALERIA"
                theme_text_color: "Custom"
                text_color: 0.18, 0.29, 0.12, 1
                line_color: 0.18, 0.29, 0.12, 1
                size_hint_x: 0.5
                on_release: root.abrir_galeria()

        MDLabel:
            id: label_foto
            text: "Sin foto seleccionada"
            font_style: "Caption"
            halign: "center"
            theme_text_color: "Custom"
            text_color: 0.5, 0.5, 0.5, 1
            pos_hint: {'center_x': 0.5, 'center_y': 0.17}

        MDRaisedButton:
            text: "GENERAR CREDENCIAL DIGITAL"
            md_bg_color: 0.18, 0.29, 0.12, 1
            pos_hint: {'center_x': 0.5, 'center_y': 0.08}
            size_hint_x: 0.88
            elevation: 4
            on_release: root.guardar_registro()


<PantallaActiva>:
    name: 'activa'

    MDFloatLayout:
        md_bg_color: 0.96, 0.96, 0.94, 1

        MDFloatLayout:
            size_hint_x: 0.06
            pos_hint: {'x': 0, 'y': 0}
            md_bg_color: 0.18, 0.29, 0.12, 1

        MDCard:
            size_hint: (0.92, 0.88)
            pos_hint: {'right': 0.99, 'center_y': 0.50}
            elevation: 3
            radius: [12, 12, 12, 12]
            md_bg_color: 1, 1, 1, 1

            MDFloatLayout:

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

                FitImage:
                    source: root.ruta_foto
                    size_hint: (0.34, 0.35)
                    pos_hint: {'x': 0.04, 'center_y': 0.56}
                    radius: [8, 8, 8, 8]

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

                MDLabel:
                    text: "Ingreso: " + root.fecha_ingreso
                    font_style: "Caption"
                    halign: "left"
                    theme_text_color: "Secondary"
                    pos_hint: {'x': 0.42, 'center_y': 0.52}
                    size_hint: (0.55, 0.06)

                MDLabel:
                    text: "Cuadrilla: " + root.num_cuadrilla
                    font_style: "Body2"
                    bold: True
                    halign: "left"
                    theme_text_color: "Custom"
                    text_color: 0.29, 0.40, 0.25, 1
                    pos_hint: {'x': 0.42, 'center_y': 0.46}
                    size_hint: (0.55, 0.06)

                MDBoxLayout:
                    size_hint: (0.88, 0.005)
                    pos_hint: {'center_x': 0.5, 'center_y': 0.38}
                    md_bg_color: 0.96, 0.65, 0.14, 1

                MDLabel:
                    text: "NSS: " + root.nss
                    font_style: "Body2"
                    bold: True
                    halign: "left"
                    theme_text_color: "Custom"
                    text_color: 0.18, 0.29, 0.12, 1
                    pos_hint: {'x': 0.06, 'center_y': 0.33}
                    size_hint: (0.5, 0.06)

                MDLabel:
                    text: "No. " + root.num_credencial
                    font_style: "H5"
                    bold: True
                    halign: "center"
                    theme_text_color: "Custom"
                    text_color: 0.18, 0.29, 0.12, 1
                    pos_hint: {'center_x': 0.5, 'center_y': 0.24}
                    size_hint: (0.88, 0.08)

                MDLabel:
                    text: root.texto_estado_conexion
                    font_style: "Caption"
                    halign: "center"
                    theme_text_color: "Custom"
                    text_color: root.color_estado
                    pos_hint: {'center_x': 0.5, 'center_y': 0.15}
                    size_hint: (0.88, 0.06)

                MDIcon:
                    icon: "wifi"
                    theme_text_color: "Custom"
                    text_color: root.color_icono_wifi
                    font_size: "32sp"
                    pos_hint: {'center_x': 0.14, 'center_y': 0.15}

                MDLabel:
                    text: root.texto_gps
                    font_style: "Caption"
                    halign: "center"
                    theme_text_color: "Secondary"
                    pos_hint: {'center_x': 0.5, 'center_y': 0.07}
                    size_hint: (0.88, 0.05)

                MDLabel:
                    text: root.texto_proximo_anuncio
                    font_style: "Caption"
                    halign: "center"
                    theme_text_color: "Custom"
                    text_color: 0.29, 0.40, 0.25, 1
                    pos_hint: {'center_x': 0.5, 'center_y': 0.03}
                    size_hint: (0.88, 0.04)

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

    def tomar_foto(self):
        if platform == 'android':
            try:
                from android.permissions import request_permissions, Permission
                from android import activity as android_activity
                from jnius import autoclass
                request_permissions([
                    Permission.CAMERA,
                    Permission.WRITE_EXTERNAL_STORAGE,
                    Permission.READ_EXTERNAL_STORAGE
                ])
                Intent         = autoclass('android.content.Intent')
                MediaStore     = autoclass('android.provider.MediaStore')
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
                PythonActivity.mActivity.startActivityForResult(intent, 1001)
                android_activity.bind(on_activity_result=self._resultado_camara)
            except Exception as e:
                self.ids.label_foto.text = f"Error camara: {e}"
        else:
            self.ids.label_foto.text = "Camara solo disponible en Android"

    def _resultado_camara(self, requestCode, resultCode, intent):
        RESULT_OK = -1
        if requestCode != 1001 or resultCode != RESULT_OK:
            self.ids.label_foto.text = "Foto cancelada"
            return
        try:
            from jnius import autoclass
            PythonActivity       = autoclass('org.kivy.android.PythonActivity')
            FileOutputStream     = autoclass('java.io.FileOutputStream')
            BitmapCompressFormat = autoclass('android.graphics.Bitmap$CompressFormat')
            extras    = intent.getExtras()
            bitmap    = extras.get("data")
            files_dir = PythonActivity.mActivity.getFilesDir().getAbsolutePath()
            ruta      = f"{files_dir}/agricactus_foto.jpg"
            fos = FileOutputStream(ruta)
            bitmap.compress(BitmapCompressFormat.JPEG, 90, fos)
            fos.close()
            self.ruta_foto_seleccionada = ruta
            self.ids.label_foto.text    = "Foto tomada correctamente"
        except Exception as e:
            self.ids.label_foto.text = f"Error guardando foto: {e}"

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
                self.ids.label_foto.text = f"Error galeria: {e}"
        else:
            self.ids.label_foto.text = "Galeria no disponible en escritorio"

    def al_seleccionar_foto(self, seleccion):
        if seleccion:
            self.ruta_foto_seleccionada = seleccion[0]
            self.ids.label_foto.text    = f"OK: {os.path.basename(seleccion[0])}"

    def guardar_registro(self):
        nombre       = self.ids.input_nombre.text.strip().upper()
        nss          = self.ids.input_nss.text.strip()
        credencial   = self.ids.input_credencial.text.strip()
        cuadrilla    = self.ids.input_cuadrilla.text.strip()
        hora_entrada = self.ids.input_hora_entrada.text.strip()

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

        hora_int = 7
        if hora_entrada:
            try:
                hora_int = int(hora_entrada.split(":")[0])
                if not (0 <= hora_int <= 23):
                    errores.append("hora valida (0-23)")
            except Exception:
                errores.append("hora en formato HH:MM")

        if errores:
            Snackbar(text=f"Falta: {', '.join(errores)}").open()
            return

        app = MDApp.get_running_app()
        pa  = app.root.get_screen('activa')

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
            "nombre":              nombre_fmt,
            "nss":                 nss,
            "credencial":          credencial,
            "cuadrilla":           cuadrilla,
            "foto":                self.ruta_foto_seleccionada,
            "fecha_ingreso":       pa.fecha_ingreso,
            "hora_entrada":        hora_int,
            "fecha_inicio_conteo": datetime.date.today().isoformat(),
            "ultima_asistencia":   datetime.datetime.now().isoformat()
        }
        guardar_datos(datos)

        app.ultima_asistencia = datetime.datetime.now()
        app.iniciar_anuncio_wifi(credencial, cuadrilla, nombre_fmt)
        app.iniciar_servidor_validacion(credencial, cuadrilla)
        app.iniciar_gps()
        app.root.current = 'activa'
        Snackbar(text="Credencial generada correctamente").open()


class PantallaActiva(Screen):
    nombre_empleado        = StringProperty("")
    fecha_ingreso          = StringProperty("")
    nss                    = StringProperty("")
    num_credencial         = StringProperty("")
    num_cuadrilla          = StringProperty("")
    texto_vigencia         = StringProperty("Sin faltas consecutivas")
    ruta_foto              = StringProperty("")
    color_icono_wifi       = ListProperty([0.96, 0.65, 0.14, 1])
    texto_gps              = StringProperty("GPS: sin senal")
    texto_estado_conexion  = StringProperty("Buscando cuadrillero...")
    color_estado           = ListProperty([0.6, 0.6, 0.6, 1])
    texto_proximo_anuncio  = StringProperty("Proximo anuncio: --:--")


class PantallaInactiva(Screen):
    PIN_RH             = "RH2024"
    motivo_bloqueo     = StringProperty("3 faltas consecutivas registradas.")
    texto_faltas       = StringProperty("Presentate a Recursos Humanos")
    _tipo_seleccionado = "falta"

    def seleccionar_tipo(self, tipo: str):
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
        pin = self.ids.pin_input.text.strip()
        self.ids.pin_input.text = ""
        if pin != self.PIN_RH:
            Snackbar(text="PIN incorrecto. Solo RH puede desbloquear.").open()
            return
        tipo  = self._tipo_seleccionado
        app   = MDApp.get_running_app()
        datos = cargar_datos()
        historial = datos.get("historial", [])
        mes_hoy = mes_actual_str()
        for i, entrada in enumerate(historial):
            if (entrada.get("mes") == mes_hoy and
                    entrada.get("estatus") == "falta"):
                historial[i]["estatus"]       = tipo
                historial[i]["autorizado_rh"] = True
        historial = agregar_dia_historial(historial, estatus="presente")
        datos["historial"]            = historial
        datos["fecha_inicio_conteo"]  = datetime.date.today().isoformat()
        datos["faltas_consecutivas"]  = 0
        datos["ultimo_desbloqueo_rh"] = {
            "fecha": datetime.date.today().isoformat(),
            "tipo":  tipo
        }
        guardar_datos(datos)
        faltas = calcular_faltas_consecutivas(historial)
        pa = app.root.get_screen('activa')
        pa.texto_vigencia = app._texto_vigencia(faltas)
        app.iniciar_anuncio_wifi(pa.num_credencial, pa.num_cuadrilla, pa.nombre_empleado)
        app.iniciar_servidor_validacion(pa.num_credencial, pa.num_cuadrilla)
        app.root.current = 'activa'
        mensajes = {
            "falta":       "Faltas aceptadas. Credencial desbloqueada.",
            "incapacidad": "Incapacidad registrada. Credencial activa.",
            "vacaciones":  "Vacaciones registradas. Credencial activa.",
        }
        Snackbar(text=mensajes.get(tipo, "Credencial desbloqueada")).open()


# =============================================================================
#  APLICACION PRINCIPAL
# =============================================================================
class CredencialAgriCactusApp(MDApp):
    estado_parpadeo    = BooleanProperty(False)
    _anuncio_activo    = False
    _validacion_activa = False
    _lat               = 0.0
    _lon               = 0.0
    _proximo_anuncio   = None

    def build(self):
        self.theme_cls.theme_style     = "Light"
        self.theme_cls.primary_palette = "Green"
        controlador = Builder.load_string(KV)
        Clock.schedule_interval(self.verificar_vigencia, 30)
        Clock.schedule_interval(self.parpadear_wifi, 1)
        Clock.schedule_interval(self._actualizar_countdown, 60)
        Clock.schedule_once(self._restaurar_sesion, 0.5)
        return controlador

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
        gracia    = en_periodo_gracia(datos)
        faltas    = 0 if gracia else calcular_faltas_consecutivas(historial)
        pa.texto_vigencia = self._texto_vigencia(faltas)
        if faltas >= MAX_FALTAS:
            pi = self.root.get_screen('inactiva')
            pi.motivo_bloqueo = (
                f"{faltas} faltas consecutivas registradas.\n"
                "Presentate a Recursos Humanos."
            )
            pi.texto_faltas = f"Faltas del mes: {contar_faltas_mes(historial)}"
            self.root.current = 'inactiva'
        else:
            cred = datos.get("credencial", "")
            cuad = datos.get("cuadrilla", "")
            nomb = datos.get("nombre", "")
            self.iniciar_anuncio_wifi(cred, cuad, nomb)
            self.iniciar_servidor_validacion(cred, cuad)
            self.iniciar_gps()
            self.root.current = 'activa'

    def iniciar_gps(self):
        if not GPS_DISPONIBLE:
            return
        try:
            gps.configure(
                on_location=self._on_gps_location,
                on_status=self._on_gps_status
            )
            gps.start(minTime=60000, minDistance=50)
        except Exception as e:
            print(f"[GPS] Error: {e}")

    def _on_gps_location(self, **kwargs):
        self._lat = kwargs.get('lat', 0.0)
        self._lon = kwargs.get('lon', 0.0)
        texto = f"GPS: {self._lat:.4f}, {self._lon:.4f}"
        def _actualizar(dt):
            pa = self.root.get_screen('activa')
            pa.texto_gps = texto
            datos = cargar_datos()
            datos["lat"] = self._lat
            datos["lon"] = self._lon
            guardar_datos(datos)
        Clock.schedule_once(_actualizar, 0)

    def _on_gps_status(self, stype, status):
        print(f"[GPS] {stype}: {status}")

    def _actualizar_countdown(self, dt):
        if self._proximo_anuncio:
            minutos = max(0, int((self._proximo_anuncio - time.time()) / 60))
            if self.root and self.root.current == 'activa':
                pa = self.root.get_screen('activa')
                pa.texto_proximo_anuncio = f"Proximo anuncio en: {minutos} min"

    # ── Anuncio WiFi UDP cada 1 hora ─────────────────────────────────────────
    def iniciar_anuncio_wifi(self, credencial, cuadrilla, nombre):
        if self._anuncio_activo:
            return
        self._anuncio_activo = True

        def _anunciar():
            while self._anuncio_activo:
                try:
                    nombre_limpio = str(nombre).replace(':', ' ').replace('\n', ' ')
                    lat = self._lat
                    lon = self._lon
                    # Formato: PRESENTE:<credencial>:<cuadrilla>:<nombre>:<lat>:<lon>
                    mensaje = f"PRESENTE:{credencial}:{cuadrilla}:{nombre_limpio}:{lat:.6f}:{lon:.6f}"
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                        sock.sendto(
                            mensaje.encode('utf-8'),
                            ('255.255.255.255', PUERTO_ANUNCIO)
                        )
                    print(f"[WIFI] Anuncio enviado: {mensaje}")
                    self._proximo_anuncio = time.time() + INTERVALO_ANUNCIO
                    Clock.schedule_once(lambda dt: self._actualizar_countdown(0), 0)
                except Exception as e:
                    print(f"[WIFI] Error anuncio: {e}")
                time.sleep(INTERVALO_ANUNCIO)

        threading.Thread(target=_anunciar, daemon=True).start()
        # Primer anuncio inmediato
        def _primer_anuncio():
            try:
                nombre_limpio = str(nombre).replace(':', ' ').replace('\n', ' ')
                mensaje = f"PRESENTE:{credencial}:{cuadrilla}:{nombre_limpio}:{self._lat:.6f}:{self._lon:.6f}"
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    sock.sendto(mensaje.encode('utf-8'), ('255.255.255.255', PUERTO_ANUNCIO))
                self._proximo_anuncio = time.time() + INTERVALO_ANUNCIO
            except Exception as e:
                print(f"[WIFI] Error primer anuncio: {e}")
        threading.Thread(target=_primer_anuncio, daemon=True).start()

    def detener_anuncio(self):
        self._anuncio_activo = False

    # ── Servidor validacion ───────────────────────────────────────────────────
    def iniciar_servidor_validacion(self, credencial, cuadrilla):
        if self._validacion_activa:
            return
        self._validacion_activa = True

        def _escuchar():
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.bind(('', PUERTO_VALIDACION))
                    sock.settimeout(2.0)
                    while self._validacion_activa:
                        try:
                            datos_raw, addr = sock.recvfrom(1024)
                            mensaje = datos_raw.decode('utf-8').strip()
                            partes  = mensaje.split(':')
                            if (len(partes) >= 3 and
                                    partes[0] == 'VALIDAR' and
                                    partes[1] == str(credencial)):
                                sock.sendto(f"OK:{credencial}".encode(), addr)
                                Clock.schedule_once(
                                    lambda dt: self._registrar_asistencia(), 0
                                )
                        except socket.timeout:
                            continue
                        except Exception as e:
                            print(f"[WIFI] Error validacion: {e}")
            except Exception as e:
                print(f"[WIFI] Error servidor: {e}")
            finally:
                self._validacion_activa = False

        threading.Thread(target=_escuchar, daemon=True).start()

    def _registrar_asistencia(self):
        ahora     = datetime.datetime.now()
        datos     = cargar_datos()
        historial = datos.get("historial", [])
        historial = agregar_dia_historial(historial, estatus="presente")
        faltas    = calcular_faltas_consecutivas(historial)
        datos["historial"]           = historial
        datos["faltas_consecutivas"] = faltas
        datos["ultima_asistencia"]   = ahora.isoformat()
        guardar_datos(datos)
        pa = self.root.get_screen('activa')
        pa.texto_estado_conexion = f"Asistencia validada: {ahora.strftime('%H:%M')}"
        pa.color_estado          = [0.18, 0.29, 0.12, 1]
        pa.texto_vigencia        = self._texto_vigencia(faltas)
        if self.root.current == 'inactiva' and faltas < MAX_FALTAS:
            self.root.current = 'activa'
        Snackbar(text="Asistencia registrada correctamente").open()

    def _texto_vigencia(self, faltas: int) -> str:
        if faltas == 0:
            return "Sin faltas consecutivas"
        restantes = MAX_FALTAS - faltas
        if restantes == 1:
            return "Atencion: 1 falta mas = bloqueo"
        return f"Faltas consecutivas: {faltas}/{MAX_FALTAS}"

    def parpadear_wifi(self, dt):
        if self.root and self.root.current == 'activa':
            pa = self.root.get_screen('activa')
            self.estado_parpadeo = not self.estado_parpadeo
            pa.color_icono_wifi = (
                [0.18, 0.29, 0.12, 1] if self.estado_parpadeo
                else [0.96, 0.65, 0.14, 0.4]
            )

    def verificar_vigencia(self, dt):
        datos     = cargar_datos()
        historial = datos.get("historial", [])
        hoy       = datetime.date.today()
        ahora     = datetime.datetime.now()
        gracia    = en_periodo_gracia(datos)
        if not gracia:
            hora_entrada = datos.get("hora_entrada", 7)
            hora_limite  = hora_entrada + TOLERANCIA_HORAS
            dias_ok      = {e.get("fecha") for e in historial}
            if es_dia_laboral(hoy) and hoy.isoformat() not in dias_ok:
                if ahora.hour >= hora_limite:
                    historial = agregar_dia_historial(historial, estatus="falta")
                    datos["historial"] = historial
                    guardar_datos(datos)
        faltas = 0 if gracia else calcular_faltas_consecutivas(historial)
        pa     = self.root.get_screen('activa')
        if faltas >= MAX_FALTAS:
            self.detener_anuncio()
            if self.root.current != 'inactiva':
                pi = self.root.get_screen('inactiva')
                pi.motivo_bloqueo = (
                    f"{faltas} faltas consecutivas registradas.\n"
                    "Presentate a Recursos Humanos para regularizar."
                )
                pi.texto_faltas = f"Faltas del mes: {contar_faltas_mes(historial)}"
                self.root.current = 'inactiva'
        else:
            if self.root.current == 'activa':
                pa.texto_vigencia = self._texto_vigencia(faltas)

    def on_stop(self):
        self.detener_anuncio()
        self._validacion_activa = False


if __name__ == '__main__':
    CredencialAgriCactusApp().run()
