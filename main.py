# =============================================================================
#  AgriCactus - App del TRABAJADOR  (main.py)
#  v3.4 - Puesto fijo con PIN RH + auto-validacion
# =============================================================================

import datetime
import hashlib
import hmac
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
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.textfield import MDTextField

try:
    from plyer import gps
    GPS_DISPONIBLE = True
except Exception:
    GPS_DISPONIBLE = False

try:
    from plyer import filechooser
    FILECHOOSER_DISPONIBLE = True
except Exception:
    FILECHOOSER_DISPONIBLE = False

try:
    import qrcode
    from kivy.core.image import Image as CoreImage
    from io import BytesIO
    QR_DISPONIBLE = True
except Exception:
    QR_DISPONIBLE = False

# =============================================================================
#  CATALOGO DE ACTIVIDADES (resumido para puesto fijo)
# =============================================================================
ACTIVIDADES_FIJAS = [
    ("1033","AUXILIAR DE RIEGO"),("1034","REGADOR"),
    ("1035","SUPERVISOR DE RIEGO"),("1038","CUADRILLERO"),
    ("1039","SUPERVISOR"),("1040","SUPERVISOR GENERAL"),
    ("1041","SUPERVISOR GENERAL 1"),("1057","AUXILIAR OPERADOR"),
    ("1058","OPERADOR"),("1068","VELADOR POZO"),
    ("1069","VELADOR EMPAQUE"),("1070","VELADOR TALLER"),
    ("1071","VELADOR PORTERO"),("1086","MONTACARGUISTA"),
    ("1099","MONTACARGUISTA SANDIA"),("1121","SUPERVISOR UVA CAMPO"),
    ("1131","OPERADOR DUMPER"),("1137","AUXILIAR MECANICO"),
    ("1138","AUXILIAR TALLER"),("1142","REGADOR SP"),
    ("1143","OPERADOR SP"),("1144","VELADOR SP"),
    ("1145","CUADRILLERO SP"),("1148","PORTERO SP"),
    ("1152","AUXILIAR ALMACEN"),("1153","VIGILANTE SP"),
    ("1176","RIEGO RODADO"),("1209","SUPERVISOR PODA UVA"),
    ("1221","SUPERVISOR DE RIEGO PLANTA"),("1231","SUPERVISOR COSECHA UVA"),
    ("1234","SUPERVISOR EMPAQUE"),("1241","ENCARGADO DE COMPRAS"),
    ("1251","CAPTURISTA"),("1260","MECANICO DIESEL"),
    ("1281","CHOFER CAMPO"),("1293","ENCARGADO EN INFORMATICA"),
    ("1296","AUXILIAR SOLDADOR"),("1311","SUPERVISOR ADMINISTRATIVO PLANTA"),
    ("1320","LIDER DE CONSTRUCCION"),("1321","OFICIAL DE CONSTRUCCION"),
    ("1325","MECANICO DIESEL PLANTA"),("1333","SUPERVISOR 1"),
    ("1352","GUARDIA PORTERO"),("1360","SEGURIDAD MONITORES"),
    ("1363","AUXILIAR DE MANTENIMIENTO"),("1380","GUARDIA TIENDA"),
    ("1388","GUARDIA PORTERO 2"),("1422","RECLUTADOR"),
]

# =============================================================================
#  CONSTANTES
# =============================================================================
ARCHIVO_DATOS      = "empleado_data.json"
PUERTO_ANUNCIO     = 45678
PUERTO_VALIDACION  = 45679
PUERTO_APUNTADOR   = 45683   # Puerto especial para auto-validacion con apuntador
INTERVALO_SIN_CONF = 3       # Cambio 3: reducido de 10s a 3s hasta primera confirmacion
INTERVALO_CON_CONF = 1800
RAFAGA_ANUNCIO     = 3       # Cambio 3: paquetes por ciclo (ráfaga anti-pérdida UDP)
PAUSA_RAFAGA       = 0.15    # Cambio 3: segundos entre paquetes de la ráfaga
MAX_FALTAS         = 3
DIAS_LABORALES     = {0, 1, 2, 3, 4}
TOLERANCIA_HORAS   = 2
DIAS_GRACIA        = 3
MAX_CONFIRMACIONES = 2
PIN_RH             = "RH2024"

# ── Ruta de respaldo persistente (sobrevive desinstalacion) ───────────────────
# En Android usamos el almacenamiento externo compartido (no se borra con uninstall).
# En escritorio/pruebas se usa el home del usuario.
def _ruta_backup() -> str:
    if platform == 'android':
        try:
            from jnius import autoclass
            Environment = autoclass('android.os.Environment')
            ruta_ext    = Environment.getExternalStorageDirectory().getAbsolutePath()
            carpeta     = os.path.join(ruta_ext, "AgriCactus")
            os.makedirs(carpeta, exist_ok=True)
            return os.path.join(carpeta, "credencial_backup.dat")
        except Exception:
            pass
    # Fallback para desarrollo en PC
    carpeta = os.path.join(os.path.expanduser("~"), ".agricactus")
    os.makedirs(carpeta, exist_ok=True)
    return os.path.join(carpeta, "credencial_backup.dat")

ARCHIVO_BACKUP = _ruta_backup()

def guardar_backup(datos: dict):
    """Guarda una copia de la credencial en almacenamiento externo persistente."""
    try:
        contenido = json.dumps(datos, ensure_ascii=False, indent=2).encode('utf-8')
        if STORAGE_CIFRADO:
            contenido = _fernet.encrypt(contenido)
        with open(ARCHIVO_BACKUP, 'wb') as f:
            f.write(contenido)
    except Exception as e:
        print(f"[BACKUP] Error al guardar backup: {e}")

def cargar_backup() -> dict:
    """Intenta recuperar la credencial desde el backup externo."""
    if not os.path.exists(ARCHIVO_BACKUP):
        return {}
    try:
        with open(ARCHIVO_BACKUP, 'rb') as f:
            contenido = f.read()
        if STORAGE_CIFRADO:
            try:
                contenido = _fernet.decrypt(contenido)
            except Exception:
                pass
        return json.loads(contenido.decode('utf-8'))
    except Exception as e:
        print(f"[BACKUP] Error al leer backup: {e}")
        return {}

# ── Autenticación de mensajes UDP (punto 2) ───────────────────────────────────
# Clave compartida con las demás apps del ecosistema AgriCactus.
# Cambiar por una clave más robusta en producción.
UDP_SECRET = b"AgriCactus2024SecretKey"

def _firmar_mensaje(mensaje: str) -> str:
    """Agrega un token HMAC-SHA256 al mensaje: '<mensaje>|<token_hex>'."""
    token = hmac.new(UDP_SECRET, mensaje.encode('utf-8'), hashlib.sha256).hexdigest()[:16]
    return f"{mensaje}|{token}"

def _verificar_mensaje(datos_raw: bytes) -> str | None:
    """Valida el token HMAC. Devuelve el mensaje sin token, o None si es inválido."""
    try:
        texto  = datos_raw.decode('utf-8').strip()
        partes = texto.rsplit('|', 1)
        if len(partes) != 2:
            return None
        mensaje, token_recibido = partes
        token_esperado = hmac.new(UDP_SECRET, mensaje.encode('utf-8'), hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(token_recibido, token_esperado):
            return None
        return mensaje
    except Exception:
        return None




# ── Cifrado del almacenamiento local (punto 3) ────────────────────────────────
try:
    from cryptography.fernet import Fernet
    import base64
    _FERNET_SEED = b"AgriCactusStorageKey2024!!"
    _FERNET_KEY  = base64.urlsafe_b64encode(
        hashlib.sha256(_FERNET_SEED).digest()
    )
    _fernet = Fernet(_FERNET_KEY)
    STORAGE_CIFRADO = True
except Exception:
    _fernet = None
    STORAGE_CIFRADO = False

def guardar_datos(datos: dict):
    try:
        contenido = json.dumps(datos, ensure_ascii=False, indent=2).encode('utf-8')
        if STORAGE_CIFRADO:
            contenido = _fernet.encrypt(contenido)
            with open(ARCHIVO_DATOS, 'wb') as f:
                f.write(contenido)
        else:
            with open(ARCHIVO_DATOS, 'w', encoding='utf-8') as f:
                f.write(contenido.decode('utf-8'))
        # Cambio 2: mantener backup externo sincronizado
        guardar_backup(datos)
    except Exception as e:
        print(f"[STORAGE] Error: {e}")

def cargar_datos() -> dict:
    if os.path.exists(ARCHIVO_DATOS):
        try:
            with open(ARCHIVO_DATOS, 'rb') as f:
                contenido = f.read()
            if STORAGE_CIFRADO:
                try:
                    contenido = _fernet.decrypt(contenido)
                except Exception:
                    # Fallback: el archivo puede ser JSON plano de una versión anterior
                    pass
            return json.loads(contenido.decode('utf-8'))
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
    # Punto 6: el conteo nunca cruza hacia el mes anterior
    hoy             = datetime.date.today()
    primer_dia_mes  = hoy.replace(day=1)
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
    fecha  = hoy - datetime.timedelta(days=1)
    for _ in range(60):
        if fecha < primer_dia_mes:
            break
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

def agregar_dia_historial(historial: list, estatus: str = "presente",
                           turno: str = "matutino") -> list:
    hoy  = datetime.date.today().isoformat()
    mes  = mes_actual_str()
    hora = datetime.datetime.now().strftime("%H:%M")
    for i, e in enumerate(historial):
        if e.get("fecha") == hoy and e.get("turno") == turno:
            historial[i]["estatus"] = estatus
            historial[i]["hora"]    = hora
            return historial
    historial.append({
        "fecha": hoy, "mes": mes,
        "turno": turno, "estatus": estatus, "hora": hora
    })
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
        return (datetime.date.today() - fecha_ingreso).days < DIAS_GRACIA
    except Exception:
        return False

def generar_qr_texture(texto: str):
    if not QR_DISPONIBLE:
        return None
    try:
        qr = qrcode.QRCode(version=1,
                           error_correction=qrcode.constants.ERROR_CORRECT_M,
                           box_size=6, border=2)
        qr.add_data(texto)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return CoreImage(buf, ext='png').texture
    except Exception as e:
        print(f"[QR] Error: {e}")
        return None

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
    PantallaPuestoFijo:


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
        md_bg_color: 0.94, 0.96, 0.94, 1

        MDFloatLayout:
            size_hint_x: 0.06
            pos_hint: {'x': 0, 'y': 0}
            md_bg_color: 0.18, 0.29, 0.12, 1

        MDCard:
            size_hint: (0.92, 0.97)
            pos_hint: {'right': 0.99, 'center_y': 0.50}
            elevation: 4
            radius: [16, 16, 16, 16]
            md_bg_color: 1, 1, 1, 1

            MDFloatLayout:

                # Encabezado
                MDFloatLayout:
                    size_hint_y: 0.13
                    pos_hint: {'x': 0, 'top': 1}
                    md_bg_color: 0.18, 0.29, 0.12, 1

                    Image:
                        source: "logo_agricactus.png"
                        size_hint: (0.40, 0.80)
                        allow_stretch: True
                        keep_ratio: True
                        pos_hint: {'center_x': 0.24, 'center_y': 0.5}

                    MDLabel:
                        text: "CREDENCIAL DIGITAL"
                        font_style: "Caption"
                        bold: True
                        halign: "center"
                        theme_text_color: "Custom"
                        text_color: 0.96, 0.65, 0.14, 1
                        pos_hint: {'center_x': 0.72, 'center_y': 0.62}
                        size_hint: (0.52, 0.22)

                    MDLabel:
                        text: root.texto_vigencia
                        font_style: "Caption"
                        halign: "center"
                        theme_text_color: "Custom"
                        text_color: 0.78, 0.92, 0.78, 1
                        pos_hint: {'center_x': 0.72, 'center_y': 0.30}
                        size_hint: (0.52, 0.22)

                MDBoxLayout:
                    size_hint: (1, 0.004)
                    pos_hint: {'x': 0, 'top': 0.87}
                    md_bg_color: 0.96, 0.65, 0.14, 1

                # Foto
                FitImage:
                    source: root.ruta_foto
                    size_hint: (0.28, 0.23)
                    pos_hint: {'x': 0.04, 'top': 0.85}
                    radius: [10, 10, 10, 10]

                # Datos
                MDLabel:
                    text: root.nombre_empleado
                    markup: True
                    font_style: "H6"
                    bold: True
                    halign: "left"
                    valign: "center"
                    theme_text_color: "Custom"
                    text_color: 0.12, 0.22, 0.08, 1
                    text_size: self.size
                    pos_hint: {'x': 0.36, 'top': 0.85}
                    size_hint: (0.60, 0.12)

                MDLabel:
                    text: "Ingreso: " + root.fecha_ingreso
                    font_style: "Caption"
                    halign: "left"
                    theme_text_color: "Secondary"
                    pos_hint: {'x': 0.36, 'top': 0.73}
                    size_hint: (0.60, 0.04)

                MDLabel:
                    text: "Cuadrilla: " + root.num_cuadrilla
                    font_style: "Body2"
                    bold: True
                    halign: "left"
                    theme_text_color: "Custom"
                    text_color: 0.18, 0.42, 0.18, 1
                    pos_hint: {'x': 0.36, 'top': 0.69}
                    size_hint: (0.60, 0.04)

                MDLabel:
                    text: "NSS: " + root.nss
                    font_style: "Caption"
                    halign: "left"
                    theme_text_color: "Custom"
                    text_color: 0.4, 0.4, 0.4, 1
                    pos_hint: {'x': 0.36, 'top': 0.65}
                    size_hint: (0.60, 0.04)

                # Badge puesto fijo
                MDCard:
                    size_hint: (0.88, 0.05)
                    pos_hint: {'center_x': 0.5, 'top': 0.61}
                    elevation: 1
                    radius: [6, 6, 6, 6]
                    md_bg_color: root.color_badge_puesto

                    MDLabel:
                        text: root.texto_puesto_fijo
                        font_style: "Caption"
                        bold: True
                        halign: "center"
                        theme_text_color: "Custom"
                        text_color: 1, 1, 1, 1

                MDBoxLayout:
                    size_hint: (0.90, 0.004)
                    pos_hint: {'center_x': 0.5, 'top': 0.56}
                    md_bg_color: 0.96, 0.65, 0.14, 1

                # Numero credencial
                MDLabel:
                    text: "No. " + root.num_credencial
                    font_style: "H4"
                    bold: True
                    halign: "center"
                    theme_text_color: "Custom"
                    text_color: 0.12, 0.22, 0.08, 1
                    pos_hint: {'center_x': 0.5, 'top': 0.55}
                    size_hint: (0.90, 0.09)

                # QR
                Image:
                    id: img_qr
                    size_hint: (0.30, 0.16)
                    pos_hint: {'center_x': 0.5, 'top': 0.46}
                    allow_stretch: True
                    keep_ratio: True

                MDLabel:
                    text: "Acceso comedor"
                    font_style: "Caption"
                    halign: "center"
                    theme_text_color: "Custom"
                    text_color: 0.5, 0.5, 0.5, 1
                    pos_hint: {'center_x': 0.5, 'top': 0.30}
                    size_hint: (0.90, 0.04)

                MDBoxLayout:
                    size_hint: (0.90, 0.004)
                    pos_hint: {'center_x': 0.5, 'top': 0.26}
                    md_bg_color: 0.90, 0.90, 0.90, 1

                # Estado turno
                MDCard:
                    size_hint: (0.90, 0.06)
                    pos_hint: {'center_x': 0.5, 'top': 0.255}
                    elevation: 1
                    radius: [8, 8, 8, 8]
                    md_bg_color: root.color_turno

                    MDLabel:
                        text: root.texto_turno
                        font_style: "Caption"
                        bold: True
                        halign: "center"
                        theme_text_color: "Custom"
                        text_color: 1, 1, 1, 1

                # Estado wifi
                MDBoxLayout:
                    orientation: 'horizontal'
                    size_hint: (0.90, 0.05)
                    pos_hint: {'center_x': 0.5, 'top': 0.195}
                    spacing: '6dp'
                    padding: ['8dp', 0, 0, 0]

                    MDIcon:
                        icon: "wifi"
                        theme_text_color: "Custom"
                        text_color: root.color_icono_wifi
                        font_size: "18sp"
                        size_hint_x: None
                        width: '22dp'

                    # Indicador rojo/verde de validacion
                    MDIcon:
                        icon: "circle"
                        theme_text_color: "Custom"
                        text_color: root.color_indicador_validacion
                        font_size: "14sp"
                        size_hint_x: None
                        width: '18dp'

                    MDLabel:
                        text: root.texto_estado_conexion
                        font_style: "Caption"
                        halign: "left"
                        theme_text_color: "Custom"
                        text_color: root.color_estado

                MDLabel:
                    text: root.texto_gps
                    font_style: "Caption"
                    halign: "center"
                    theme_text_color: "Secondary"
                    pos_hint: {'center_x': 0.5, 'top': 0.145}
                    size_hint: (0.90, 0.04)

                MDLabel:
                    text: root.texto_proximo_anuncio
                    font_style: "Caption"
                    halign: "center"
                    theme_text_color: "Custom"
                    text_color: 0.29, 0.50, 0.29, 1
                    pos_hint: {'center_x': 0.5, 'top': 0.105}
                    size_hint: (0.90, 0.04)

                # Boton puesto fijo
                MDRectangleFlatIconButton:
                    icon: "briefcase-edit"
                    text: "CONFIGURAR PUESTO"
                    theme_text_color: "Custom"
                    text_color: 0.18, 0.29, 0.12, 1
                    line_color: 0.18, 0.29, 0.12, 1
                    pos_hint: {'center_x': 0.5, 'top': 0.065}
                    size_hint: (0.88, 0.05)
                    on_release: app.root.current = 'puesto_fijo'

                # Pie
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


<PantallaPuestoFijo>:
    name: 'puesto_fijo'

    MDFloatLayout:
        md_bg_color: 0.94, 0.96, 0.94, 1

        MDFloatLayout:
            size_hint_y: 0.13
            pos_hint: {'x': 0, 'top': 1}
            md_bg_color: 0.18, 0.29, 0.12, 1

            MDLabel:
                text: "CONFIGURAR PUESTO FIJO"
                font_style: "H6"
                bold: True
                halign: "center"
                theme_text_color: "Custom"
                text_color: 0.96, 0.65, 0.14, 1
                pos_hint: {'center_x': 0.5, 'center_y': 0.5}
                size_hint: (1, 1)

        MDBoxLayout:
            size_hint_y: 0.004
            pos_hint: {'x': 0, 'top': 0.87}
            md_bg_color: 0.96, 0.65, 0.14, 1

        MDCard:
            size_hint: (0.92, 0.20)
            pos_hint: {'center_x': 0.5, 'top': 0.85}
            elevation: 2
            radius: [10, 10, 10, 10]
            md_bg_color: 1, 1, 1, 1

            MDBoxLayout:
                orientation: 'vertical'
                padding: '12dp'
                spacing: '8dp'

                MDLabel:
                    text: "Puesto fijo actual:"
                    font_style: "Caption"
                    halign: "center"
                    theme_text_color: "Secondary"

                MDLabel:
                    id: label_puesto_actual
                    text: root.puesto_actual
                    font_style: "Body1"
                    bold: True
                    halign: "center"
                    theme_text_color: "Custom"
                    text_color: 0.18, 0.42, 0.18, 1

        MDCard:
            size_hint: (0.92, 0.14)
            pos_hint: {'center_x': 0.5, 'top': 0.63}
            elevation: 2
            radius: [10, 10, 10, 10]
            md_bg_color: 1, 1, 1, 1

            MDBoxLayout:
                orientation: 'horizontal'
                padding: '10dp'
                spacing: '8dp'

                MDTextField:
                    id: input_pin_puesto
                    hint_text: "PIN de RH para configurar"
                    password: True
                    line_color_focus: 0.18, 0.29, 0.12, 1
                    size_hint_x: 0.6

                MDRaisedButton:
                    text: "VERIFICAR"
                    md_bg_color: 0.18, 0.29, 0.12, 1
                    size_hint_x: 0.4
                    on_release: root.verificar_pin()

        MDTextField:
            id: input_buscar_puesto
            hint_text: "Buscar puesto por nombre o clave..."
            line_color_focus: 0.18, 0.29, 0.12, 1
            pos_hint: {'center_x': 0.5, 'top': 0.47}
            size_hint: (0.92, None)
            height: '48dp'
            disabled: True
            on_text: root.filtrar_puestos(self.text)

        ScrollView:
            size_hint: (0.92, 0.32)
            pos_hint: {'center_x': 0.5, 'top': 0.38}
            id: scroll_puestos

            MDList:
                id: lista_puestos

        MDBoxLayout:
            orientation: 'horizontal'
            size_hint: (0.92, 0.08)
            pos_hint: {'center_x': 0.5, 'y': 0.02}
            spacing: '8dp'

            MDRaisedButton:
                text: "QUITAR PUESTO FIJO"
                md_bg_color: 0.65, 0.08, 0.08, 1
                size_hint_x: 0.5
                on_release: root.quitar_puesto()

            MDRectangleFlatButton:
                text: "CANCELAR"
                theme_text_color: "Custom"
                text_color: 0.18, 0.29, 0.12, 1
                line_color: 0.18, 0.29, 0.12, 1
                size_hint_x: 0.5
                on_release: app.root.current = 'activa'


<PantallaInactiva>:
    name: 'inactiva'

    MDFloatLayout:
        md_bg_color: 0.10, 0.06, 0.06, 1

        MDFloatLayout:
            size_hint_y: 0.18
            pos_hint: {'x': 0, 'top': 1}
            md_bg_color: 0.65, 0.08, 0.08, 1

            Image:
                source: "logo_agricactus.png"
                size_hint: (0.28, 0.65)
                allow_stretch: True
                keep_ratio: True
                pos_hint: {'center_x': 0.5, 'center_y': 0.5}
                opacity: 0.35

        MDIcon:
            icon: "lock-alert"
            theme_text_color: "Custom"
            text_color: 0.80, 0.12, 0.12, 1
            font_size: "60sp"
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
            size_hint: (0.82, 0.003)
            pos_hint: {'center_x': 0.5, 'center_y': 0.43}
            md_bg_color: 0.35, 0.20, 0.20, 1

        MDCard:
            size_hint: (0.88, 0.15)
            pos_hint: {'center_x': 0.5, 'center_y': 0.34}
            elevation: 2
            radius: [10, 10, 10, 10]
            md_bg_color: 0.18, 0.12, 0.12, 1

            MDBoxLayout:
                orientation: 'vertical'
                padding: '10dp'
                spacing: '4dp'

                MDIcon:
                    icon: "office-building"
                    theme_text_color: "Custom"
                    text_color: 0.96, 0.65, 0.14, 1
                    font_size: "22sp"
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
                    text_color: 0.72, 0.55, 0.55, 1

        MDBoxLayout:
            size_hint: (0.82, 0.003)
            pos_hint: {'center_x': 0.5, 'center_y': 0.23}
            md_bg_color: 0.35, 0.20, 0.20, 1

        MDLabel:
            text: "Desbloqueo autorizado por RH:"
            font_style: "Caption"
            halign: "center"
            theme_text_color: "Custom"
            text_color: 0.60, 0.60, 0.60, 1
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
                md_bg_color: 0.18, 0.38, 0.18, 1
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
                text_color: 0.12, 0.22, 0.08, 1
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
                self.ids.label_foto.text = f"Error: {e}"
        else:
            self.ids.label_foto.text = "Camara solo en Android"

    def _resultado_camara(self, requestCode, resultCode, intent):
        RESULT_OK = -1
        if requestCode != 1001 or resultCode != RESULT_OK:
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
            self.ids.label_foto.text    = "Foto tomada"
        except Exception as e:
            self.ids.label_foto.text = f"Error: {e}"

    def abrir_galeria(self):
        if FILECHOOSER_DISPONIBLE:
            try:
                from plyer import filechooser as fc
                fc.open_file(
                    title="Foto de perfil",
                    filters=[("Imagenes", "*.jpg", "*.jpeg", "*.png")],
                    on_selection=self.al_seleccionar_foto
                )
            except Exception as e:
                self.ids.label_foto.text = f"Error: {e}"

    def al_seleccionar_foto(self, seleccion):
        if seleccion:
            self.ruta_foto_seleccionada = seleccion[0]
            self.ids.label_foto.text    = f"OK: {os.path.basename(seleccion[0])}"

    def guardar_registro(self):
        # Cambio 2: bloquear si ya existe una credencial registrada
        datos_existentes = cargar_datos()
        if not datos_existentes:
            datos_existentes = cargar_backup()
        if datos_existentes.get("credencial"):
            Snackbar(text="Ya existe una credencial registrada en este dispositivo.").open()
            return

        nombre       = self.ids.input_nombre.text.strip().upper()
        nss          = self.ids.input_nss.text.strip()
        credencial   = self.ids.input_credencial.text.strip()
        cuadrilla    = self.ids.input_cuadrilla.text.strip()
        hora_entrada = self.ids.input_hora_entrada.text.strip()

        errores = []
        if not nombre:     errores.append("nombre")
        if len(nss) < 10:  errores.append("NSS")
        if not credencial: errores.append("credencial")
        if not cuadrilla:  errores.append("cuadrilla")
        if not self.ruta_foto_seleccionada: errores.append("foto")

        hora_int = 7
        if hora_entrada:
            try:
                hora_int = int(hora_entrada.split(":")[0])
            except Exception:
                errores.append("hora HH:MM")

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

        datos = cargar_datos()
        datos.update({
            "nombre":              nombre_fmt,
            "nss":                 nss,
            "credencial":          credencial,
            "cuadrilla":           cuadrilla,
            "foto":                self.ruta_foto_seleccionada,
            "fecha_ingreso":       pa.fecha_ingreso,
            "hora_entrada":        hora_int,
            "fecha_inicio_conteo": datetime.date.today().isoformat(),
            "ultima_asistencia":   datetime.datetime.now().isoformat(),
            "confirmaciones_hoy":  0,
        })
        guardar_datos(datos)

        app._confirmaciones_hoy = 0
        app.iniciar_anuncio_wifi(credencial, cuadrilla, nombre_fmt)
        app.iniciar_servidor_validacion(credencial, cuadrilla)
        app.iniciar_gps()
        Clock.schedule_once(lambda dt: app.cargar_qr(credencial), 0.5)
        Clock.schedule_once(lambda dt: app.actualizar_badge_puesto(), 0.3)
        app.root.current = 'activa'
        Snackbar(text="Credencial generada").open()


class PantallaActiva(Screen):
    nombre_empleado           = StringProperty("")
    fecha_ingreso             = StringProperty("")
    nss                       = StringProperty("")
    num_credencial            = StringProperty("")
    num_cuadrilla             = StringProperty("")
    texto_vigencia            = StringProperty("Sin faltas consecutivas")
    ruta_foto                 = StringProperty("")
    color_icono_wifi          = ListProperty([0.96, 0.65, 0.14, 1])
    texto_gps                 = StringProperty("GPS: sin senal")
    texto_estado_conexion     = StringProperty("Buscando cuadrillero...")
    color_estado              = ListProperty([0.6, 0.6, 0.6, 1])
    texto_proximo_anuncio     = StringProperty("Emitiendo cada 3s...")
    texto_turno               = StringProperty("Sin confirmar — emitiendo cada 3s")
    color_turno               = ListProperty([0.96, 0.65, 0.14, 1])
    texto_puesto_fijo         = StringProperty("Sin puesto fijo configurado")
    color_badge_puesto        = ListProperty([0.7, 0.7, 0.7, 1])
    # Indicador de validación: rojo = sin validar, verde = validado hoy
    color_indicador_validacion = ListProperty([0.80, 0.10, 0.10, 1])


class PantallaPuestoFijo(Screen):
    puesto_actual   = StringProperty("Sin configurar")
    _pin_verificado = False

    def on_enter(self):
        self._pin_verificado = False
        self.ids.input_pin_puesto.text = ""
        self.ids.input_buscar_puesto.disabled = True
        self.ids.lista_puestos.clear_widgets()

        datos = cargar_datos()
        puesto = datos.get("puesto_fijo_desc", "Sin configurar")
        self.puesto_actual = puesto

    def verificar_pin(self):
        pin = self.ids.input_pin_puesto.text.strip()
        self.ids.input_pin_puesto.text = ""
        if pin != PIN_RH:
            Snackbar(text="PIN incorrecto").open()
            return
        self._pin_verificado = True
        self.ids.input_buscar_puesto.disabled = False
        self.filtrar_puestos("")
        Snackbar(text="PIN correcto — selecciona el puesto").open()

    def filtrar_puestos(self, texto):
        if not self._pin_verificado:
            return
        self.ids.lista_puestos.clear_widgets()
        txt = texto.strip().upper()
        resultados = [
            (c, d) for c, d in ACTIVIDADES_FIJAS
            if txt in d.upper() or txt in c
        ] if txt else ACTIVIDADES_FIJAS

        from kivymd.uix.list import OneLineListItem
        for clave, desc in resultados:
            item = OneLineListItem(
                text=f"{clave} - {desc}",
                on_release=lambda x, c=clave, d=desc: self._seleccionar_puesto(c, d)
            )
            self.ids.lista_puestos.add_widget(item)

    def _seleccionar_puesto(self, clave, desc):
        if not self._pin_verificado:
            return
        datos = cargar_datos()
        datos["puesto_fijo_clave"] = clave
        datos["puesto_fijo_desc"]  = f"{clave} - {desc}"
        datos["es_puesto_fijo"]    = True
        guardar_datos(datos)

        self.puesto_actual = f"{clave} - {desc}"
        app = MDApp.get_running_app()
        app.actualizar_badge_puesto()

        Snackbar(text=f"Puesto configurado: {desc}").open()
        Clock.schedule_once(lambda dt: setattr(
            app.root, 'current', 'activa'
        ), 1.0)

    def quitar_puesto(self):
        if not self._pin_verificado:
            Snackbar(text="Verifica el PIN primero").open()
            return
        datos = cargar_datos()
        datos["puesto_fijo_clave"] = ""
        datos["puesto_fijo_desc"]  = ""
        datos["es_puesto_fijo"]    = False
        guardar_datos(datos)
        self.puesto_actual = "Sin configurar"
        app = MDApp.get_running_app()
        app.actualizar_badge_puesto()
        Snackbar(text="Puesto fijo eliminado").open()
        app.root.current = 'activa'


class PantallaInactiva(Screen):
    PIN_RH             = "RH2024"
    motivo_bloqueo     = StringProperty("3 faltas consecutivas registradas.")
    texto_faltas       = StringProperty("Presentate a Recursos Humanos")
    _tipo_seleccionado = "falta"

    def seleccionar_tipo(self, tipo: str):
        self._tipo_seleccionado = tipo
        colores = {
            "falta":       [0.50, 0.15, 0.15, 1],
            "incapacidad": [0.18, 0.38, 0.18, 1],
            "vacaciones":  [0.18, 0.29, 0.45, 1],
        }
        apagado = [0.22, 0.22, 0.22, 1]
        self.ids.btn_tipo_falta.md_bg_color       = apagado
        self.ids.btn_tipo_incapacidad.md_bg_color = apagado
        self.ids.btn_tipo_vacaciones.md_bg_color  = apagado
        self.ids[{
            "falta": "btn_tipo_falta",
            "incapacidad": "btn_tipo_incapacidad",
            "vacaciones": "btn_tipo_vacaciones"
        }[tipo]].md_bg_color = colores[tipo]
        Snackbar(text=f"Tipo: {tipo.upper()}").open()

    def intentar_reactivacion(self):
        pin = self.ids.pin_input.text.strip()
        self.ids.pin_input.text = ""
        if pin != self.PIN_RH:
            Snackbar(text="PIN incorrecto.").open()
            return
        tipo  = self._tipo_seleccionado
        app   = MDApp.get_running_app()
        datos = cargar_datos()
        historial = datos.get("historial", [])
        mes_hoy = mes_actual_str()
        for i, e in enumerate(historial):
            if e.get("mes") == mes_hoy and e.get("estatus") == "falta":
                historial[i]["estatus"]       = tipo
                historial[i]["autorizado_rh"] = True
        historial = agregar_dia_historial(historial, estatus="presente", turno="matutino")
        datos["historial"]           = historial
        datos["fecha_inicio_conteo"] = datetime.date.today().isoformat()
        datos["faltas_consecutivas"] = 0
        datos["confirmaciones_hoy"]  = 0
        guardar_datos(datos)
        faltas = calcular_faltas_consecutivas(historial)
        pa = app.root.get_screen('activa')
        pa.texto_vigencia = app._texto_vigencia(faltas)
        app._confirmaciones_hoy = 0
        app._anuncio_activo = False
        app.iniciar_anuncio_wifi(pa.num_credencial, pa.num_cuadrilla, pa.nombre_empleado)
        app.iniciar_servidor_validacion(pa.num_credencial, pa.num_cuadrilla)
        Clock.schedule_once(lambda dt: app.cargar_qr(pa.num_credencial), 0.3)
        app.root.current = 'activa'
        Snackbar(text="Credencial desbloqueada.").open()


# =============================================================================
#  APLICACION PRINCIPAL
# =============================================================================
class CredencialAgriCactusApp(MDApp):
    estado_parpadeo     = BooleanProperty(False)
    _anuncio_activo     = False
    _validacion_activa  = False
    _autovalidacion_activa = False
    _lat                = 0.0
    _lon                = 0.0
    _proximo_anuncio    = None
    _confirmaciones_hoy = 0

    def build(self):
        self.theme_cls.theme_style     = "Light"
        self.theme_cls.primary_palette = "Green"
        controlador = Builder.load_string(KV)
        Clock.schedule_interval(self.verificar_vigencia, 30)
        Clock.schedule_interval(self.parpadear_wifi, 1)
        Clock.schedule_interval(self._actualizar_ui_anuncio, 15)
        Clock.schedule_once(self._restaurar_sesion, 0.5)
        return controlador

    def _restaurar_sesion(self, dt):
        datos = cargar_datos()

        # Cambio 2: si no hay datos locales (reinstalacion), intentar recuperar backup
        if not datos:
            datos = cargar_backup()
            if datos:
                # Reconstruir datos locales desde el backup
                guardar_datos(datos)
                Snackbar(text="Credencial restaurada desde respaldo.").open()

        if not datos:
            return
        pa = self.root.get_screen('activa')
        pa.nombre_empleado = datos.get("nombre", "")
        pa.nss             = datos.get("nss", "")
        pa.num_credencial  = datos.get("credencial", "")
        pa.num_cuadrilla   = datos.get("cuadrilla", "")
        pa.ruta_foto       = datos.get("foto", "")
        pa.fecha_ingreso   = datos.get("fecha_ingreso", "")

        conf_guardadas = datos.get("confirmaciones_hoy", 0)
        ultima = datos.get("ultima_asistencia", "")
        if ultima:
            try:
                fecha_ultima = datetime.datetime.fromisoformat(ultima).date()
                self._confirmaciones_hoy = (
                    conf_guardadas if fecha_ultima == datetime.date.today() else 0
                )
            except Exception:
                self._confirmaciones_hoy = 0

        historial = datos.get("historial", [])
        gracia    = en_periodo_gracia(datos)
        faltas    = 0 if gracia else calcular_faltas_consecutivas(historial)
        pa.texto_vigencia = self._texto_vigencia(faltas)
        self._actualizar_texto_turno(pa)
        self.actualizar_badge_puesto()

        # Restaurar indicador rojo/verde según si ya fue validado hoy
        if self._confirmaciones_hoy > 0:
            pa.color_indicador_validacion = [0.10, 0.72, 0.10, 1]
        else:
            pa.color_indicador_validacion = [0.80, 0.10, 0.10, 1]

        if faltas >= MAX_FALTAS:
            pi = self.root.get_screen('inactiva')
            pi.motivo_bloqueo = f"{faltas} faltas.\nPresentate a RH."
            pi.texto_faltas   = f"Faltas del mes: {contar_faltas_mes(historial)}"
            self.root.current = 'inactiva'
        else:
            cred = datos.get("credencial", "")
            cuad = datos.get("cuadrilla", "")
            nomb = datos.get("nombre", "")
            self.iniciar_anuncio_wifi(cred, cuad, nomb)
            self.iniciar_servidor_validacion(cred, cuad)
            self.iniciar_autovalidacion_apuntador(cred, cuad, nomb)
            self.iniciar_gps()
            Clock.schedule_once(lambda dt: self.cargar_qr(cred), 1.0)
            self.root.current = 'activa'

    def actualizar_badge_puesto(self):
        datos  = cargar_datos()
        es_fijo = datos.get("es_puesto_fijo", False)
        desc    = datos.get("puesto_fijo_desc", "")
        pa      = self.root.get_screen('activa')
        if es_fijo and desc:
            pa.texto_puesto_fijo  = f"PUESTO FIJO: {desc}"
            pa.color_badge_puesto = [0.18, 0.29, 0.55, 1]
        else:
            pa.texto_puesto_fijo  = "Sin puesto fijo — jornalero"
            pa.color_badge_puesto = [0.6, 0.6, 0.6, 1]

    def _actualizar_texto_turno(self, pa=None):
        if pa is None:
            pa = self.root.get_screen('activa')
        if self._confirmaciones_hoy == 0:
            pa.texto_turno = "Sin confirmar — emitiendo cada 3s"
            pa.color_turno = [0.96, 0.65, 0.14, 1]
        elif self._confirmaciones_hoy == 1:
            pa.texto_turno = "✓ Turno MATUTINO confirmado"
            pa.color_turno = [0.18, 0.42, 0.18, 1]
        else:
            pa.texto_turno = "✓✓ Turno VESPERTINO confirmado"
            pa.color_turno = [0.10, 0.30, 0.55, 1]

    def _actualizar_ui_anuncio(self, dt):
        if not self.root or self.root.current != 'activa':
            return
        pa = self.root.get_screen('activa')
        if self._confirmaciones_hoy == 0:
            pa.texto_proximo_anuncio = "Emitiendo cada 3s"
        elif self._proximo_anuncio:
            mins = max(0, int((self._proximo_anuncio - time.time()) / 60))
            pa.texto_proximo_anuncio = f"Proximo anuncio en: {mins} min"

    def cargar_qr(self, credencial: str):
        if not credencial:
            return
        def _gen(dt):
            tex = generar_qr_texture(credencial)
            if tex:
                self.root.get_screen('activa').ids.img_qr.texture = tex
        Clock.schedule_once(_gen, 0)

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
        def _act(dt):
            self.root.get_screen('activa').texto_gps = texto
            datos = cargar_datos()
            datos["lat"] = self._lat
            datos["lon"] = self._lon
            guardar_datos(datos)
        Clock.schedule_once(_act, 0)

    def _on_gps_status(self, stype, status):
        print(f"[GPS] {stype}: {status}")

    # ── Anuncio WiFi adaptativo ───────────────────────────────────────────────
    def iniciar_anuncio_wifi(self, credencial, cuadrilla, nombre):
        if self._anuncio_activo:
            return
        self._anuncio_activo = True

        def _anunciar():
            # Cambio 3: socket persistente — evita overhead de crear/cerrar en cada ciclo
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                # TTL=255 para que el broadcast alcance toda la subred
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, 255)
                sock.setblocking(False)
            except Exception as e:
                print(f"[WIFI] Error creando socket: {e}")
                self._anuncio_activo = False
                return

            self._enviar_anuncio(credencial, cuadrilla, nombre, sock)
            while self._anuncio_activo:
                intervalo = (
                    INTERVALO_SIN_CONF
                    if self._confirmaciones_hoy < MAX_CONFIRMACIONES
                    else INTERVALO_CON_CONF
                )
                self._proximo_anuncio = time.time() + intervalo
                time.sleep(intervalo)
                if self._anuncio_activo:
                    self._enviar_anuncio(credencial, cuadrilla, nombre, sock)

            try:
                sock.close()
            except Exception:
                pass

        threading.Thread(target=_anunciar, daemon=True).start()

    def _enviar_anuncio(self, credencial, cuadrilla, nombre, sock=None):
        try:
            datos         = cargar_datos()
            es_fijo       = datos.get("es_puesto_fijo", False)
            puesto_clave  = datos.get("puesto_fijo_clave", "")
            puesto_desc   = datos.get("puesto_fijo_desc", "").replace(':', '-')
            nombre_limpio = str(nombre).replace(':', ' ').replace('\n', ' ')
            tipo_trabajador = "FIJO" if es_fijo else "JORNALERO"

            mensaje = (
                f"PRESENTE:{credencial}:{cuadrilla}:{nombre_limpio}"
                f":{self._lat:.6f}:{self._lon:.6f}"
                f":{self._confirmaciones_hoy}"
                f":{tipo_trabajador}:{puesto_clave}:{puesto_desc[:20]}"
            )
            payload = _firmar_mensaje(mensaje).encode('utf-8')
            destino = ('255.255.255.255', PUERTO_ANUNCIO)

            # Cambio 3: enviar en ráfaga para compensar pérdida de paquetes UDP
            _sock_propio = sock is None
            if _sock_propio:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, 255)

            for i in range(RAFAGA_ANUNCIO):
                try:
                    sock.sendto(payload, destino)
                except Exception:
                    # Si el socket no-bloqueante está ocupado, reintentamos de inmediato
                    try:
                        sock.sendto(payload, destino)
                    except Exception:
                        pass
                if i < RAFAGA_ANUNCIO - 1:
                    time.sleep(PAUSA_RAFAGA)

            if _sock_propio:
                sock.close()
        except Exception as e:
            print(f"[WIFI] Error anuncio: {e}")

    def detener_anuncio(self):
        self._anuncio_activo = False

    # ── Servidor validacion (cuadrillero -> trabajador) ───────────────────────
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
                            msg = _verificar_mensaje(datos_raw)
                            if msg is None:
                                continue
                            partes = msg.split(':')
                            if (len(partes) >= 3 and
                                    partes[0] == 'VALIDAR' and
                                    partes[1] == str(credencial)):
                                turno = partes[4] if len(partes) > 4 else "matutino"
                                sock.sendto(_firmar_mensaje(f"OK:{credencial}").encode(), addr)
                                Clock.schedule_once(
                                    lambda dt, t=turno: self._registrar_asistencia(t), 0
                                )
                        except socket.timeout:
                            continue
                        except Exception as e:
                            print(f"[WIFI] Error: {e}")
            except Exception as e:
                print(f"[WIFI] Error servidor: {e}")
            finally:
                self._validacion_activa = False

        threading.Thread(target=_escuchar, daemon=True).start()

    # ── Auto-validacion para puesto fijo (apuntador -> trabajador) ────────────
    def iniciar_autovalidacion_apuntador(self, credencial, cuadrilla, nombre):
        if self._autovalidacion_activa:
            return
        self._autovalidacion_activa = True

        def _escuchar():
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.bind(('', PUERTO_APUNTADOR))
                    sock.settimeout(2.0)
                    while self._autovalidacion_activa:
                        try:
                            datos_raw, addr = sock.recvfrom(1024)
                            msg = _verificar_mensaje(datos_raw)
                            if msg is None:
                                continue
                            partes = msg.split(':')
                            # Formato: SCAN_FIJO:<credencial>
                            if (len(partes) >= 2 and
                                    partes[0] == 'SCAN_FIJO' and
                                    partes[1] == str(credencial)):
                                sock.sendto(
                                    _firmar_mensaje(f"OK_FIJO:{credencial}").encode(), addr
                                )
                                Clock.schedule_once(
                                    lambda dt: self._registrar_asistencia("matutino"), 0
                                )
                        except socket.timeout:
                            continue
                        except Exception as e:
                            print(f"[WIFI] Error autovalidacion: {e}")
            except Exception as e:
                print(f"[WIFI] Error autovalidacion servidor: {e}")
            finally:
                self._autovalidacion_activa = False

        threading.Thread(target=_escuchar, daemon=True).start()

    def _registrar_asistencia(self, turno: str = "matutino"):
        ahora     = datetime.datetime.now()
        datos     = cargar_datos()
        historial = datos.get("historial", [])
        historial = agregar_dia_historial(historial, estatus="presente", turno=turno)
        faltas    = calcular_faltas_consecutivas(historial)

        if self._confirmaciones_hoy < MAX_CONFIRMACIONES:
            self._confirmaciones_hoy += 1

        datos["historial"]           = historial
        datos["faltas_consecutivas"] = faltas
        datos["ultima_asistencia"]   = ahora.isoformat()
        datos["confirmaciones_hoy"]  = self._confirmaciones_hoy
        guardar_datos(datos)

        pa        = self.root.get_screen('activa')
        turno_txt = "MATUTINO" if turno == "matutino" else "VESPERTINO"
        pa.texto_estado_conexion       = f"✓ Turno {turno_txt}: {ahora.strftime('%H:%M')}"
        pa.color_estado                = [0.18, 0.42, 0.18, 1]
        pa.color_indicador_validacion  = [0.10, 0.72, 0.10, 1]   # verde
        pa.texto_vigencia              = self._texto_vigencia(faltas)
        self._actualizar_texto_turno(pa)

        if self.root.current == 'inactiva' and faltas < MAX_FALTAS:
            self.root.current = 'activa'
        Snackbar(text=f"✓ Turno {turno_txt}: {ahora.strftime('%H:%M')}").open()

    def _texto_vigencia(self, faltas: int) -> str:
        if faltas == 0:
            return "Sin faltas consecutivas"
        if MAX_FALTAS - faltas == 1:
            return "⚠ 1 falta mas = bloqueo"
        return f"Faltas: {faltas}/{MAX_FALTAS}"

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
            dias_ok      = {
                e.get("fecha") for e in historial
                if e.get("turno") == "matutino"
            }
            if es_dia_laboral(hoy) and hoy.isoformat() not in dias_ok:
                if ahora.hour >= hora_limite:
                    historial = agregar_dia_historial(
                        historial, estatus="falta", turno="matutino"
                    )
                    datos["historial"] = historial
                    guardar_datos(datos)
        faltas = 0 if gracia else calcular_faltas_consecutivas(historial)
        if faltas >= MAX_FALTAS:
            self.detener_anuncio()
            if self.root.current != 'inactiva':
                pi = self.root.get_screen('inactiva')
                pi.motivo_bloqueo = f"{faltas} faltas.\nPresentate a RH."
                pi.texto_faltas   = f"Faltas: {contar_faltas_mes(historial)}"
                self.root.current = 'inactiva'
        else:
            if self.root.current == 'activa':
                self.root.get_screen('activa').texto_vigencia = \
                    self._texto_vigencia(faltas)

    def on_stop(self):
        self.detener_anuncio()
        self._validacion_activa      = False
        self._autovalidacion_activa  = False


if __name__ == '__main__':
    CredencialAgriCactusApp().run()

