import flet as ft
import datetime
import json
import os
import socket
import threading
import time
import traceback
import base64

try:
    import qrcode
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
ARCHIVO_DATOS       = "empleado_data.json"
PUERTO_ANUNCIO      = 45678
PUERTO_VALIDACION   = 45679
PUERTO_APUNTADOR    = 45683
PUERTO_CONSULTA_EMP = 45690
TIMEOUT_CONSULTA_EMP = 3.0
REINTENTOS_CONSULTA_EMP = 3
INTERVALO_SIN_CONF  = 10
INTERVALO_CON_CONF  = 1800
MAX_FALTAS          = 3
DIAS_LABORALES      = {0, 1, 2, 3, 4}
TOLERANCIA_HORAS    = 2
DIAS_GRACIA         = 3
MAX_CONFIRMACIONES  = 2
PIN_RH              = "RH2024"

# =============================================================================
#  COLORES
# =============================================================================
VERDE_OSCURO    = "#2E4A1F"
DORADO          = "#F5A624"
VERDE_MEDIO     = "#2E6B2E"
VERDE_CLARO_BG  = "#F0F5F0"
CREMA_BG        = "#F5F5F0"
ROJO            = "#A61414"
ROJO_OSCURO     = "#801313"
FONDO_INACTIVA  = "#1A0F0F"
CARD_INACTIVA   = "#2E1F1F"
DIVIDER_INACT   = "#593333"

# =============================================================================
#  PERSISTENCIA  (idéntico al original)
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

def obtener_cuadrilla_efectiva(datos: dict) -> str:
    if datos.get("cuadrilla_dia_fecha") == datetime.date.today().isoformat():
        return datos.get("cuadrilla_dia") or datos.get("cuadrilla", "")
    return datos.get("cuadrilla", "")

# =============================================================================
#  LOGICA DE FALTAS  (idéntico al original)
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

# =============================================================================
#  QR  (adaptado para Flet – devuelve base64 en vez de Kivy texture)
# =============================================================================
def generar_qr_base64(texto: str):
    if not QR_DISPONIBLE:
        return None
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=6, border=2,
        )
        qr.add_data(texto)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf, format='PNG')
        return base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        print(f"[QR] Error generando QR: {e}")
        return None

# =============================================================================
#  CRASH LOG
# =============================================================================
def escribir_crash(exc):
    try:
        with open('crash_log.txt', 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*60}\n{datetime.datetime.now().isoformat()}\n")
            f.write(traceback.format_exc())
    except Exception:
        pass


# =============================================================================
#  APLICACION PRINCIPAL
# =============================================================================
class AgriCactusApp:

    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "AgriCactus"
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.padding = 0
        self.page.bgcolor = CREMA_BG
        self.pantalla_actual = "registro"

        # ── Estado ──
        self._anuncio_activo        = False
        self._validacion_activa     = False
        self._autovalidacion_activa = False
        self._lat  = 0.0
        self._lon  = 0.0
        self._proximo_anuncio    = None
        self._confirmaciones_hoy = 0
        self._ruta_foto          = ""
        self._puesto_clave_reg   = ""
        self._puesto_desc_reg    = ""
        self._pin_puesto_ok      = False
        self._tipo_bloqueo       = "falta"
        self._running            = True
        self._estado_parpadeo    = False

        # ── File picker (en 0.82 es un Service, va en page.services) ──
        self.file_picker = ft.FilePicker()
        self.page.services.append(self.file_picker)

        # ── Construir UI ──
        self._build_all()
        self.page.add(self.contenedor)

        # ── Restaurar sesión ──
        self._restaurar_sesion()
        self.page.update()

        # ── Tareas periódicas ──
        self._iniciar_tareas()

    # ─────────────────────────────────────────────────────────────────────────
    #  HELPERS
    # ─────────────────────────────────────────────────────────────────────────
    def snack(self, msg: str):
        try:
            sb = ft.SnackBar(content=ft.Text(msg), duration=2500, open=True)
            self.page.show_dialog(sb)
        except Exception:
            pass

    def ir_a(self, nombre: str):
        vistas = {
            "registro":    self.vista_registro,
            "activa":      self.vista_activa,
            "inactiva":    self.vista_inactiva,
            "puesto_fijo": self.vista_puesto_fijo,
        }
        self.pantalla_actual = nombre
        self.contenedor.content = vistas.get(nombre, self.vista_registro)
        if nombre == "puesto_fijo":
            self._on_enter_puesto_fijo()
        try:
            self.page.update()
        except Exception:
            pass

    def _header(self, titulo: str, bgcolor=VERDE_OSCURO):
        return ft.Container(
            bgcolor=bgcolor,
            padding=ft.Padding.symmetric(horizontal=12, vertical=10),
            content=ft.Row([
                ft.Image(
                    src="logo_agricactus.png",
                    width=110, height=45,
                    fit='contain',
                    error_content=ft.Text("AgriCactus", color="white",
                                          weight=ft.FontWeight.BOLD),
                ),
                ft.Text(
                    titulo, color="white", size=17,
                    weight=ft.FontWeight.BOLD,
                    expand=True, text_align=ft.TextAlign.CENTER,
                ),
            ]),
        )

    def _divider_dorado(self):
        return ft.Container(height=4, bgcolor=DORADO)

    # ─────────────────────────────────────────────────────────────────────────
    #  CONSTRUIR UI
    # ─────────────────────────────────────────────────────────────────────────
    def _build_all(self):
        self._build_registro()
        self._build_activa()
        self._build_inactiva()
        self._build_puesto_fijo()
        self.contenedor = ft.Container(
            expand=True,
            content=self.vista_registro,
        )

    # ── REGISTRO ─────────────────────────────────────────────────────────────
    def _build_registro(self):
        self.inp_nombre = ft.TextField(
            label="Nombre Completo",
            helper="Se convertirá a MAYÚSCULAS",
            focused_border_color=VERDE_OSCURO,
            cursor_color=VERDE_OSCURO,
        )
        self.inp_nss = ft.TextField(
            label="Número de Seguro Social (NSS)",
            max_length=11,
            input_filter=ft.NumbersOnlyInputFilter(),
            focused_border_color=VERDE_OSCURO,
            cursor_color=VERDE_OSCURO,
        )
        self.inp_credencial = ft.TextField(
            label="No. de Credencial / Empleado",
            input_filter=ft.NumbersOnlyInputFilter(),
            focused_border_color=VERDE_OSCURO,
            cursor_color=VERDE_OSCURO,
            expand=True,
            on_submit=lambda e: self._buscar_empleado(e),
        )
        self.lbl_busqueda = ft.Text("", size=12, color=ft.Colors.GREY)
        self.inp_cuadrilla = ft.TextField(
            label="Número de Cuadrilla",
            input_filter=ft.NumbersOnlyInputFilter(),
            focused_border_color=VERDE_OSCURO,
            cursor_color=VERDE_OSCURO,
        )
        self.inp_hora = ft.TextField(
            label="Hora de entrada (ej: 07:00)",
            helper="Formato 24h",
            focused_border_color=VERDE_OSCURO,
            cursor_color=VERDE_OSCURO,
        )
        self.lbl_foto = ft.Text(
            "Sin foto seleccionada", size=12,
            color=ft.Colors.GREY, text_align=ft.TextAlign.CENTER,
        )

        self.vista_registro = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=0,
            controls=[
                self._header("REGISTRO DE EMPLEADO"),
                self._divider_dorado(),
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=16, vertical=14),
                    content=ft.Column(spacing=10, controls=[
                        self.inp_nombre,
                        self.inp_nss,
                        ft.Row([
                            self.inp_credencial,
                            ft.OutlinedButton(
                                "BUSCAR", icon=ft.Icons.SEARCH,
                                style=ft.ButtonStyle(color=VERDE_OSCURO,
                                    side=ft.BorderSide(1, VERDE_OSCURO)),
                                on_click=self._buscar_empleado,
                            ),
                        ], spacing=8),
                        self.lbl_busqueda,
                        self.inp_cuadrilla,
                        self.inp_hora,
                        ft.Row([
                            ft.OutlinedButton(
                                "CÁMARA", icon=ft.Icons.CAMERA_ALT,
                                expand=True,
                                style=ft.ButtonStyle(color=VERDE_OSCURO,
                                    side=ft.BorderSide(1, VERDE_OSCURO)),
                                on_click=self._tomar_foto,
                            ),
                            ft.OutlinedButton(
                                "GALERÍA", icon=ft.Icons.IMAGE,
                                expand=True,
                                style=ft.ButtonStyle(color=VERDE_OSCURO,
                                    side=ft.BorderSide(1, VERDE_OSCURO)),
                                on_click=self._abrir_galeria,
                            ),
                        ], spacing=8),
                        self.lbl_foto,
                        ft.Container(height=6),
                        ft.Button(
                            "GENERAR CREDENCIAL DIGITAL",
                            bgcolor=VERDE_OSCURO, color="white",
                            width=9999, height=48,
                            elevation=4,
                            on_click=self._guardar_registro,
                        ),
                    ]),
                ),
            ],
        )

    # ── ACTIVA (credencial) ──────────────────────────────────────────────────
    def _build_activa(self):
        self.lbl_vigencia = ft.Text(
            "Sin faltas consecutivas", size=11,
            color="#C7EBC7",
        )
        self.img_foto = ft.Image(
            src="", width=85, height=105,
            fit='cover',
            error_content=ft.Container(
                width=85, height=105, bgcolor=ft.Colors.GREY_300,
                alignment=ft.Alignment.CENTER,
                content=ft.Icon(ft.Icons.PERSON, size=40, color=ft.Colors.GREY_500),
            ),
        )
        self.lbl_nombre = ft.Text(
            "", size=17, weight=ft.FontWeight.BOLD,
            color="#1F3814",
        )
        self.lbl_ingreso = ft.Text("Ingreso: ", size=11, color=ft.Colors.GREY_600)
        self.lbl_cuadrilla = ft.Text(
            "Cuadrilla: ", size=14,
            weight=ft.FontWeight.BOLD, color=VERDE_MEDIO,
        )
        self.lbl_nss = ft.Text("NSS: ", size=11, color=ft.Colors.GREY_600)

        self.lbl_puesto_badge = ft.Text(
            "Sin puesto fijo configurado",
            size=12, weight=ft.FontWeight.BOLD,
            color="white", text_align=ft.TextAlign.CENTER,
        )
        self.cont_puesto_badge = ft.Container(
            bgcolor=ft.Colors.GREY,
            border_radius=6, padding=ft.Padding.symmetric(vertical=8, horizontal=12),
            content=self.lbl_puesto_badge,
            alignment=ft.Alignment.CENTER,
        )

        self.lbl_num_cred = ft.Text(
            "No. ", size=32, weight=ft.FontWeight.BOLD,
            color="#1F3814", text_align=ft.TextAlign.CENTER,
        )
        self.img_qr = ft.Image(
            src="", width=110, height=110,
            fit='contain', visible=False,
        )
        self.lbl_qr_error = ft.Text(
            "", size=11, color="#B33326",
            text_align=ft.TextAlign.CENTER,
        )

        self.lbl_turno = ft.Text(
            "Sin confirmar — emitiendo cada 10s",
            size=12, weight=ft.FontWeight.BOLD,
            color="white", text_align=ft.TextAlign.CENTER,
        )
        self.cont_turno = ft.Container(
            bgcolor=DORADO, border_radius=8,
            padding=ft.Padding.symmetric(vertical=10, horizontal=12),
            content=self.lbl_turno,
            alignment=ft.Alignment.CENTER,
        )

        self.icon_wifi = ft.Icon(
            ft.Icons.WIFI, size=18, color=DORADO,
        )
        self.lbl_estado_wifi = ft.Text(
            "Buscando cuadrillero...", size=12,
            color=ft.Colors.GREY_600,
        )
        self.lbl_gps = ft.Text(
            "GPS: sin señal", size=11,
            color=ft.Colors.GREY_500, text_align=ft.TextAlign.CENTER,
        )
        self.lbl_prox_anuncio = ft.Text(
            "Emitiendo cada 10s...", size=11,
            color=VERDE_MEDIO, text_align=ft.TextAlign.CENTER,
        )

        card_content = ft.Column(
            spacing=0, expand=True,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                # Header
                ft.Container(
                    bgcolor=VERDE_OSCURO,
                    padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                    border_radius=ft.BorderRadius.only(top_left=14, top_right=14),
                    content=ft.Row([
                        ft.Image(
                            src="logo_agricactus.png",
                            width=100, height=40, fit='contain',
                            error_content=ft.Text("AgriCactus", color="white",
                                                   weight=ft.FontWeight.BOLD, size=12),
                        ),
                        ft.Column([
                            ft.Text("CREDENCIAL DIGITAL", size=11,
                                     weight=ft.FontWeight.BOLD, color=DORADO),
                            self.lbl_vigencia,
                        ], spacing=2, expand=True,
                           horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    ]),
                ),
                ft.Container(height=3, bgcolor=DORADO),

                # Datos empleado
                ft.Container(
                    padding=ft.Padding.only(left=12, right=12, top=10, bottom=6),
                    content=ft.Row([
                        ft.Container(
                            width=85, height=105, border_radius=10,
                            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                            content=self.img_foto,
                        ),
                        ft.Column([
                            self.lbl_nombre,
                            self.lbl_ingreso,
                            ft.Row([
                                self.lbl_cuadrilla,
                                ft.IconButton(
                                    icon=ft.Icons.EDIT, icon_size=18,
                                    icon_color=VERDE_OSCURO,
                                    tooltip="Cambiar cuadrilla del día",
                                    on_click=self._editar_cuadrilla_dia,
                                ),
                            ], spacing=0),
                            self.lbl_nss,
                        ], spacing=2, expand=True),
                    ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.START),
                ),

                # Badge puesto fijo
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=2),
                    content=self.cont_puesto_badge,
                ),
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=14),
                    content=ft.Container(height=3, bgcolor=DORADO),
                ),

                # Número de credencial
                ft.Container(
                    padding=ft.Padding.only(top=4, bottom=0),
                    alignment=ft.Alignment.CENTER,
                    content=self.lbl_num_cred,
                ),

                # QR
                ft.Container(
                    alignment=ft.Alignment.CENTER,
                    padding=ft.Padding.only(top=2, bottom=0),
                    content=self.img_qr,
                ),
                ft.Container(
                    alignment=ft.Alignment.CENTER,
                    content=self.lbl_qr_error,
                ),
                ft.Text(
                    "Acceso comedor", size=11,
                    color=ft.Colors.GREY_500,
                    text_align=ft.TextAlign.CENTER,
                    width=9999,
                ),
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=14, vertical=4),
                    content=ft.Divider(height=1, color=ft.Colors.GREY_300),
                ),

                # Turno
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=2),
                    content=self.cont_turno,
                ),

                # WiFi
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=14, vertical=4),
                    content=ft.Row([
                        self.icon_wifi,
                        self.lbl_estado_wifi,
                    ], spacing=6),
                ),
                ft.Container(
                    alignment=ft.Alignment.CENTER,
                    content=self.lbl_gps,
                ),
                ft.Container(
                    alignment=ft.Alignment.CENTER,
                    padding=ft.Padding.only(bottom=6),
                    content=self.lbl_prox_anuncio,
                ),

                # Botón puesto fijo
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=2),
                    content=ft.OutlinedButton(
                        "CONFIGURAR PUESTO",
                        icon=ft.Icons.WORK_OUTLINE,
                        width=9999,
                        style=ft.ButtonStyle(
                            color=VERDE_OSCURO,
                            side=ft.BorderSide(1, VERDE_OSCURO),
                        ),
                        on_click=lambda e: self.ir_a("puesto_fijo"),
                    ),
                ),

                # Footer
                ft.Container(
                    bgcolor=VERDE_OSCURO,
                    padding=ft.Padding.symmetric(vertical=6),
                    border_radius=ft.BorderRadius.only(bottom_left=14, bottom_right=14),
                    content=ft.Text(
                        "Blvd. Kino 309, Piso 6 - Hermosillo, Sonora",
                        size=10, color="#CCDDCC",
                        text_align=ft.TextAlign.CENTER, width=9999,
                    ),
                ),
            ],
        )

        self.vista_activa = ft.Row(
            expand=True, spacing=0,
            controls=[
                ft.Container(width=18, bgcolor=VERDE_OSCURO),
                ft.Container(
                    expand=True,
                    padding=ft.Padding.only(right=4, top=4, bottom=4),
                    content=ft.Card(
                        elevation=4,
                        content=ft.Container(
                            border_radius=16,
                            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                            content=card_content,
                        ),
                    ),
                ),
            ],
        )

    # ── INACTIVA (bloqueada) ─────────────────────────────────────────────────
    def _build_inactiva(self):
        self.lbl_motivo = ft.Text(
            "3 faltas consecutivas registradas.",
            size=14, color="#E6B3B3",
            text_align=ft.TextAlign.CENTER,
        )
        self.lbl_faltas_inact = ft.Text(
            "Presentate a Recursos Humanos",
            size=18, weight=ft.FontWeight.BOLD,
            color=DORADO, text_align=ft.TextAlign.CENTER,
        )

        self.btn_falta = ft.Button(
            "FALTAS", bgcolor="#801326", color="white",
            expand=True, on_click=lambda e: self._sel_tipo("falta"),
        )
        self.btn_incapacidad = ft.Button(
            "INCAPACIDAD", bgcolor=VERDE_MEDIO, color="white",
            expand=True, on_click=lambda e: self._sel_tipo("incapacidad"),
        )
        self.btn_vacaciones = ft.Button(
            "VACACIONES", bgcolor="#2E4A73", color="white",
            expand=True, on_click=lambda e: self._sel_tipo("vacaciones"),
        )
        self.inp_pin_desbloqueo = ft.TextField(
            label="PIN de RH", password=True,
            can_reveal_password=True, expand=True,
            focused_border_color=DORADO,
            cursor_color=DORADO,
            label_style=ft.TextStyle(color=DORADO),
            color="white",
            border_color="#593333",
        )

        self.vista_inactiva = ft.Container(
            expand=True, bgcolor=FONDO_INACTIVA,
            content=ft.Column(
                expand=True, scroll=ft.ScrollMode.AUTO, spacing=0,
                controls=[
                    # Header rojo
                    ft.Container(
                        bgcolor=ROJO, height=90,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Image(
                            src="logo_agricactus.png",
                            width=100, height=50, fit='contain',
                            opacity=0.35,
                            error_content=ft.Text("AgriCactus", color="white",
                                                   opacity=0.35),
                        ),
                    ),
                    ft.Container(height=16),
                    ft.Icon(ft.Icons.LOCK, size=55, color="#CC1F1F"),
                    ft.Container(height=8),
                    ft.Text(
                        "CREDENCIAL BLOQUEADA", size=22,
                        weight=ft.FontWeight.BOLD, color="white",
                        text_align=ft.TextAlign.CENTER, width=9999,
                    ),
                    ft.Container(height=8),
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=20),
                        content=self.lbl_motivo,
                    ),
                    ft.Container(height=8),
                    self.lbl_faltas_inact,
                    ft.Container(height=10),
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=30),
                        content=ft.Divider(height=2, color=DIVIDER_INACT),
                    ),
                    ft.Container(height=10),
                    # Card instrucciones
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=20),
                        content=ft.Card(
                            bgcolor=CARD_INACTIVA, elevation=2,
                            content=ft.Container(
                                padding=14,
                                content=ft.Column([
                                    ft.Icon(ft.Icons.BUSINESS, color=DORADO, size=22),
                                    ft.Text("Preséntate a Recursos Humanos",
                                             size=15, weight=ft.FontWeight.BOLD,
                                             color=DORADO, text_align=ft.TextAlign.CENTER,
                                             width=9999),
                                    ft.Text("RH evaluará tus faltas e incapacidades\ny desbloqueará tu credencial si procede.",
                                             size=11, color="#B88E8E",
                                             text_align=ft.TextAlign.CENTER, width=9999),
                                ], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                            ),
                        ),
                    ),
                    ft.Container(height=10),
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=30),
                        content=ft.Divider(height=2, color=DIVIDER_INACT),
                    ),
                    ft.Container(height=8),
                    ft.Text(
                        "Desbloqueo autorizado por RH:",
                        size=11, color=ft.Colors.GREY_500,
                        text_align=ft.TextAlign.CENTER, width=9999,
                    ),
                    ft.Container(height=6),
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=20),
                        content=ft.Row([
                            self.btn_falta, self.btn_incapacidad, self.btn_vacaciones,
                        ], spacing=6),
                    ),
                    ft.Container(height=10),
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=20),
                        content=ft.Row([
                            self.inp_pin_desbloqueo,
                            ft.Button(
                                "APLICAR", bgcolor=DORADO, color="#1F3814",
                                height=48, elevation=4,
                                on_click=self._intentar_reactivacion,
                            ),
                        ], spacing=8),
                    ),
                    ft.Container(height=20),
                ],
            ),
        )

    # ── PUESTO FIJO ──────────────────────────────────────────────────────────
    def _build_puesto_fijo(self):
        self.lbl_puesto_actual = ft.Text(
            "Sin configurar", size=15,
            weight=ft.FontWeight.BOLD, color=VERDE_MEDIO,
            text_align=ft.TextAlign.CENTER, width=9999,
        )
        self.inp_pin_puesto = ft.TextField(
            label="PIN de RH para configurar",
            password=True, can_reveal_password=True,
            focused_border_color=VERDE_OSCURO, cursor_color=VERDE_OSCURO,
            expand=True,
        )
        self.btn_actualizar_red = ft.OutlinedButton(
            "ACTUALIZAR PUESTO DESDE RED (RH)",
            icon=ft.Icons.WIFI_PROTECTED_SETUP,
            width=9999, disabled=True,
            style=ft.ButtonStyle(color=VERDE_OSCURO,
                side=ft.BorderSide(1, VERDE_OSCURO)),
            on_click=self._actualizar_puesto_red,
        )
        self.lbl_estado_red = ft.Text(
            "", size=11, color=ft.Colors.GREY,
            text_align=ft.TextAlign.CENTER, width=9999,
        )
        self.inp_buscar_puesto = ft.TextField(
            label="Buscar puesto por nombre o clave...",
            focused_border_color=VERDE_OSCURO, cursor_color=VERDE_OSCURO,
            disabled=True,
            on_change=self._filtrar_puestos,
        )
        self.lista_puestos = ft.ListView(
            expand=True, spacing=2, padding=0,
        )

        self.vista_puesto_fijo = ft.Column(
            expand=True, spacing=0,
            controls=[
                self._header("CONFIGURAR PUESTO FIJO"),
                self._divider_dorado(),
                ft.Container(
                    padding=ft.Padding.all(14),
                    content=ft.Column(spacing=10, controls=[
                        # Puesto actual
                        ft.Card(
                            elevation=2,
                            content=ft.Container(
                                padding=14,
                                content=ft.Column([
                                    ft.Text("Puesto fijo actual:", size=12,
                                             color=ft.Colors.GREY_600,
                                             text_align=ft.TextAlign.CENTER, width=9999),
                                    self.lbl_puesto_actual,
                                ], spacing=6),
                            ),
                        ),
                        # PIN
                        ft.Card(
                            elevation=2,
                            content=ft.Container(
                                padding=10,
                                content=ft.Row([
                                    self.inp_pin_puesto,
                                    ft.Button(
                                        "VERIFICAR",
                                        bgcolor=VERDE_OSCURO, color="white",
                                        on_click=self._verificar_pin_puesto,
                                    ),
                                ], spacing=8),
                            ),
                        ),
                        self.btn_actualizar_red,
                        self.lbl_estado_red,
                        self.inp_buscar_puesto,
                    ]),
                ),
                # Lista puestos
                ft.Container(
                    expand=True,
                    padding=ft.Padding.symmetric(horizontal=14),
                    content=self.lista_puestos,
                ),
                # Botones inferiores
                ft.Container(
                    padding=ft.Padding.all(14),
                    content=ft.Row([
                        ft.Button(
                            "QUITAR PUESTO FIJO",
                            bgcolor="#A61414", color="white",
                            expand=True,
                            on_click=self._quitar_puesto,
                        ),
                        ft.OutlinedButton(
                            "CANCELAR", expand=True,
                            style=ft.ButtonStyle(color=VERDE_OSCURO,
                                side=ft.BorderSide(1, VERDE_OSCURO)),
                            on_click=lambda e: self.ir_a("activa"),
                        ),
                    ], spacing=8),
                ),
            ],
        )

    # ─────────────────────────────────────────────────────────────────────────
    #  LOGICA DE REGISTRO
    # ─────────────────────────────────────────────────────────────────────────
    def _tomar_foto(self, e):
        self._pick_imagen()

    def _abrir_galeria(self, e):
        self._pick_imagen()

    def _pick_imagen(self):
        def _worker():
            try:
                result = self.file_picker.pick_files(
                    dialog_title="Seleccionar foto",
                    file_type=ft.FilePickerFileType.IMAGE,
                )
                if result and len(result) > 0:
                    self._ruta_foto = result[0].path or ""
                    nombre = os.path.basename(self._ruta_foto) if self._ruta_foto else ""
                    self.lbl_foto.value = f"OK: {nombre}" if nombre else "Foto seleccionada"
                    self.lbl_foto.color = VERDE_MEDIO
                else:
                    self.lbl_foto.value = "Sin foto seleccionada"
                    self.lbl_foto.color = ft.Colors.GREY
                try:
                    self.page.update()
                except Exception:
                    pass
            except Exception as ex:
                self.lbl_foto.value = f"Error: {ex}"
                try:
                    self.page.update()
                except Exception:
                    pass
        threading.Thread(target=_worker, daemon=True).start()

    def _buscar_empleado(self, e):
        credencial = self.inp_credencial.value.strip() if self.inp_credencial.value else ""
        if not credencial:
            self.snack("Escribe primero el número de credencial")
            return
        self.lbl_busqueda.value = "Buscando en la red..."
        self.lbl_busqueda.color = ft.Colors.GREY
        self.page.update()

        self.buscar_empleado_red(
            credencial,
            callback_ok=self._reg_encontrado,
            callback_error=self._reg_no_encontrado,
        )

    def _reg_encontrado(self, datos: dict):
        self.inp_nombre.value    = datos.get("nombre", "")
        self.inp_nss.value       = datos.get("nss", "")
        self.inp_cuadrilla.value = datos.get("cuadrilla", "")
        self._puesto_clave_reg   = datos.get("puesto_clave", "")
        self._puesto_desc_reg    = datos.get("puesto_desc", "")
        self.lbl_busqueda.value  = f"✓ Encontrado: {datos.get('nombre', '')}"
        self.lbl_busqueda.color  = VERDE_MEDIO
        try:
            self.page.update()
        except Exception:
            pass
        self.snack("Datos del empleado cargados")

    def _reg_no_encontrado(self, msg: str):
        self.lbl_busqueda.value = msg
        self.lbl_busqueda.color = "#B33326"
        try:
            self.page.update()
        except Exception:
            pass
        self.snack(msg)

    def _guardar_registro(self, e):
        nombre     = (self.inp_nombre.value or "").strip().upper()
        nss        = (self.inp_nss.value or "").strip()
        credencial = (self.inp_credencial.value or "").strip()
        cuadrilla  = (self.inp_cuadrilla.value or "").strip()
        hora_txt   = (self.inp_hora.value or "").strip()

        errores = []
        if not nombre:     errores.append("nombre")
        if len(nss) < 10:  errores.append("NSS")
        if not credencial: errores.append("credencial")
        if not cuadrilla:  errores.append("cuadrilla")
        if not self._ruta_foto: errores.append("foto")

        hora_int = 7
        if hora_txt:
            try:
                hora_int = int(hora_txt.split(":")[0])
            except Exception:
                errores.append("hora HH:MM")

        if errores:
            self.snack(f"Falta: {', '.join(errores)}")
            return

        # Formato nombre
        palabras = nombre.split()
        if len(palabras) >= 3:
            nombre_fmt = f"{palabras[0]} {palabras[1]}\n{' '.join(palabras[2:])}"
        elif len(palabras) == 2:
            nombre_fmt = f"{palabras[0]}\n{palabras[1]}"
        else:
            nombre_fmt = nombre

        fecha_ingreso = datetime.date.today().strftime("%d/%m/%Y")

        # Actualizar UI activa
        self.lbl_nombre.value     = nombre_fmt
        self.lbl_nss.value        = f"NSS: {nss}"
        self.lbl_num_cred.value   = f"No. {credencial}"
        self.lbl_cuadrilla.value  = f"Cuadrilla: {cuadrilla}"
        self.lbl_ingreso.value    = f"Ingreso: {fecha_ingreso}"
        self.img_foto.src         = self._ruta_foto

        datos = cargar_datos()
        datos.update({
            "nombre":              nombre_fmt,
            "nss":                 nss,
            "credencial":          credencial,
            "cuadrilla":           cuadrilla,
            "foto":                self._ruta_foto,
            "fecha_ingreso":       fecha_ingreso,
            "hora_entrada":        hora_int,
            "fecha_inicio_conteo": datetime.date.today().isoformat(),
            "ultima_asistencia":   datetime.datetime.now().isoformat(),
            "confirmaciones_hoy":  0,
        })

        if self._puesto_clave_reg or self._puesto_desc_reg:
            clave = self._puesto_clave_reg
            desc  = self._puesto_desc_reg
            desc_completa = f"{clave} - {desc}" if clave and desc else (desc or clave)
            datos["puesto_fijo_clave"] = clave
            datos["puesto_fijo_desc"]  = desc_completa
            datos["es_puesto_fijo"]    = True

        guardar_datos(datos)

        self._confirmaciones_hoy = 0
        self.iniciar_anuncio_wifi(credencial, cuadrilla, nombre_fmt)
        self.iniciar_servidor_validacion(credencial, cuadrilla)
        self._cargar_qr(credencial)
        self.actualizar_badge_puesto()
        self.ir_a("activa")
        self.snack("Credencial generada")

    # ─────────────────────────────────────────────────────────────────────────
    #  LOGICA CUADRILLA DEL DIA
    # ─────────────────────────────────────────────────────────────────────────
    def _editar_cuadrilla_dia(self, e):
        campo_pin = ft.TextField(
            label="PIN de RH", password=True, can_reveal_password=True,
            focused_border_color=VERDE_OSCURO, cursor_color=VERDE_OSCURO,
        )
        campo_cuad = ft.TextField(
            label="Nueva cuadrilla",
            input_filter=ft.NumbersOnlyInputFilter(),
            focused_border_color=VERDE_OSCURO, cursor_color=VERDE_OSCURO,
        )

        dlg = ft.AlertDialog(
            title=ft.Text("Cambiar cuadrilla de hoy\n(requiere PIN de RH)", size=15),
            content=ft.Column([campo_pin, campo_cuad], spacing=10, tight=True),
            actions=[
                ft.TextButton("CANCELAR", on_click=lambda e: self.page.pop_dialog()),
                ft.Button(
                    "GUARDAR", bgcolor=VERDE_OSCURO, color="white",
                    on_click=lambda e: self._guardar_cuadrilla_dia(
                        dlg, campo_pin.value, campo_cuad.value
                    ),
                ),
            ],
        )
        self.page.show_dialog(dlg)

    def _guardar_cuadrilla_dia(self, dlg, pin, nueva):
        pin   = (pin or "").strip()
        nueva = (nueva or "").strip()
        if pin != PIN_RH:
            self.snack("PIN incorrecto")
            return
        if not nueva:
            self.snack("Escribe el número de cuadrilla")
            return
        datos = cargar_datos()
        datos["cuadrilla_dia"]       = nueva
        datos["cuadrilla_dia_fecha"] = datetime.date.today().isoformat()
        guardar_datos(datos)
        self.lbl_cuadrilla.value = f"Cuadrilla: {nueva}"
        self.page.pop_dialog()
        self.page.update()
        self.snack(f"Cuadrilla del día actualizada a {nueva}")

    # ─────────────────────────────────────────────────────────────────────────
    #  LOGICA QR
    # ─────────────────────────────────────────────────────────────────────────
    def _cargar_qr(self, credencial: str):
        if not credencial:
            return
        b64 = generar_qr_base64(credencial)
        if b64:
            self.img_qr.src        = f"data:image/png;base64,{b64}"
            self.img_qr.visible    = True
            self.lbl_qr_error.value = ""
        else:
            self.img_qr.visible     = False
            self.lbl_qr_error.value = "QR no disponible en este dispositivo"
        try:
            self.page.update()
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────────
    #  BADGE PUESTO FIJO
    # ─────────────────────────────────────────────────────────────────────────
    def actualizar_badge_puesto(self):
        datos   = cargar_datos()
        es_fijo = datos.get("es_puesto_fijo", False)
        desc    = datos.get("puesto_fijo_desc", "")
        if es_fijo and desc:
            self.lbl_puesto_badge.value    = f"PUESTO FIJO: {desc}"
            self.cont_puesto_badge.bgcolor = "#2E4A8C"
        else:
            self.lbl_puesto_badge.value    = "Sin puesto fijo — jornalero"
            self.cont_puesto_badge.bgcolor = ft.Colors.GREY
        try:
            self.page.update()
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────────
    #  LOGICA PUESTO FIJO
    # ─────────────────────────────────────────────────────────────────────────
    def _on_enter_puesto_fijo(self):
        self._pin_puesto_ok = False
        self.inp_pin_puesto.value = ""
        self.inp_buscar_puesto.disabled = True
        self.inp_buscar_puesto.value = ""
        self.btn_actualizar_red.disabled = True
        self.lbl_estado_red.value = ""
        self.lista_puestos.controls.clear()
        datos = cargar_datos()
        self.lbl_puesto_actual.value = datos.get("puesto_fijo_desc", "Sin configurar")

    def _verificar_pin_puesto(self, e):
        pin = (self.inp_pin_puesto.value or "").strip()
        self.inp_pin_puesto.value = ""
        if pin != PIN_RH:
            self.snack("PIN incorrecto")
            self.page.update()
            return
        self._pin_puesto_ok = True
        self.inp_buscar_puesto.disabled = False
        self.btn_actualizar_red.disabled = False
        self._poblar_lista_puestos("")
        self.page.update()
        self.snack("PIN correcto — selecciona el puesto")

    def _filtrar_puestos(self, e):
        if not self._pin_puesto_ok:
            return
        self._poblar_lista_puestos((e.data or "").strip().upper())
        self.page.update()

    def _poblar_lista_puestos(self, filtro: str):
        self.lista_puestos.controls.clear()
        resultados = [
            (c, d) for c, d in ACTIVIDADES_FIJAS
            if filtro in d.upper() or filtro in c
        ] if filtro else ACTIVIDADES_FIJAS

        for clave, desc in resultados:
            self.lista_puestos.controls.append(
                ft.ListTile(
                    title=ft.Text(f"{clave} - {desc}", size=13),
                    dense=True,
                    on_click=lambda e, c=clave, d=desc: self._seleccionar_puesto(c, d),
                )
            )

    def _seleccionar_puesto(self, clave, desc):
        if not self._pin_puesto_ok:
            return
        datos = cargar_datos()
        datos["puesto_fijo_clave"] = clave
        datos["puesto_fijo_desc"]  = f"{clave} - {desc}"
        datos["es_puesto_fijo"]    = True
        guardar_datos(datos)
        self.lbl_puesto_actual.value = f"{clave} - {desc}"
        self.actualizar_badge_puesto()
        self.snack(f"Puesto configurado: {desc}")

        def _volver():
            time.sleep(1.0)
            self.ir_a("activa")
        threading.Thread(target=_volver, daemon=True).start()

    def _quitar_puesto(self, e):
        if not self._pin_puesto_ok:
            self.snack("Verifica el PIN primero")
            return
        datos = cargar_datos()
        datos["puesto_fijo_clave"] = ""
        datos["puesto_fijo_desc"]  = ""
        datos["es_puesto_fijo"]    = False
        guardar_datos(datos)
        self.lbl_puesto_actual.value = "Sin configurar"
        self.actualizar_badge_puesto()
        self.snack("Puesto fijo eliminado")
        self.ir_a("activa")

    def _actualizar_puesto_red(self, e):
        if not self._pin_puesto_ok:
            self.snack("Verifica el PIN primero")
            return
        datos      = cargar_datos()
        credencial = datos.get("credencial", "")
        if not credencial:
            self.snack("No hay credencial registrada")
            return
        self.lbl_estado_red.value = "Buscando en la red..."
        self.lbl_estado_red.color = ft.Colors.GREY
        self.page.update()

        self.buscar_empleado_red(
            credencial,
            callback_ok=self._puesto_red_ok,
            callback_error=self._puesto_red_error,
        )

    def _puesto_red_ok(self, datos_emp: dict):
        clave = datos_emp.get("puesto_clave", "")
        desc  = datos_emp.get("puesto_desc", "")
        if not clave and not desc:
            self.lbl_estado_red.value = "RH no tiene puesto fijo para esta credencial"
            self.lbl_estado_red.color = "#B33326"
            try:
                self.page.update()
            except Exception:
                pass
            self.snack("Sin puesto fijo en RH para esta credencial")
            return
        desc_completa = f"{clave} - {desc}" if clave and desc else (desc or clave)
        datos = cargar_datos()
        datos["puesto_fijo_clave"] = clave
        datos["puesto_fijo_desc"]  = desc_completa
        datos["es_puesto_fijo"]    = True
        guardar_datos(datos)
        self.lbl_puesto_actual.value = desc_completa
        self.lbl_estado_red.value    = "✓ Puesto actualizado desde RH"
        self.lbl_estado_red.color    = VERDE_MEDIO
        self.actualizar_badge_puesto()
        try:
            self.page.update()
        except Exception:
            pass
        self.snack(f"Puesto actualizado: {desc_completa}")

    def _puesto_red_error(self, msg: str):
        self.lbl_estado_red.value = msg
        self.lbl_estado_red.color = "#B33326"
        try:
            self.page.update()
        except Exception:
            pass
        self.snack(msg)

    # ─────────────────────────────────────────────────────────────────────────
    #  LOGICA DE DESBLOQUEO (pantalla inactiva)
    # ─────────────────────────────────────────────────────────────────────────
    def _sel_tipo(self, tipo: str):
        self._tipo_bloqueo = tipo
        apagado = "#383838"
        colores = {
            "falta":       "#801326",
            "incapacidad": VERDE_MEDIO,
            "vacaciones":  "#2E4A73",
        }
        self.btn_falta.bgcolor       = apagado
        self.btn_incapacidad.bgcolor  = apagado
        self.btn_vacaciones.bgcolor   = apagado
        {
            "falta":       self.btn_falta,
            "incapacidad": self.btn_incapacidad,
            "vacaciones":  self.btn_vacaciones,
        }[tipo].bgcolor = colores[tipo]
        self.page.update()
        self.snack(f"Tipo: {tipo.upper()}")

    def _intentar_reactivacion(self, e):
        pin = (self.inp_pin_desbloqueo.value or "").strip()
        self.inp_pin_desbloqueo.value = ""
        if pin != PIN_RH:
            self.snack("PIN incorrecto.")
            self.page.update()
            return

        tipo      = self._tipo_bloqueo
        datos     = cargar_datos()
        historial = datos.get("historial", [])
        mes_hoy   = mes_actual_str()

        for i, entry in enumerate(historial):
            if entry.get("mes") == mes_hoy and entry.get("estatus") == "falta":
                historial[i]["estatus"]       = tipo
                historial[i]["autorizado_rh"] = True

        historial = agregar_dia_historial(historial, estatus="presente", turno="matutino")
        datos["historial"]           = historial
        datos["fecha_inicio_conteo"] = datetime.date.today().isoformat()
        datos["faltas_consecutivas"] = 0
        datos["confirmaciones_hoy"]  = 0
        guardar_datos(datos)

        faltas = calcular_faltas_consecutivas(historial)
        self._confirmaciones_hoy = 0
        self._actualizar_texto_turno()
        self.lbl_vigencia.value = self._texto_vigencia(faltas)

        cred = datos.get("credencial", "")
        cuad = datos.get("cuadrilla", "")
        nomb = datos.get("nombre", "")
        self._anuncio_activo = False
        self.iniciar_anuncio_wifi(cred, cuad, nomb)
        self.iniciar_servidor_validacion(cred, cuad)
        self._cargar_qr(cred)
        self.ir_a("activa")
        self.snack("Credencial desbloqueada.")

    # ─────────────────────────────────────────────────────────────────────────
    #  RED WIFI  (idéntico al original)
    # ─────────────────────────────────────────────────────────────────────────
    def iniciar_anuncio_wifi(self, credencial, cuadrilla, nombre):
        if self._anuncio_activo:
            return
        self._anuncio_activo = True

        def _anunciar():
            self._enviar_anuncio(credencial, cuadrilla, nombre)
            while self._anuncio_activo:
                intervalo = (
                    INTERVALO_SIN_CONF
                    if self._confirmaciones_hoy < MAX_CONFIRMACIONES
                    else INTERVALO_CON_CONF
                )
                self._proximo_anuncio = time.time() + intervalo
                time.sleep(intervalo)
                if self._anuncio_activo:
                    self._enviar_anuncio(credencial, cuadrilla, nombre)

        threading.Thread(target=_anunciar, daemon=True).start()

    def _enviar_anuncio(self, credencial, cuadrilla, nombre):
        try:
            datos            = cargar_datos()
            cuadrilla_actual = obtener_cuadrilla_efectiva(datos) or cuadrilla
            es_fijo       = datos.get("es_puesto_fijo", False)
            puesto_clave  = datos.get("puesto_fijo_clave", "")
            puesto_desc   = datos.get("puesto_fijo_desc", "").replace(':', '-')
            nombre_limpio = str(nombre).replace(':', ' ').replace('\n', ' ')
            tipo_trabajador = "FIJO" if es_fijo else "JORNALERO"
            mensaje = (
                f"PRESENTE:{credencial}:{cuadrilla_actual}:{nombre_limpio}"
                f":{self._lat:.6f}:{self._lon:.6f}"
                f":{self._confirmaciones_hoy}"
                f":{tipo_trabajador}:{puesto_clave}:{puesto_desc[:20]}"
            )
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.sendto(mensaje.encode('utf-8'), ('255.255.255.255', PUERTO_ANUNCIO))
        except Exception as e:
            print(f"[WIFI] Error anuncio: {e}")

    def detener_anuncio(self):
        self._anuncio_activo = False

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
                            msg    = datos_raw.decode('utf-8').strip()
                            partes = msg.split(':')
                            if (len(partes) >= 3
                                    and partes[0] == 'VALIDAR'
                                    and partes[1] == str(credencial)):
                                turno = partes[4] if len(partes) > 4 else "matutino"
                                sock.sendto(f"OK:{credencial}".encode(), addr)
                                self._registrar_asistencia(turno)
                        except socket.timeout:
                            continue
                        except Exception as e:
                            print(f"[WIFI] Error: {e}")
            except Exception as e:
                print(f"[WIFI] Error servidor: {e}")
            finally:
                self._validacion_activa = False

        threading.Thread(target=_escuchar, daemon=True).start()

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
                            msg    = datos_raw.decode('utf-8').strip()
                            partes = msg.split(':')
                            if (len(partes) >= 2
                                    and partes[0] == 'SCAN_FIJO'
                                    and partes[1] == str(credencial)):
                                sock.sendto(f"OK_FIJO:{credencial}".encode(), addr)
                                self._registrar_asistencia("matutino")
                        except socket.timeout:
                            continue
                        except Exception as e:
                            print(f"[WIFI] Error autovalidacion: {e}")
            except Exception as e:
                print(f"[WIFI] Error autovalidacion servidor: {e}")
            finally:
                self._autovalidacion_activa = False

        threading.Thread(target=_escuchar, daemon=True).start()

    def buscar_empleado_red(self, credencial, callback_ok, callback_error):
        credencial = str(credencial).strip()

        def _worker():
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    sock.settimeout(TIMEOUT_CONSULTA_EMP)
                    mensaje = f"CONSULTA_EMP|{credencial}".encode('utf-8')

                    for intento in range(REINTENTOS_CONSULTA_EMP):
                        try:
                            sock.sendto(mensaje, ('255.255.255.255', PUERTO_CONSULTA_EMP))
                            datos_raw, addr = sock.recvfrom(4096)
                            msg    = datos_raw.decode('utf-8').strip()
                            partes = msg.split('|')

                            if partes[0] == 'EMP_OK' and len(partes) >= 2 and partes[1] == credencial:
                                resultado = {
                                    "nombre":       partes[2] if len(partes) > 2 else "",
                                    "nss":          partes[3] if len(partes) > 3 else "",
                                    "cuadrilla":    partes[4] if len(partes) > 4 else "",
                                    "puesto_clave": partes[5] if len(partes) > 5 else "",
                                    "puesto_desc":  partes[6] if len(partes) > 6 else "",
                                }
                                callback_ok(resultado)
                                return

                            if partes[0] == 'EMP_NOTFOUND' and len(partes) >= 2 and partes[1] == credencial:
                                callback_error(
                                    f"No existe ningún empleado con credencial {credencial}"
                                )
                                return
                        except socket.timeout:
                            continue

                    callback_error(
                        "Sin respuesta del servidor. Verifica que la laptop "
                        "esté encendida y conectada al mismo WiFi."
                    )
            except Exception as e:
                callback_error(f"Error de red: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    # ─────────────────────────────────────────────────────────────────────────
    #  ASISTENCIA
    # ─────────────────────────────────────────────────────────────────────────
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

        turno_txt = "MATUTINO" if turno == "matutino" else "VESPERTINO"
        self.lbl_estado_wifi.value = f"✓ Turno {turno_txt}: {ahora.strftime('%H:%M')}"
        self.lbl_estado_wifi.color = VERDE_MEDIO
        self.lbl_vigencia.value    = self._texto_vigencia(faltas)
        self._actualizar_texto_turno()

        if self.pantalla_actual == "inactiva" and faltas < MAX_FALTAS:
            self.ir_a("activa")

        try:
            self.page.update()
        except Exception:
            pass
        self.snack(f"✓ Turno {turno_txt}: {ahora.strftime('%H:%M')}")

    def _texto_vigencia(self, faltas: int) -> str:
        if faltas == 0:
            return "Sin faltas consecutivas"
        if MAX_FALTAS - faltas == 1:
            return "⚠ 1 falta mas = bloqueo"
        return f"Faltas: {faltas}/{MAX_FALTAS}"

    def _actualizar_texto_turno(self):
        if self._confirmaciones_hoy == 0:
            self.lbl_turno.value  = "Sin confirmar — emitiendo cada 10s"
            self.cont_turno.bgcolor = DORADO
        elif self._confirmaciones_hoy == 1:
            self.lbl_turno.value  = "✓ Turno MATUTINO confirmado"
            self.cont_turno.bgcolor = VERDE_MEDIO
        else:
            self.lbl_turno.value  = "✓✓ Turno VESPERTINO confirmado"
            self.cont_turno.bgcolor = "#1A4D8C"

    # ─────────────────────────────────────────────────────────────────────────
    #  TAREAS PERIODICAS
    # ─────────────────────────────────────────────────────────────────────────
    def _iniciar_tareas(self):
        threading.Thread(target=self._loop_vigencia, daemon=True).start()
        threading.Thread(target=self._loop_parpadeo, daemon=True).start()
        threading.Thread(target=self._loop_anuncio_ui, daemon=True).start()

    def _loop_vigencia(self):
        while self._running:
            time.sleep(30)
            try:
                self._verificar_vigencia()
            except Exception as e:
                print(f"[VIGENCIA] Error: {e}")

    def _verificar_vigencia(self):
        datos     = cargar_datos()
        historial = datos.get("historial", [])
        hoy       = datetime.date.today()
        ahora     = datetime.datetime.now()
        gracia    = en_periodo_gracia(datos)

        if not gracia:
            hora_entrada = datos.get("hora_entrada", 7)
            hora_limite  = hora_entrada + TOLERANCIA_HORAS
            dias_ok = {
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
            if self.pantalla_actual != "inactiva":
                self.lbl_motivo.value      = f"{faltas} faltas.\nPreséntate a RH."
                self.lbl_faltas_inact.value = f"Faltas: {contar_faltas_mes(historial)}"
                self.ir_a("inactiva")
        else:
            if self.pantalla_actual == "activa":
                self.lbl_vigencia.value = self._texto_vigencia(faltas)
                try:
                    self.page.update()
                except Exception:
                    pass

    def _loop_parpadeo(self):
        while self._running:
            time.sleep(1)
            if self.pantalla_actual == "activa":
                self._estado_parpadeo = not self._estado_parpadeo
                self.icon_wifi.color = (
                    VERDE_OSCURO if self._estado_parpadeo
                    else "#F5A66666"
                )
                try:
                    self.page.update()
                except Exception:
                    pass

    def _loop_anuncio_ui(self):
        while self._running:
            time.sleep(15)
            if self.pantalla_actual != "activa":
                continue
            if self._confirmaciones_hoy == 0:
                self.lbl_prox_anuncio.value = "Emitiendo cada 10s"
            elif self._proximo_anuncio:
                mins = max(0, int((self._proximo_anuncio - time.time()) / 60))
                self.lbl_prox_anuncio.value = f"Próximo anuncio en: {mins} min"
            try:
                self.page.update()
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────────────────────
    #  GPS  (simplificado — Flet no tiene plyer.gps)
    # ─────────────────────────────────────────────────────────────────────────
    def _iniciar_gps(self):
        """
        GPS: en Flet móvil se puede integrar con paquetes nativos.
        Por ahora se mantiene la última ubicación guardada en JSON.
        """
        datos = cargar_datos()
        lat = datos.get("lat", 0.0)
        lon = datos.get("lon", 0.0)
        if lat and lon:
            self._lat = lat
            self._lon = lon
            self.lbl_gps.value = f"GPS: {self._lat:.4f}, {self._lon:.4f}"
        else:
            self.lbl_gps.value = "GPS: sin señal"

    # ─────────────────────────────────────────────────────────────────────────
    #  RESTAURAR SESION
    # ─────────────────────────────────────────────────────────────────────────
    def _restaurar_sesion(self):
        datos = cargar_datos()
        if not datos:
            return

        self.lbl_nombre.value    = datos.get("nombre", "")
        self.lbl_nss.value       = f"NSS: {datos.get('nss', '')}"
        self.lbl_num_cred.value  = f"No. {datos.get('credencial', '')}"
        self.lbl_cuadrilla.value = f"Cuadrilla: {obtener_cuadrilla_efectiva(datos)}"
        self.lbl_ingreso.value   = f"Ingreso: {datos.get('fecha_ingreso', '')}"
        self.img_foto.src        = datos.get("foto", "")

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
        self.lbl_vigencia.value = self._texto_vigencia(faltas)
        self._actualizar_texto_turno()
        self.actualizar_badge_puesto()

        if faltas >= MAX_FALTAS:
            self.lbl_motivo.value       = f"{faltas} faltas.\nPreséntate a RH."
            self.lbl_faltas_inact.value = f"Faltas del mes: {contar_faltas_mes(historial)}"
            self.ir_a("inactiva")
        else:
            cred = datos.get("credencial", "")
            cuad = datos.get("cuadrilla", "")
            nomb = datos.get("nombre", "")
            self.iniciar_anuncio_wifi(cred, cuad, nomb)
            self.iniciar_servidor_validacion(cred, cuad)
            self.iniciar_autovalidacion_apuntador(cred, cuad, nomb)
            self._iniciar_gps()
            self._cargar_qr(cred)
            self.ir_a("activa")


# =============================================================================
#  PUNTO DE ENTRADA
# =============================================================================
def main(page: ft.Page):
    page.title = "AgriCactus"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.bgcolor = CREMA_BG

    try:
        AgriCactusApp(page)
    except Exception as e:
        escribir_crash(e)
        raise

ft.run(main)
