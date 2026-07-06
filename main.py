# =============================================================================
#  AgriCactus - App del CUADRILLERO  (main.py)
#  v3.6 - Fix deteccion WiFi (multicast lock) + sin comida + busqueda RH + rediseno
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
from kivymd.uix.list import TwoLineIconListItem, IconLeftWidget, OneLineListItem

ACTIVIDADES = [
    ("1000","APOYO CAMPO AGUA"),("1001","APOYO CAMPO BAÑOS"),
    ("1002","APOYO CAMPO BASURA"),("1003","APOYO CAMPO RANCHO"),
    ("1004","APOYO CAMPO TALLER"),("1005","APOYO CAMPO ASISTENCIA"),
    ("1006","APOYO CAMPO LIMPIEZA"),("1007","APOYO CAMPO LIMPIEZA GUARDERIA"),
    ("1008","PIPA"),("1009","TRANSPORTE PERSONAL"),("1010","TROQUE/CAMION"),
    ("1011","BATANGA AGUA"),("1012","BATANGA BOMBA BAÑOS"),("1013","BATANGA RESAGA"),
    ("1014","SUBSUELO"),("1015","PREPODA"),("1016","MOLINO RANCHO"),
    ("1017","MEZCLADORA ALIMENTO RANCHO"),("1018","SEMBRADORA"),("1019","BATANGA"),
    ("1020","APLICADORA FOLIAR"),("1021","ARADO/BARVECHO"),("1022","RASTRA"),
    ("1023","TABLON"),("1024","BORDERO CINTA Y ACOLCHADO"),("1025","ESCREPA"),
    ("1026","APLICADORA HERBICIDA"),("1027","HAYBINE"),("1028","CORTADORA DE DISCOS"),
    ("1029","RASTRILLO"),("1030","EMPACADORA"),("1031","MONTAGARGA CALABAZA"),
    ("1032","APLICACION MOCHILA"),("1033","AUXILIAR DE RIEGO"),("1034","REGADOR"),
    ("1035","SUPERVISOR DE RIEGO"),("1036","PODA DIA"),("1037","PODA ENSAYO"),
    ("1038","CUADRILLERO"),("1039","SUPERVISOR"),("1040","SUPERVISOR GENERAL"),
    ("1041","SUPERVISOR GENERAL 1"),("1042","SUPERVISOR RECLUTADOR 2"),
    ("1043","SUPERVISOR RECLUTADOR 3"),("1044","SUPERVISOR RECLUTADOR 4"),
    ("1045","SACAR PLANTAS UVA"),("1046","DESHIERBE"),("1047","QUEMANDO ALAMBRE"),
    ("1048","APOYO CAMPO EN GENERAL"),("1049","LOMBRICARIO"),
    ("1050","CORTINA APLICACION"),("1051","PREPARADOR DE MEZCLA"),
    ("1052","AUXILIAR PREPARADOR DE MEZCLAS"),("1053","CATERPILLAR"),
    ("1054","TRITURADORA DE BROCHA"),("1055","RETROESCABADORA"),
    ("1056","AMARRE DE PUENTES Y EXTENCIONES"),("1057","AUXILIAR OPERADOR"),
    ("1058","OPERADOR"),("1059","EMPAQUE CALABAZA"),("1060","EMPAQUE CALABAZA 1"),
    ("1061","LEVANTANDO CALABAZA"),("1062","MOVER CALABAZA"),
    ("1063","LIMPIEZA DE CUADROS"),("1064","APOYO GUARDERIA"),("1065","BATANGA 1"),
    ("1066","SERVICIO EN HACIENDA"),("1067","APOYO CAMPO ADMINISTRATIVO"),
    ("1068","VELADOR POZO"),("1069","VELADOR EMPAQUE"),("1070","VELADOR TALLER"),
    ("1071","VELADOR PORTERO"),("1074","TAXI"),("1075","JONALERO TAXI"),
    ("1076","REFORZAR Y PARCHAR AGRIBON"),("1077","COLOCACION DE AROS"),
    ("1078","ACARREO DE AROS Y AGRIBON"),("1079","ALIMENTANDO LOMBRICES"),
    ("1080","PLANTACION"),("1081","INSTALACION PLASTICO Y CINTA"),
    ("1082","PODA NOGAL SP + PLANTAS"),("1084","COLOCACION DE AGRIBON"),
    ("1085","ENTRENE"),("1086","MONTACARGUISTA"),
    ("1087","MANTENIMIENTO DE EMPARRADO"),("1088","MARCACION PLANTACION"),
    ("1089","APLICACION MOCHOMO TOPOS"),("1090","DESBROTE"),("1091","MATEADO"),
    ("1092","ACOMODO DE GUIA"),("1093","ATOMIZANDO"),("1094","DESCOLE"),
    ("1095","SELECCION DE RACIMOS"),("1096","DESHOJE"),("1097","ANILLADA"),
    ("1098","DESPUNTE DE RACIMOS"),("1099","MONTACARGUISTA SANDIA"),
    ("1100","ETIQUETADOR SANDIA"),("1101","TARIMERO"),
    ("1102","LIMPIEZA EMPAQUE SANDIA"),("1103","APOYO EMPAQUE SANDIA"),
    ("1104","APUNTADOR COSECHA SANDIA"),("1106","TROQUE ACARREO DE SANDIA"),
    ("1107","AUXILIAR ETIQUETADOR"),("1108","BAÑERAS"),
    ("1109","SELECCION Y DESPUNTE DE RACIMOS"),("1110","TAPADO DE RACIMOS"),
    ("1112","RALEO POR DIA"),("1113","ARREGLO DE RACIMOS"),
    ("1114","ETIQUETADOR UVA"),("1115","CARGADOR UVA"),
    ("1116","AUXILIAR CARGADOR UVA"),("1117","APOYO INOCUIDAD"),
    ("1118","APOYO EMPAQUE UVA"),("1119","APOYO LIMPIEZA EMPAQUE UVA"),
    ("1120","PASERO"),("1121","SUPERVISOR UVA CAMPO"),
    ("1122","TROQUE ACARREO UVA"),("1123","ENCARGADA DE INOCUIDAD"),
    ("1124","CUADRILLERO TAXI"),("1128","DESCHUPONE"),
    ("1129","INSTALACION DE EMPARRE"),("1130","DESEMPARRE"),
    ("1131","OPERADOR DUMPER"),("1133","CULTIVADORA"),
    ("1134","APOYO CAMPO HERBICIDAS"),("1135","BORDERO TRIPLE"),
    ("1154","COSECHA NUEZ"),("1164","CONTRATO SANDIA"),("1165","CONTRATO UVA"),
    ("1172","CORTAR CALABAZA"),("1176","RIEGO RODADO"),("1178","CONTRATO PODA"),
    ("1240","COSECHA UVA DIARIO"),("1290","CONTRATO RALEO"),
    ("1300","PODA NOGAL"),("1301","QUITAR PLASTICO-CINTA"),("1302","SACAR GUIA"),
    ("1330","CONTRATO DESBROCHE"),("1389","PODA DIARIO 2023/2024"),
    ("1391","ACARREO Y MOJADO DE PLANTA"),("1395","TAREAS PLASTICO CINTA Y AROS"),
    ("1398","CORTA GUIAS"),("1399","BORDERO INVERTIDO"),
    ("1421","CONTEO DE RACIMOS"),("1442","ARREGLO DE RACIMOS 1/4"),
    ("1449","CONTAR PLANTAS"),("1456","PODA DIA 2024-2025"),
    ("1462","POLINIZADOR"),("1499","DESGALLE"),
    ("1500","EMPAQUE GENERAL BICENTENARIO"),("1507","CALIDAD EMPAQUE"),
    ("1508","ARMADO DE CAJA UVA"),("1541","DESCABEZADO DE PLANTAS"),
    ("1542","ENCARGADA DE LABORATORIO"),
]

ARCHIVO_DATOS      = "cuadrillero_data.json"
ARCHIVO_LISTA      = "lista_asistencia.json"
PUERTO_ANUNCIO     = 45678
PUERTO_VALIDACION  = 45679
PUERTO_CUADRILLERO = 45680
PUERTO_RECEPCION   = 45681
PUERTO_ANUNCIO_CU  = 45682
INTERVALO_ANUNCIO  = 30

# Consulta al servidor de empleados (misma laptop/servicio que usa el Trabajador)
PUERTO_CONSULTA_EMP     = 45690
TIMEOUT_CONSULTA_EMP    = 3.0
REINTENTOS_CONSULTA_EMP = 3

PERIODO_ENTRADA = "entrada"
PERIODO_CAMBIO  = "cambio_cuadro"
PERIODO_SALIDA  = "salida_final"


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

def guardar_lista(datos: dict):
    try:
        with open(ARCHIVO_LISTA, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[STORAGE] Error lista: {e}")


KV = '''
#:import FadeTransition kivy.uix.screenmanager.FadeTransition
#:import FitImage kivymd.uix.fitimage.FitImage

ScreenManager:
    transition: FadeTransition()
    PantallaRegistro:
    PantallaCredencial:
    PantallaAsistencia:
    PantallaBuscadorActividad:
    PantallaResumen:


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
                text: "REGISTRO CUADRILLERO"
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
            pos_hint: {'center_x': 0.5, 'center_y': 0.78}
            size_hint_x: 0.88

        MDTextField:
            id: input_nss
            hint_text: "Numero de Seguro Social (NSS)"
            max_text_length: 11
            input_filter: "int"
            line_color_focus: 0.18, 0.29, 0.12, 1
            pos_hint: {'center_x': 0.5, 'center_y': 0.68}
            size_hint_x: 0.88

        MDBoxLayout:
            orientation: 'horizontal'
            size_hint: (0.88, 0.07)
            pos_hint: {'center_x': 0.5, 'center_y': 0.575}
            spacing: '6dp'

            MDTextField:
                id: input_credencial
                hint_text: "Numero de Credencial / Empleado"
                input_filter: "int"
                line_color_focus: 0.18, 0.29, 0.12, 1
                size_hint_x: 0.68
                on_text_validate: root.buscar_datos_empleado()

            MDRectangleFlatIconButton:
                icon: "magnify"
                text: "BUSCAR"
                theme_text_color: "Custom"
                text_color: 0.18, 0.29, 0.12, 1
                line_color: 0.18, 0.29, 0.12, 1
                size_hint_x: 0.32
                pos_hint: {'center_y': 0.4}
                on_release: root.buscar_datos_empleado()

        MDLabel:
            id: label_busqueda
            text: ""
            font_style: "Caption"
            halign: "center"
            theme_text_color: "Custom"
            text_color: 0.5, 0.5, 0.5, 1
            pos_hint: {'center_x': 0.5, 'center_y': 0.525}
            size_hint_x: 0.88

        MDTextField:
            id: input_cuadrilla
            hint_text: "Numero de Cuadrilla a cargo"
            input_filter: "int"
            line_color_focus: 0.18, 0.29, 0.12, 1
            pos_hint: {'center_x': 0.5, 'center_y': 0.44}
            size_hint_x: 0.88

        MDBoxLayout:
            orientation: 'horizontal'
            size_hint: (0.88, 0.07)
            pos_hint: {'center_x': 0.5, 'center_y': 0.34}
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
            pos_hint: {'center_x': 0.5, 'center_y': 0.26}

        MDRaisedButton:
            text: "GENERAR CREDENCIAL DIGITAL"
            md_bg_color: 0.18, 0.29, 0.12, 1
            pos_hint: {'center_x': 0.5, 'center_y': 0.13}
            size_hint_x: 0.88
            elevation: 4
            on_release: root.guardar_registro()


<PantallaCredencial>:
    name: 'credencial'

    MDFloatLayout:
        md_bg_color: 0.94, 0.96, 0.94, 1

        MDFloatLayout:
            size_hint_x: 0.06
            pos_hint: {'x': 0, 'y': 0}
            md_bg_color: 0.18, 0.29, 0.12, 1

        MDCard:
            size_hint: (0.92, 0.76)
            pos_hint: {'right': 0.99, 'top': 0.97}
            elevation: 6
            radius: [18, 18, 18, 18]
            md_bg_color: 1, 1, 1, 1

            MDFloatLayout:

                MDFloatLayout:
                    size_hint_y: 0.20
                    pos_hint: {'x': 0, 'top': 1}
                    md_bg_color: 0.18, 0.29, 0.12, 1

                    Image:
                        source: "logo_agricactus.png"
                        size_hint: (0.44, 0.80)
                        allow_stretch: True
                        keep_ratio: True
                        pos_hint: {'center_x': 0.26, 'center_y': 0.5}

                    MDLabel:
                        text: "CUADRILLERO"
                        font_style: "Caption"
                        bold: True
                        halign: "center"
                        theme_text_color: "Custom"
                        text_color: 0.96, 0.65, 0.14, 1
                        pos_hint: {'center_x': 0.72, 'center_y': 0.65}
                        size_hint: (0.52, 0.22)

                    MDLabel:
                        text: "CREDENCIAL DIGITAL"
                        font_style: "Caption"
                        halign: "center"
                        theme_text_color: "Custom"
                        text_color: 0.78, 0.92, 0.78, 1
                        pos_hint: {'center_x': 0.72, 'center_y': 0.32}
                        size_hint: (0.52, 0.22)

                MDBoxLayout:
                    size_hint: (1, 0.004)
                    pos_hint: {'x': 0, 'top': 0.80}
                    md_bg_color: 0.96, 0.65, 0.14, 1

                FitImage:
                    source: root.ruta_foto
                    size_hint: (0.28, 0.34)
                    pos_hint: {'x': 0.04, 'top': 0.78}
                    radius: [10, 10, 10, 10]

                MDLabel:
                    text: root.nombre_cuadrillero
                    markup: True
                    font_style: "H6"
                    bold: True
                    halign: "left"
                    valign: "center"
                    theme_text_color: "Custom"
                    text_color: 0.12, 0.22, 0.08, 1
                    text_size: self.size
                    pos_hint: {'x': 0.36, 'top': 0.78}
                    size_hint: (0.60, 0.14)

                MDLabel:
                    text: "Ingreso: " + root.fecha_ingreso
                    font_style: "Caption"
                    halign: "left"
                    theme_text_color: "Secondary"
                    pos_hint: {'x': 0.36, 'top': 0.64}
                    size_hint: (0.60, 0.05)

                MDLabel:
                    text: "Cuadrilla: " + root.num_cuadrilla
                    font_style: "Body2"
                    bold: True
                    halign: "left"
                    theme_text_color: "Custom"
                    text_color: 0.18, 0.42, 0.18, 1
                    pos_hint: {'x': 0.36, 'top': 0.59}
                    size_hint: (0.60, 0.05)

                MDLabel:
                    text: "NSS: " + root.nss
                    font_style: "Caption"
                    halign: "left"
                    theme_text_color: "Custom"
                    text_color: 0.4, 0.4, 0.4, 1
                    pos_hint: {'x': 0.36, 'top': 0.54}
                    size_hint: (0.60, 0.05)

                MDBoxLayout:
                    size_hint: (0.90, 0.004)
                    pos_hint: {'center_x': 0.5, 'top': 0.48}
                    md_bg_color: 0.96, 0.65, 0.14, 1

                MDLabel:
                    text: "No. " + root.num_credencial
                    font_style: "H4"
                    bold: True
                    halign: "center"
                    theme_text_color: "Custom"
                    text_color: 0.12, 0.22, 0.08, 1
                    pos_hint: {'center_x': 0.5, 'top': 0.47}
                    size_hint: (0.88, 0.10)

                MDFloatLayout:
                    size_hint_y: 0.05
                    pos_hint: {'x': 0, 'y': 0}
                    md_bg_color: 0.18, 0.29, 0.12, 1
                    MDLabel:
                        text: "Blvd. Kino 309, Piso 6 - Hermosillo, Sonora"
                        font_style: "Caption"
                        halign: "center"
                        theme_text_color: "Custom"
                        text_color: 0.8, 0.9, 0.8, 1

        MDRaisedButton:
            text: "INICIAR JORNADA"
            md_bg_color: 0.18, 0.29, 0.12, 1
            pos_hint: {'center_x': 0.55, 'y': 0.13}
            size_hint: (0.80, 0.07)
            elevation: 5
            on_release: root.ir_a_asistencia()

        MDRectangleFlatButton:
            text: "EDITAR DATOS"
            theme_text_color: "Custom"
            text_color: 0.18, 0.29, 0.12, 1
            line_color: 0.18, 0.29, 0.12, 1
            pos_hint: {'center_x': 0.55, 'y': 0.05}
            size_hint: (0.80, 0.07)
            on_release: app.root.current = 'registro'


<PantallaAsistencia>:
    name: 'asistencia'

    MDFloatLayout:
        md_bg_color: 0.94, 0.96, 0.94, 1

        MDFloatLayout:
            size_hint_y: 0.12
            pos_hint: {'x': 0, 'top': 1}
            md_bg_color: 0.18, 0.29, 0.12, 1

            Image:
                source: "logo_agricactus.png"
                size_hint: (0.24, 0.76)
                allow_stretch: True
                keep_ratio: True
                pos_hint: {'center_x': 0.14, 'center_y': 0.5}

            MDLabel:
                text: root.titulo_sesion
                font_style: "Body1"
                bold: True
                halign: "center"
                theme_text_color: "Custom"
                text_color: 1, 1, 1, 1
                pos_hint: {'center_x': 0.58, 'center_y': 0.62}
                size_hint: (0.68, 0.38)

            MDLabel:
                text: root.fecha_hoy
                font_style: "Caption"
                halign: "center"
                theme_text_color: "Custom"
                text_color: 0.96, 0.65, 0.14, 1
                pos_hint: {'center_x': 0.58, 'center_y': 0.26}
                size_hint: (0.68, 0.28)

        MDBoxLayout:
            size_hint_y: 0.004
            pos_hint: {'x': 0, 'top': 0.88}
            md_bg_color: 0.96, 0.65, 0.14, 1

        MDCard:
            size_hint: (0.96, 0.055)
            pos_hint: {'center_x': 0.5, 'top': 0.875}
            elevation: 1
            radius: [8, 8, 8, 8]
            md_bg_color: root.color_estado_jornada

            MDLabel:
                text: root.texto_estado_jornada
                font_style: "Caption"
                bold: True
                halign: "center"
                theme_text_color: "Custom"
                text_color: 1, 1, 1, 1

        MDBoxLayout:
            orientation: 'horizontal'
            size_hint: (0.96, None)
            height: '44dp'
            pos_hint: {'center_x': 0.5, 'top': 0.818}
            spacing: '6dp'

            MDTextField:
                id: input_cuadro
                hint_text: "Cuadro / Lote"
                line_color_focus: 0.18, 0.29, 0.12, 1
                size_hint_x: 0.35

            MDRectangleFlatButton:
                id: btn_actividad
                text: root.actividad_seleccionada
                theme_text_color: "Custom"
                text_color: 0.18, 0.29, 0.12, 1
                line_color: 0.18, 0.29, 0.12, 1
                size_hint_x: 0.65
                on_release: app.root.current = 'buscador'

        MDCard:
            size_hint: (0.96, 0.10)
            pos_hint: {'center_x': 0.5, 'top': 0.73}
            elevation: 3
            radius: [12, 12, 12, 12]
            md_bg_color: 1, 1, 1, 1

            MDBoxLayout:
                orientation: 'horizontal'
                padding: '8dp'
                spacing: '4dp'

                MDBoxLayout:
                    orientation: 'vertical'
                    MDLabel:
                        text: root.total_presentes
                        font_style: "H5"
                        bold: True
                        halign: "center"
                        theme_text_color: "Custom"
                        text_color: 0.18, 0.42, 0.18, 1
                    MDLabel:
                        text: "Presentes"
                        font_style: "Caption"
                        halign: "center"
                        theme_text_color: "Secondary"

                MDBoxLayout:
                    orientation: 'vertical'
                    MDLabel:
                        text: root.total_fijos
                        font_style: "H5"
                        bold: True
                        halign: "center"
                        theme_text_color: "Custom"
                        text_color: 0.18, 0.29, 0.55, 1
                    MDLabel:
                        text: "Fijos"
                        font_style: "Caption"
                        halign: "center"
                        theme_text_color: "Secondary"

                MDBoxLayout:
                    orientation: 'vertical'
                    MDLabel:
                        text: root.total_detectados
                        font_style: "H5"
                        bold: True
                        halign: "center"
                        theme_text_color: "Custom"
                        text_color: 0.96, 0.65, 0.14, 1
                    MDLabel:
                        text: "Total"
                        font_style: "Caption"
                        halign: "center"
                        theme_text_color: "Secondary"

                MDBoxLayout:
                    orientation: 'vertical'
                    MDLabel:
                        text: root.estado_escucha
                        font_style: "Caption"
                        bold: True
                        halign: "center"
                        theme_text_color: "Custom"
                        text_color: root.color_estado_escucha
                    MDLabel:
                        text: "WiFi"
                        font_style: "Caption"
                        halign: "center"
                        theme_text_color: "Secondary"

        MDCard:
            size_hint: (0.96, 0.36)
            pos_hint: {'center_x': 0.5, 'top': 0.645}
            elevation: 3
            radius: [12, 12, 12, 12]
            md_bg_color: 1, 1, 1, 1

            MDBoxLayout:
                orientation: 'vertical'
                padding: '4dp'

                MDLabel:
                    text: "Trabajadores  [ azul = puesto fijo ]"
                    font_style: "Caption"
                    bold: True
                    halign: "center"
                    theme_text_color: "Custom"
                    text_color: 0.18, 0.29, 0.12, 1
                    size_hint_y: None
                    height: '24dp'

                ScrollView:
                    MDList:
                        id: lista_trabajadores

        MDBoxLayout:
            orientation: 'horizontal'
            size_hint: (0.96, 0.075)
            pos_hint: {'center_x': 0.5, 'top': 0.255}
            spacing: '10dp'

            MDRaisedButton:
                text: "VALIDAR ENTRADA"
                md_bg_color: 0.18, 0.42, 0.18, 1
                size_hint_x: 0.5
                font_size: '13sp'
                elevation: 3
                on_release: root.accion_periodo('entrada')

            MDRaisedButton:
                text: "CAMBIO DE CUADRO"
                md_bg_color: 0.55, 0.18, 0.55, 1
                size_hint_x: 0.5
                font_size: '13sp'
                elevation: 3
                on_release: root.accion_periodo('cambio_cuadro')

        MDBoxLayout:
            orientation: 'horizontal'
            size_hint: (0.96, 0.07)
            pos_hint: {'center_x': 0.5, 'top': 0.17}
            spacing: '6dp'

            MDRaisedButton:
                text: "VALIDAR TODOS"
                md_bg_color: 0.18, 0.29, 0.12, 1
                size_hint_x: 0.5
                elevation: 2
                on_release: root.validar_todos()

            MDRaisedButton:
                text: "VER RESUMEN"
                md_bg_color: 0.96, 0.65, 0.14, 1
                text_color: 0.12, 0.22, 0.08, 1
                size_hint_x: 0.5
                elevation: 2
                on_release: root.ver_resumen()

        MDRectangleFlatButton:
            text: "MI CREDENCIAL"
            theme_text_color: "Custom"
            text_color: 0.18, 0.29, 0.12, 1
            line_color: 0.18, 0.29, 0.12, 1
            size_hint: (0.96, 0.07)
            pos_hint: {'center_x': 0.5, 'y': 0.01}
            on_release: app.root.current = 'credencial'


<PantallaBuscadorActividad>:
    name: 'buscador'

    MDFloatLayout:
        md_bg_color: 0.94, 0.96, 0.94, 1

        MDFloatLayout:
            size_hint_y: 0.13
            pos_hint: {'x': 0, 'top': 1}
            md_bg_color: 0.18, 0.29, 0.12, 1

            MDLabel:
                text: "SELECCIONAR ACTIVIDAD"
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

        MDTextField:
            id: input_buscar
            hint_text: "Buscar por nombre o clave..."
            line_color_focus: 0.18, 0.29, 0.12, 1
            pos_hint: {'center_x': 0.5, 'top': 0.85}
            size_hint: (0.96, None)
            height: '48dp'
            on_text: root.filtrar_actividades(self.text)

        ScrollView:
            size_hint: (0.96, 0.68)
            pos_hint: {'center_x': 0.5, 'top': 0.76}
            MDList:
                id: lista_actividades

        MDRaisedButton:
            text: "CANCELAR"
            md_bg_color: 0.65, 0.08, 0.08, 1
            size_hint: (0.96, 0.07)
            pos_hint: {'center_x': 0.5, 'y': 0.01}
            on_release: app.root.current = 'asistencia'


<PantallaResumen>:
    name: 'resumen'

    MDFloatLayout:
        md_bg_color: 0.94, 0.96, 0.94, 1

        MDFloatLayout:
            size_hint_y: 0.12
            pos_hint: {'x': 0, 'top': 1}
            md_bg_color: 0.18, 0.29, 0.12, 1

            MDLabel:
                text: "RESUMEN / AVANCE"
                font_style: "H6"
                bold: True
                halign: "center"
                theme_text_color: "Custom"
                text_color: 0.96, 0.65, 0.14, 1
                pos_hint: {'center_x': 0.5, 'center_y': 0.5}
                size_hint: (1, 1)

        MDBoxLayout:
            size_hint_y: 0.004
            pos_hint: {'x': 0, 'top': 0.88}
            md_bg_color: 0.96, 0.65, 0.14, 1

        MDCard:
            size_hint: (0.96, 0.72)
            pos_hint: {'center_x': 0.5, 'top': 0.875}
            elevation: 3
            radius: [12, 12, 12, 12]
            md_bg_color: 1, 1, 1, 1

            MDBoxLayout:
                orientation: 'vertical'
                padding: '10dp'
                spacing: '6dp'

                MDLabel:
                    text: root.resumen_texto
                    font_style: "Body2"
                    halign: "center"
                    theme_text_color: "Custom"
                    text_color: 0.12, 0.22, 0.08, 1
                    size_hint_y: None
                    height: '96dp'

                ScrollView:
                    MDList:
                        id: lista_resumen

        MDBoxLayout:
            orientation: 'horizontal'
            size_hint: (0.96, 0.08)
            pos_hint: {'center_x': 0.5, 'y': 0.01}
            spacing: '6dp'

            MDRaisedButton:
                text: "GUARDAR AVANCE"
                md_bg_color: 0.18, 0.29, 0.12, 1
                size_hint_x: 0.34
                elevation: 3
                on_release: root.guardar_avance()

            MDRaisedButton:
                text: "CERRAR JORNADA"
                md_bg_color: 0.65, 0.08, 0.08, 1
                size_hint_x: 0.34
                elevation: 3
                on_release: root.cerrar_jornada()

            MDRaisedButton:
                text: "REGRESAR"
                md_bg_color: 0.96, 0.65, 0.14, 1
                text_color: 0.12, 0.22, 0.08, 1
                size_hint_x: 0.32
                elevation: 3
                on_release: app.root.current = 'asistencia'
'''


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
            ruta      = f"{files_dir}/cuadrillero_foto.jpg"
            fos = FileOutputStream(ruta)
            bitmap.compress(BitmapCompressFormat.JPEG, 90, fos)
            fos.close()
            self.ruta_foto_seleccionada = ruta
            self.ids.label_foto.text    = "Foto tomada"
        except Exception as e:
            self.ids.label_foto.text = f"Error: {e}"

    def abrir_galeria(self):
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

    # ── Consulta al servidor de empleados (empleados_server.py) ──────────────
    def buscar_datos_empleado(self):
        credencial = self.ids.input_credencial.text.strip()
        if not credencial:
            Snackbar(text="Escribe primero el numero de credencial").open()
            return

        self.ids.label_busqueda.text       = "Buscando en la red..."
        self.ids.label_busqueda.text_color = (0.5, 0.5, 0.5, 1)

        app = MDApp.get_running_app()
        app.buscar_empleado_red(
            credencial,
            callback_ok=self._al_encontrar_empleado,
            callback_error=self._al_fallar_busqueda,
        )

    def _al_encontrar_empleado(self, datos: dict):
        self.ids.input_nombre.text = datos.get("nombre", "")
        self.ids.input_nss.text    = datos.get("nss", "")
        if datos.get("cuadrilla"):
            self.ids.input_cuadrilla.text = datos.get("cuadrilla", "")

        self.ids.label_busqueda.text       = f"✓ Encontrado: {datos.get('nombre', '')}"
        self.ids.label_busqueda.text_color = (0.18, 0.42, 0.18, 1)
        Snackbar(text="Datos cargados desde RH").open()

    def _al_fallar_busqueda(self, mensaje: str):
        self.ids.label_busqueda.text       = mensaje
        self.ids.label_busqueda.text_color = (0.7, 0.2, 0.15, 1)
        Snackbar(text=mensaje).open()

    def guardar_registro(self):
        nombre     = self.ids.input_nombre.text.strip().upper()
        nss        = self.ids.input_nss.text.strip()
        credencial = self.ids.input_credencial.text.strip()
        cuadrilla  = self.ids.input_cuadrilla.text.strip()

        errores = []
        if not nombre:     errores.append("nombre")
        if len(nss) < 10:  errores.append("NSS")
        if not credencial: errores.append("credencial")
        if not cuadrilla:  errores.append("cuadrilla")
        if not self.ruta_foto_seleccionada: errores.append("foto")

        if errores:
            Snackbar(text=f"Falta: {', '.join(errores)}").open()
            return

        app = MDApp.get_running_app()
        pc  = app.root.get_screen('credencial')

        palabras = nombre.split()
        if len(palabras) >= 3:
            nombre_fmt = f"{palabras[0]} {palabras[1]}\n{' '.join(palabras[2:])}"
        elif len(palabras) == 2:
            nombre_fmt = f"{palabras[0]}\n{palabras[1]}"
        else:
            nombre_fmt = nombre

        pc.nombre_cuadrillero = nombre_fmt
        pc.nss                = nss
        pc.num_credencial     = credencial
        pc.num_cuadrilla      = cuadrilla
        pc.ruta_foto          = self.ruta_foto_seleccionada
        pc.fecha_ingreso      = datetime.date.today().strftime("%d/%m/%Y")

        app.num_cuadrilla      = cuadrilla
        app.nombre_cuadrillero = nombre_fmt

        guardar_datos({
            "nombre":        nombre_fmt,
            "nss":           nss,
            "credencial":    credencial,
            "cuadrilla":     cuadrilla,
            "foto":          self.ruta_foto_seleccionada,
            "fecha_ingreso": pc.fecha_ingreso,
            "ultima_sesion": datetime.datetime.now().isoformat()
        })
        app.root.current = 'credencial'
        Snackbar(text="Credencial generada").open()


class PantallaCredencial(Screen):
    nombre_cuadrillero = StringProperty("")
    fecha_ingreso      = StringProperty("")
    nss                = StringProperty("")
    num_credencial     = StringProperty("")
    num_cuadrilla      = StringProperty("")
    ruta_foto          = StringProperty("")

    def ir_a_asistencia(self):
        app = MDApp.get_running_app()
        pa  = app.root.get_screen('asistencia')
        pa.titulo_sesion = f"Cuadrilla {self.num_cuadrilla}"
        pa.fecha_hoy     = datetime.datetime.now().strftime("%d/%m/%Y  %H:%M")
        app.iniciar_escucha_trabajadores()
        app.iniciar_respuesta_apuntador()
        app.root.current = 'asistencia'
        Snackbar(text="Jornada iniciada").open()


class PantallaAsistencia(Screen):
    titulo_sesion          = StringProperty("Cuadrilla")
    fecha_hoy              = StringProperty("")
    total_presentes        = StringProperty("0")
    total_detectados       = StringProperty("0")
    total_fijos            = StringProperty("0")
    estado_escucha         = StringProperty("Inactivo")
    color_estado_escucha   = ListProperty([0.6, 0.6, 0.6, 1])
    actividad_seleccionada = StringProperty("Seleccionar actividad...")
    texto_estado_jornada   = StringProperty("JORNADA ABIERTA")
    color_estado_jornada   = ListProperty([0.18, 0.42, 0.18, 1])

    def actualizar_lista_ui(self, trabajadores: dict):
        self.ids.lista_trabajadores.clear_widgets()
        presentes = 0
        fijos     = 0

        items_ordenados = sorted(
            trabajadores.items(),
            key=lambda x: (0 if x[1].get('tipo_trabajador') == 'FIJO' else 1)
        )

        for credencial, info in items_ordenados:
            validado    = info.get('validado', False)
            nombre      = info.get('nombre', f"Cred. {credencial}")
            periodos    = info.get('periodos', [])
            es_fijo     = info.get('tipo_trabajador', '') == 'FIJO'
            puesto_desc = info.get('puesto_fijo_desc', '')

            if validado: presentes += 1
            if es_fijo:  fijos += 1

            ultimo     = periodos[-1] if periodos else {}
            estado_txt = ultimo.get('tipo', '').replace('_', ' ').upper() or (
                'PRESENTE' if validado else 'Detectado'
            )
            hora_txt = ultimo.get('hora', info.get('hora_deteccion', '--'))

            if es_fijo:
                icono_nombre = "briefcase-check"
                icono_color  = (0.18, 0.29, 0.55, 1)
                subtexto     = f"[FIJO: {puesto_desc[:25]}]  {hora_txt}"
            elif validado:
                icono_nombre = "check-circle"
                icono_color  = (0.18, 0.42, 0.18, 1)
                subtexto     = f"{estado_txt}  {hora_txt}  |  {len(periodos)} reg"
            else:
                icono_nombre = "wifi"
                icono_color  = (0.96, 0.65, 0.14, 1)
                subtexto     = f"{estado_txt}  {hora_txt}  |  {len(periodos)} reg"

            icono = IconLeftWidget(
                icon=icono_nombre,
                theme_text_color="Custom",
                icon_color=icono_color
            )
            item = TwoLineIconListItem(
                text=f"[b]{nombre}[/b]  |  No. {credencial}",
                secondary_text=subtexto,
            )
            item.add_widget(icono)
            self.ids.lista_trabajadores.add_widget(item)

        self.total_presentes  = str(presentes)
        self.total_detectados = str(len(trabajadores))
        self.total_fijos      = str(fijos)

    def accion_periodo(self, tipo: str):
        app       = MDApp.get_running_app()
        cuadro    = self.ids.input_cuadro.text.strip().upper() or "SIN CUADRO"
        actividad = self.actividad_seleccionada

        count = 0
        for cred in list(app.trabajadores_detectados.keys()):
            info = app.trabajadores_detectados[cred]
            if info.get('tipo_trabajador') != 'FIJO':
                app.enviar_validacion(cred, tipo, cuadro, actividad)
                count += 1

        etiquetas = {
            PERIODO_ENTRADA: "VALIDANDO ENTRADA",
            PERIODO_CAMBIO:  "VALIDANDO CAMBIO DE CUADRO",
        }
        colores = {
            PERIODO_ENTRADA: [0.18, 0.42, 0.18, 1],
            PERIODO_CAMBIO:  [0.55, 0.18, 0.55, 1],
        }
        self.texto_estado_jornada = etiquetas.get(tipo, tipo.upper())
        self.color_estado_jornada = colores.get(tipo, [0.3, 0.3, 0.3, 1])
        Snackbar(text=f"{etiquetas.get(tipo, tipo)} — {count} jornaleros").open()

    def validar_todos(self):
        app      = MDApp.get_running_app()
        cuadro   = self.ids.input_cuadro.text.strip().upper() or "SIN CUADRO"
        actividad = self.actividad_seleccionada
        count = 0
        for cred in list(app.trabajadores_detectados.keys()):
            info = app.trabajadores_detectados[cred]
            if not info.get('validado') and info.get('tipo_trabajador') != 'FIJO':
                app.enviar_validacion(cred, PERIODO_ENTRADA, cuadro, actividad)
                count += 1
        Snackbar(
            text=f"{count} jornaleros validados" if count else "Todos validados"
        ).open()

    def ver_resumen(self):
        app      = MDApp.get_running_app()
        cuadro   = self.ids.input_cuadro.text.strip().upper() or "SIN CUADRO"
        actividad = self.actividad_seleccionada
        pr       = app.root.get_screen('resumen')
        pr.construir_resumen(
            app.trabajadores_detectados,
            app.nombre_cuadrillero,
            app.num_cuadrilla,
            cuadro, actividad, cerrada=False
        )
        app.cuadro_trabajo    = cuadro
        app.actividad_trabajo = actividad
        app.root.current      = 'resumen'


class PantallaBuscadorActividad(Screen):
    def on_enter(self):
        self.ids.input_buscar.text = ""
        self.filtrar_actividades("")

    def filtrar_actividades(self, texto):
        self.ids.lista_actividades.clear_widgets()
        txt = texto.strip().upper()
        resultados = [
            (c, d) for c, d in ACTIVIDADES
            if txt in d.upper() or txt in c
        ] if txt else ACTIVIDADES[:60]
        for clave, desc in resultados:
            item = OneLineListItem(
                text=f"{clave} - {desc}",
                on_release=lambda x, c=clave, d=desc: self._seleccionar(c, d)
            )
            self.ids.lista_actividades.add_widget(item)

    def _seleccionar(self, clave, desc):
        app = MDApp.get_running_app()
        pa  = app.root.get_screen('asistencia')
        pa.actividad_seleccionada = f"{clave} - {desc}"
        app.actividad_trabajo     = f"{clave} - {desc}"
        app.root.current          = 'asistencia'


class PantallaResumen(Screen):
    resumen_texto = StringProperty("")

    def construir_resumen(self, trabajadores, cuadrillero, cuadrilla,
                           cuadro, actividad, cerrada=False):
        presentes = sum(1 for v in trabajadores.values() if v.get('validado'))
        fijos     = sum(1 for v in trabajadores.values()
                        if v.get('tipo_trabajador') == 'FIJO')
        total     = len(trabajadores)
        fecha     = datetime.datetime.now().strftime("%d/%m/%Y  %H:%M")
        estado    = "CERRADA" if cerrada else "EN CURSO"

        self.resumen_texto = (
            f"Cuadrilla {cuadrilla}  [{estado}]\n"
            f"Cuadro: {cuadro}  |  Act: {actividad[:30]}\n"
            f"{cuadrillero.replace(chr(10),' ')}  |  {fecha}\n"
            f"Presentes: {presentes}/{total}  Fijos: {fijos}"
        )

        self.ids.lista_resumen.clear_widgets()

        items_ord = sorted(
            trabajadores.items(),
            key=lambda x: (0 if x[1].get('tipo_trabajador') == 'FIJO' else 1)
        )

        for cred, info in items_ord:
            validado    = info.get('validado', False)
            nombre      = info.get('nombre', '').replace('\n', ' ')
            periodos    = info.get('periodos', [])
            es_fijo     = info.get('tipo_trabajador', '') == 'FIJO'
            puesto_desc = info.get('puesto_fijo_desc', '')

            per_txt = "  ".join([
                f"{p.get('tipo','').replace('_',' ')[:4].upper()} {p.get('hora','')}"
                for p in periodos
            ]) or (
                'FIJO AUTO' if es_fijo and validado
                else ('PRESENTE' if validado else 'AUSENTE')
            )

            if es_fijo:
                icono_n = "briefcase-check"
                icono_c = (0.18, 0.29, 0.55, 1)
                sec_txt = puesto_desc[:30]
            else:
                icono_n = "check" if validado else "close"
                icono_c = (0.18, 0.42, 0.18, 1) if validado else (0.72, 0.10, 0.10, 1)
                sec_txt = per_txt

            icono = IconLeftWidget(
                icon=icono_n,
                theme_text_color="Custom",
                icon_color=icono_c
            )
            item = TwoLineIconListItem(
                text=f"{'[F] ' if es_fijo else ''}Cred. {cred}  —  {nombre}",
                secondary_text=sec_txt,
            )
            item.add_widget(icono)
            self.ids.lista_resumen.add_widget(item)

    def _payload_actual(self):
        app = MDApp.get_running_app()
        return {
            "tipo":            "LISTA_CUADRILLA",
            "fecha":           datetime.datetime.now().strftime("%Y-%m-%d"),
            "hora_reporte":    datetime.datetime.now().strftime("%H:%M:%S"),
            "cuadrilla":       app.num_cuadrilla,
            "cuadrillero":     app.nombre_cuadrillero,
            "cuadro":          app.cuadro_trabajo,
            "actividad":       app.actividad_trabajo,
            "jornada_cerrada": app.jornada_cerrada,
            "trabajadores":    app.trabajadores_detectados
        }

    def guardar_avance(self):
        app     = MDApp.get_running_app()
        payload = self._payload_actual()
        payload["tipo_reporte"] = "AVANCE"
        guardar_lista(payload)
        Snackbar(text="Avance guardado").open()
        app.root.current = 'asistencia'

    def cerrar_jornada(self):
        app   = MDApp.get_running_app()
        ahora = datetime.datetime.now().strftime("%H:%M:%S")

        for cred in app.trabajadores_detectados:
            if app.trabajadores_detectados[cred].get('validado'):
                app.trabajadores_detectados[cred].setdefault('periodos', []).append({
                    "tipo": PERIODO_SALIDA, "hora": ahora,
                    "cuadro": app.cuadro_trabajo,
                    "actividad": app.actividad_trabajo
                })

        payload = self._payload_actual()
        payload["tipo_reporte"] = "FINAL"
        payload["hora_cierre"]  = ahora
        guardar_lista(payload)

        app.jornada_cerrada = True
        app.iniciar_anuncio_apuntador()
        app._escucha_activa = False

        pa = app.root.get_screen('asistencia')
        pa.texto_estado_jornada = f"JORNADA CERRADA  {ahora}"
        pa.color_estado_jornada = [0.65, 0.08, 0.08, 1]
        pa.estado_escucha       = "Cerrado"
        pa.color_estado_escucha = [0.65, 0.08, 0.08, 1]

        app.root.current = 'asistencia'
        Snackbar(text="Jornada cerrada. Emitiendo al apuntador.").open()


class CuadrilleroAgriCactusApp(MDApp):
    nombre_cuadrillero      = ""
    num_cuadrilla           = ""
    cuadro_trabajo          = ""
    actividad_trabajo       = ""
    trabajadores_detectados = {}
    _escucha_activa         = False
    _anuncio_activo         = False
    jornada_cerrada         = False
    _multicast_lock         = None
    _lock_intentado         = False

    def build(self):
        self.theme_cls.theme_style     = "Light"
        self.theme_cls.primary_palette = "Green"
        controlador = Builder.load_string(KV)
        Clock.schedule_once(self._restaurar_sesion, 0.5)
        self._adquirir_multicast_lock()
        return controlador

    def _restaurar_sesion(self, dt):
        datos = cargar_datos()
        if not datos:
            return
        pc = self.root.get_screen('credencial')
        pc.nombre_cuadrillero = datos.get("nombre", "")
        pc.nss                = datos.get("nss", "")
        pc.num_credencial     = datos.get("credencial", "")
        pc.num_cuadrilla      = datos.get("cuadrilla", "")
        pc.ruta_foto          = datos.get("foto", "")
        pc.fecha_ingreso      = datos.get("fecha_ingreso", "")
        self.num_cuadrilla      = datos.get("cuadrilla", "")
        self.nombre_cuadrillero = datos.get("nombre", "")
        self.root.current = 'credencial'

    # ── Fix de deteccion: en muchos dispositivos Android, WiFi descarta ───────
    # paquetes UDP broadcast entrantes salvo que se pida un "multicast lock".
    # Enviar (el Trabajador) funciona sin esto; RECIBIR (el Cuadrillero) es
    # lo que fallaba en silencio. Esto es lo que corrige "no detecta".
    def _adquirir_multicast_lock(self):
        if self._lock_intentado:
            return
        self._lock_intentado = True
        if platform != 'android':
            return
        try:
            from jnius import autoclass, cast
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Context        = autoclass('android.content.Context')
            activity       = PythonActivity.mActivity
            wifi_manager   = activity.getSystemService(Context.WIFI_SERVICE)
            wifi_manager   = cast('android.net.wifi.WifiManager', wifi_manager)
            self._multicast_lock = wifi_manager.createMulticastLock("agricactus_cuadrillero")
            self._multicast_lock.setReferenceCounted(True)
            self._multicast_lock.acquire()
            print("[WIFI] Multicast lock adquirido correctamente.")
        except Exception as e:
            print(f"[WIFI] No se pudo adquirir multicast lock: {e}")

    @staticmethod
    def _mismo_cuadrilla(a, b):
        a, b = str(a).strip(), str(b).strip()
        if a == b:
            return True
        try:
            return int(a) == int(b)
        except ValueError:
            return False

    def iniciar_escucha_trabajadores(self):
        if self._escucha_activa:
            return
        self._escucha_activa = True
        self._adquirir_multicast_lock()

        pa = self.root.get_screen('asistencia')
        pa.estado_escucha       = "Activo"
        pa.color_estado_escucha = [0.18, 0.42, 0.18, 1]

        def _escuchar():
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    sock.bind(('', PUERTO_ANUNCIO))
                    sock.settimeout(2.0)

                    while self._escucha_activa:
                        try:
                            datos_raw, addr = sock.recvfrom(1024)
                            msg    = datos_raw.decode('utf-8').strip()
                            partes = msg.split(':')

                            if len(partes) >= 4 and partes[0] == 'PRESENTE':
                                cred         = partes[1]
                                cuad         = partes[2]
                                nombre       = partes[3]
                                lat          = partes[4] if len(partes) > 4 else "0"
                                lon          = partes[5] if len(partes) > 5 else "0"
                                conf         = int(partes[6]) if len(partes) > 6 else 0
                                tipo_trab    = partes[7] if len(partes) > 7 else "JORNALERO"
                                puesto_clave = partes[8] if len(partes) > 8 else ""
                                puesto_desc  = partes[9] if len(partes) > 9 else ""

                                if not self._mismo_cuadrilla(cuad, self.num_cuadrilla):
                                    continue

                                ahora   = datetime.datetime.now().strftime("%H:%M:%S")
                                ip      = addr[0]
                                gps_txt = f"{lat},{lon}" if lat != "0" else ""

                                if cred not in self.trabajadores_detectados:
                                    self.trabajadores_detectados[cred] = {
                                        "nombre":            nombre,
                                        "hora_deteccion":    ahora,
                                        "validado":          False,
                                        "ip":                ip,
                                        "gps":               gps_txt,
                                        "confirmaciones":    conf,
                                        "tipo_trabajador":   tipo_trab,
                                        "puesto_fijo_clave": puesto_clave,
                                        "puesto_fijo_desc":  puesto_desc,
                                        "periodos":          []
                                    }
                                    if tipo_trab == 'FIJO':
                                        self.trabajadores_detectados[cred]['validado'] = True
                                        self.trabajadores_detectados[cred]['periodos'].append({
                                            "tipo":      "entrada",
                                            "hora":      ahora,
                                            "cuadro":    "",
                                            "actividad": puesto_desc
                                        })
                                else:
                                    self.trabajadores_detectados[cred].update({
                                        "ip":             ip,
                                        "nombre":         nombre,
                                        "gps":            gps_txt,
                                        "confirmaciones": conf
                                    })

                                Clock.schedule_once(lambda dt: self._actualizar_ui(), 0)

                        except socket.timeout:
                            continue
                        except Exception as e:
                            print(f"[WIFI] Error: {e}")

            except Exception as e:
                print(f"[WIFI] Error servidor: {e}")
            finally:
                self._escucha_activa = False

        threading.Thread(target=_escuchar, daemon=True).start()

    def _actualizar_ui(self):
        pa = self.root.get_screen('asistencia')
        if self.root.current == 'asistencia':
            pa.actualizar_lista_ui(self.trabajadores_detectados)

    def enviar_validacion(self, credencial, tipo=PERIODO_ENTRADA,
                           cuadro="", actividad=""):
        info = self.trabajadores_detectados.get(credencial, {})
        ip   = info.get('ip')
        if not ip:
            return

        fecha         = datetime.datetime.now().strftime("%Y-%m-%d")
        cuadro_enc    = cuadro.replace(':', '-')
        actividad_enc = actividad.replace(':', '-')[:20]
        mensaje = (
            f"VALIDAR:{credencial}:{self.num_cuadrilla}:{fecha}:{tipo}"
            f":{cuadro_enc}:{actividad_enc}"
        )

        def _enviar():
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.settimeout(3.0)
                    sock.sendto(mensaje.encode('utf-8'), (ip, PUERTO_VALIDACION))
                    try:
                        resp_raw, _ = sock.recvfrom(256)
                        resp = resp_raw.decode('utf-8').strip()
                        if resp.startswith(f"OK:{credencial}"):
                            Clock.schedule_once(
                                lambda dt: self._confirmar_periodo(
                                    credencial, tipo, cuadro, actividad
                                ), 0
                            )
                    except socket.timeout:
                        Clock.schedule_once(
                            lambda dt: self._confirmar_periodo(
                                credencial, tipo, cuadro, actividad
                            ), 0
                        )
            except Exception as e:
                print(f"[WIFI] Error validacion: {e}")

        threading.Thread(target=_enviar, daemon=True).start()

    def _confirmar_periodo(self, credencial, tipo, cuadro, actividad):
        if credencial not in self.trabajadores_detectados:
            return
        ahora = datetime.datetime.now().strftime("%H:%M:%S")
        info  = self.trabajadores_detectados[credencial]
        if tipo == PERIODO_ENTRADA:
            info['validado']        = True
            info['hora_validacion'] = ahora
        info.setdefault('periodos', []).append({
            "tipo": tipo, "hora": ahora,
            "cuadro": cuadro, "actividad": actividad
        })
        self._actualizar_ui()

    def iniciar_anuncio_apuntador(self):
        if self._anuncio_activo:
            return
        self._anuncio_activo = True

        def _anunciar():
            while self._anuncio_activo:
                try:
                    nombre_limpio = str(self.nombre_cuadrillero).replace(':', ' ').replace('\n', ' ')
                    msg = f"CUADRILLERO:{self.num_cuadrilla}:{nombre_limpio}"
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                        sock.sendto(msg.encode('utf-8'), ('255.255.255.255', PUERTO_ANUNCIO_CU))
                except Exception as e:
                    print(f"[WIFI] Error anuncio: {e}")
                time.sleep(INTERVALO_ANUNCIO)

        threading.Thread(target=_anunciar, daemon=True).start()

    def iniciar_respuesta_apuntador(self):
        self._adquirir_multicast_lock()

        def _escuchar():
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.bind(('', PUERTO_CUADRILLERO))
                    sock.settimeout(2.0)
                    while True:
                        try:
                            datos_raw, addr = sock.recvfrom(1024)
                            msg = datos_raw.decode('utf-8').strip()
                            if msg.startswith('PEDIR_LISTA:'):
                                Clock.schedule_once(
                                    lambda dt, a=addr, s=sock:
                                    self._enviar_lista_apuntador(s, a), 0
                                )
                        except socket.timeout:
                            continue
                        except Exception as e:
                            print(f"[WIFI] Error: {e}")
            except Exception as e:
                print(f"[WIFI] Error apuntador: {e}")

        threading.Thread(target=_escuchar, daemon=True).start()

    def _enviar_lista_apuntador(self, sock, addr):
        payload = {
            "tipo":            "LISTA_CUADRILLA",
            "fecha":           datetime.datetime.now().strftime("%Y-%m-%d"),
            "hora_reporte":    datetime.datetime.now().strftime("%H:%M:%S"),
            "cuadrilla":       self.num_cuadrilla,
            "cuadrillero":     self.nombre_cuadrillero,
            "cuadro":          self.cuadro_trabajo,
            "actividad":       self.actividad_trabajo,
            "jornada_cerrada": self.jornada_cerrada,
            "tipo_reporte":    "FINAL" if self.jornada_cerrada else "AVANCE",
            "trabajadores":    self.trabajadores_detectados
        }
        try:
            datos = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            sock.sendto(datos, (addr[0], PUERTO_RECEPCION))
            Snackbar(text="Lista enviada al apuntador").open()
        except Exception as e:
            print(f"[WIFI] Error: {e}")

    # ── Consulta de datos de empleado (registro -> laptop servidor RH) ───────
    def buscar_empleado_red(self, credencial, callback_ok, callback_error):
        """
        Busca los datos de un empleado por credencial en el servidor local
        (empleados_server.py corriendo en una laptop en el mismo WiFi).
        """
        credencial = str(credencial).strip()

        def _worker():
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    sock.settimeout(TIMEOUT_CONSULTA_EMP)
                    mensaje = f"CONSULTA_EMP|{credencial}".encode('utf-8')

                    for _ in range(REINTENTOS_CONSULTA_EMP):
                        try:
                            sock.sendto(mensaje, ('255.255.255.255', PUERTO_CONSULTA_EMP))
                            datos_raw, addr = sock.recvfrom(4096)
                            msg    = datos_raw.decode('utf-8').strip()
                            partes = msg.split('|')

                            if partes[0] == 'EMP_OK' and len(partes) >= 2 and partes[1] == credencial:
                                # EMP_OK|credencial|nombre|nss|cuadrilla|puesto_clave|puesto_desc
                                resultado = {
                                    "nombre":       partes[2] if len(partes) > 2 else "",
                                    "nss":          partes[3] if len(partes) > 3 else "",
                                    "cuadrilla":    partes[4] if len(partes) > 4 else "",
                                    "puesto_clave": partes[5] if len(partes) > 5 else "",
                                    "puesto_desc":  partes[6] if len(partes) > 6 else "",
                                }
                                Clock.schedule_once(lambda dt: callback_ok(resultado), 0)
                                return

                            if partes[0] == 'EMP_NOTFOUND' and len(partes) >= 2 and partes[1] == credencial:
                                Clock.schedule_once(
                                    lambda dt: callback_error(
                                        f"No existe ningun empleado con credencial {credencial}"
                                    ), 0
                                )
                                return
                        except socket.timeout:
                            continue

                    Clock.schedule_once(
                        lambda dt: callback_error(
                            "Sin respuesta del servidor. Verifica que la laptop "
                            "este encendida y conectada al mismo WiFi."
                        ), 0
                    )
            except Exception as e:
                Clock.schedule_once(lambda dt, err=str(e): callback_error(f"Error de red: {err}"), 0)

        threading.Thread(target=_worker, daemon=True).start()

    def on_stop(self):
        self._escucha_activa = False
        self._anuncio_activo = False
        if self._multicast_lock is not None:
            try:
                self._multicast_lock.release()
            except Exception:
                pass


if __name__ == '__main__':
    CuadrilleroAgriCactusApp().run()

