import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client
import pandas as pd
import zxingcpp
import cv2
import numpy as np
from datetime import datetime
import time
import requests

# ==========================================
# 1. CONEXIÓN AL CEREBRO DE BASE DE DATOS
# ==========================================
URL_SUPABASE = "https://degzltrjrzqbahdonmmb.supabase.co"
KEY_SUPABASE = "sb_publishable_td5_vXX42LYc8PlTAbBgVg_-xCp-94r"
supabase = create_client(URL_SUPABASE, KEY_SUPABASE)

st.set_page_config(page_title="JORDAN POS SMART", layout="wide", page_icon="📱")

ERROR_ADMIN = "🚨 Ocurrió un error inesperado. Contactar al administrador: **Williams Luna - Celular: 95555555**"

# ==========================================
# 2. DISEÑO VISUAL Y ESTILOS (CSS)
# ==========================================
st.markdown("""
    <style>
    .stApp { background-color: #f1f5f9; }
    .main-header { font-size: 26px; font-weight: 800; color: #1e3a8a; text-align: center; padding: 15px; border-bottom: 4px solid #1e3a8a; margin-bottom: 20px; }
    .css-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 5px solid #2563eb; margin-bottom: 15px; }
    .ticket-termico { background: white; color: black; font-family: 'Courier New', monospace; padding: 15px; border: 1px dashed #333; width: 100%; max-width: 320px; margin: 0 auto; line-height: 1.2; font-size: 14px; }
    .stButton>button { border-radius: 6px; font-weight: bold; height: 3.5em; width: 100%; }
    .resumen-duplicado { background-color: #fff3cd; color: #856404; padding: 15px; border-radius: 8px; border: 1px solid #ffeeba; margin-bottom: 15px; }
    .info-caja { background-color: #e0f2fe; color: #0369a1; padding: 15px; border-radius: 8px; border: 1px solid #bae6fd; margin-bottom: 15px; font-weight: 500;}
    .metric-box { background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); text-align: center; border: 1px solid #e2e8f0;}
    .metric-title { font-size: 13px; color: #64748b; font-weight: 700; text-transform: uppercase; margin-bottom: 5px;}
    .metric-value { font-size: 22px; font-weight: 900; color: #0f172a;}
    .metric-green { color: #16a34a; }
    .metric-red { color: #dc2626; }
    .metric-orange { color: #ea580c; }
    .cierre-box { background-color: #fef2f2; border: 2px solid #fca5a5; padding: 20px; border-radius: 10px; margin-top: 20px;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 3. MEMORIA DEL SISTEMA Y ESTADO (SESSION)
# ==========================================
keys_to_init = {
    'empleado_id': None, 'empleado_nombre': "", 'empleado_rol': "", 'turno_id': None,
    'carrito': [], 'last_ticket_html': None,
    'iny_alm_cod': "", 'iny_dev_cod': "", 'iny_merma_cod': "",
    'cam_v_key': 0, 'cam_a_key': 0, 'cam_d_key': 0, 'cam_m_key': 0,
    'api_nombre_sugerido': ""
}
for key, value in keys_to_init.items():
    if key not in st.session_state: st.session_state[key] = value

# ==========================================
# 4. FUNCIONES DE APOYO Y MOTOR PRINCIPAL
# ==========================================
def scan_pos(image):
    if not image: return None
    try:
        file_bytes = np.asarray(bytearray(image.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, 1)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enh = clahe.apply(gray)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        scale_down = cv2.resize(gray, None, fx=0.6, fy=0.6, interpolation=cv2.INTER_AREA)
        scale_up = cv2.resize(gray, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
        
        variantes = [img, gray, enh, thresh, scale_down, scale_up]
        for var in variantes:
            for rot in [None, cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_90_COUNTERCLOCKWISE]:
                test_img = cv2.rotate(var, rot) if rot else var
                res = zxingcpp.read_barcodes(test_img)
                if res: return res[0].text
        return None
    except: return None

def load_data(table):
    try:
        res = supabase.table(table).select("*").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except: return pd.DataFrame()

def procesar_codigo_venta(code):
    exito = False
    try:
        prod_db = supabase.table("productos").select("*").eq("codigo_barras", code).execute()
        if prod_db.data:
            p = prod_db.data[0]
            if p['stock_actual'] > 0:
                exist = False
                for item in st.session_state.carrito:
                    if item['id'] == code: 
                        item['cant'] += 1; exist = True
                if not exist:
                    st.session_state.carrito.append({
                        'id': code, 'nombre': p['nombre'], 'precio': float(p['precio_lista']), 
                        'cant': 1, 'costo': float(p['costo_compra']), 'p_min': float(p['precio_minimo'])
                    })
                st.success(f"✅ Añadido: {p['nombre']}")
                exito = True
            else: st.error("❌ Sin stock disponible.")
        else: st.warning("⚠️ Producto no encontrado.")
    except: st.error(ERROR_ADMIN)
    return exito

@st.cache_data(show_spinner=False, ttl=60)
def fetch_upc_api(codigo):
    try:
        r = requests.get(f"https://api.upcitemdb.com/prod/trial/lookup?upc={codigo}", timeout=3)
        if r.status_code == 200 and r.json().get('items'):
            return r.json()['items'][0].get('title', '')
    except: pass
    return ""

# ==========================================
# 🛑 BLOQUE 1: PANTALLA DE LOGIN (AUTENTICACIÓN PIN)
# ==========================================
if not st.session_state.empleado_id:
    st.markdown('<div class="main-header">🔒 ACCESO AL SISTEMA POS</div>', unsafe_allow_html=True)
    col_log1, col_log2, col_log3 = st.columns([1, 1.5, 1])
    with col_log2:
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        st.write("### Identificación de Empleado")
        with st.form("login_pin_form"):
            user_pin = st.text_input("Ingresa tu PIN de Acceso", type="password")
            if st.form_submit_button("Ingresar", type="primary"):
                emp_db = supabase.table("empleados").select("*").eq("pin", user_pin).execute()
                if emp_db.data:
                    st.session_state.empleado_id = emp_db.data[0]['id']
                    st.session_state.empleado_nombre = emp_db.data[0]['nombre']
                    st.session_state.empleado_rol = emp_db.data[0]['rol']
                    st.success(f"Bienvenido, {emp_db.data[0]['nombre']}")
                    time.sleep(0.5); st.rerun()
                else:
                    st.error("❌ PIN Incorrecto.")
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ==========================================
# 🛑 BLOQUE 2: APERTURA DE TURNO (CAJA)
# ==========================================
if not st.session_state.turno_id:
    # Verificar si el empleado ya tiene un turno abierto en BD
    turno_abierto = supabase.table("turnos").select("*").eq("empleado_id", st.session_state.empleado_id).eq("estado", "Abierto").execute()
    if turno_abierto.data:
        st.session_state.turno_id = turno_abierto.data[0]['turno_id']
        st.rerun()
    
    st.markdown('<div class="main-header">🏦 APERTURA DE TURNO DE CAJA</div>', unsafe_allow_html=True)
    col_t1, col_t2, col_t3 = st.columns([1, 1.5, 1])
    with col_t2:
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        st.write(f"Hola **{st.session_state.empleado_nombre}**, debes abrir tu turno para comenzar a facturar.")
        with st.form("open_shift_form"):
            monto_ini = st.number_input("Dinero en caja inicial (Efectivo Base S/.)", min_value=0.0, step=10.0, value=0.0)
            if st.form_submit_button("Abrir Caja e Iniciar Turno", type="primary"):
                res_turno = supabase.table("turnos").insert({
                    "empleado_id": st.session_state.empleado_id,
                    "monto_apertura": monto_ini,
                    "estado": "Abierto"
                }).execute()
                st.session_state.turno_id = res_turno.data[0]['turno_id']
                st.success("✅ Turno abierto correctamente.")
                time.sleep(0.5); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ==========================================
# 5. ESTRUCTURA PRINCIPAL Y SIDEBAR (ERP)
# ==========================================
st.markdown('<div class="main-header">📱 ACCESORIOS JORDAN | SMART POS v7.0</div>', unsafe_allow_html=True)

st.sidebar.markdown(f"👤 **Vendedor:** {st.session_state.empleado_nombre} ({st.session_state.empleado_rol})")
st.sidebar.markdown(f"⏱️ **Turno N°:** {st.session_state.turno_id}")
if st.sidebar.button("🔒 Cerrar Sesión"):
    st.session_state.empleado_id = None
    st.session_state.turno_id = None
    st.rerun()

st.sidebar.divider()

# MENÚ DINÁMICO POR ROLES
menu_options = ["🛒 VENTAS (POS)", "🔄 DEVOLUCIONES", "⚠️ MERMAS/DAÑOS", "🧾 REGISTRO DE TICKETS"]
if st.session_state.empleado_rol == "Admin":
    menu_options.insert(1, "📦 ALMACÉN PRO")
    menu_options.append("📊 REPORTES (CAJA)")

menu = st.sidebar.radio("SISTEMA DE GESTIÓN", menu_options)

st.sidebar.divider()

# CONTROL DE ASISTENCIA
st.sidebar.markdown("#### ⌚ Control de Asistencia")
with st.sidebar.form("asistencia_form", clear_on_submit=True):
    pin_ast = st.text_input("Ingresa tu PIN", type="password")
    c_a1, c_a2 = st.columns(2)
    ingreso = c_a1.form_submit_button("🟢 Ingreso")
    salida = c_a2.form_submit_button("🔴 Salida")
    if ingreso or salida:
        if pin_ast == supabase.table("empleados").select("pin").eq("id", st.session_state.empleado_id).execute().data[0]['pin']:
            tipo = "Ingreso" if ingreso else "Salida"
            supabase.table("asistencia").insert({"empleado_id": st.session_state.empleado_id, "tipo_marcacion": tipo}).execute()
            st.sidebar.success(f"{tipo} registrado.")
        else: st.sidebar.error("PIN inválido.")

# ==========================================
# 🛒 MÓDULO 1: VENTAS Y REGATEO
# ==========================================
if menu == "🛒 VENTAS (POS)":
    # 4. Impresión silenciosa vía JS incrustado en HTML (Si hay ticket pendiente)
    if st.session_state.last_ticket_html:
        components.html(st.session_state.last_ticket_html, width=0, height=0)
        st.success("🖨️ Enviando ticket a la impresora térmica...")
        st.session_state.last_ticket_html = None # Limpiar tras imprimir

    col_v1, col_v2 = st.columns([1.5, 1.4])
    with col_v1:
        st.subheader("🔍 Ingreso de Productos")
        with st.form("form_manual_barcode", clear_on_submit=True):
            col_mb1, col_mb2 = st.columns([3, 1])
            manual_code = col_mb1.text_input("Tipear Código Numérico")
            add_manual = col_mb2.form_submit_button("➕ Agregar")
            if add_manual and manual_code:
                if procesar_codigo_venta(manual_code): time.sleep(0.5); st.rerun()

        with st.expander("📷 ABRIR ESCÁNER TÁCTIL", expanded=False):
            img = st.camera_input("Lector", key=f"scanner_venta_{st.session_state.cam_v_key}", label_visibility="hidden")
            if img:
                code = scan_pos(img)
                if code:
                    if procesar_codigo_venta(code):
                        st.session_state.cam_v_key += 1; time.sleep(0.5); st.rerun()
                else: st.error("⚠️ Foto borrosa.")

        st.divider()
        search = st.text_input("Búsqueda por Nombre")
        if search:
            try:
                res_s = supabase.table("productos").select("*, marcas(nombre)").ilike("nombre", f"%{search}%").execute()
                if res_s.data:
                    for p in res_s.data:
                        c_p1, c_p2, c_p3 = st.columns([3, 1, 1])
                        c_p1.write(f"**{p['nombre']}** ({p['marcas']['nombre'] if p['marcas'] else 'Genérico'}) - Stock: {p['stock_actual']}")
                        c_p2.write(f"S/. {p['precio_lista']}")
                        if c_p3.button("➕", key=f"add_{p['codigo_barras']}"):
                            if p['stock_actual'] > 0:
                                st.session_state.carrito.append({'id': p['codigo_barras'], 'nombre': p['nombre'], 'precio': float(p['precio_lista']), 'cant': 1, 'costo': float(p['costo_compra']), 'p_min': float(p['precio_minimo'])})
                                st.rerun()
                            else: st.error("Sin stock")
            except: pass

    with col_v2:
        st.subheader("🛍️ Carrito de Compras")
        if not st.session_state.carrito: st.info("🛒 Aún no se han agregado productos.")
        else:
            total_venta = 0
            for i, item in enumerate(st.session_state.carrito):
                st.write(f"**{item['cant']}x** {item['nombre']} (Mín: S/. {item['p_min']:.2f})")
                c_c1, c_c2, c_c3 = st.columns([2, 1.5, 0.7])
                nuevo_precio = c_c1.number_input("Precio final (S/.)", min_value=float(item['p_min']), value=float(item['precio']), step=1.0, key=f"precio_{i}")
                st.session_state.carrito[i]['precio'] = nuevo_precio
                subtotal = nuevo_precio * item['cant']
                c_c2.markdown(f"<div style='padding-top:30px;'><b>Sub: S/. {subtotal:.2f}</b></div>", unsafe_allow_html=True)
                if c_c3.button("❌", key=f"del_{i}"): st.session_state.carrito.pop(i); st.rerun()
                total_venta += subtotal
            
            st.divider()
            st.markdown(f"<h2 style='color:#16a34a; text-align:center;'>TOTAL: S/. {total_venta:.2f}</h2>", unsafe_allow_html=True)
            pago = st.selectbox("Medio de Pago", ["Efectivo", "Yape", "Plin", "Tarjeta VISA/MC"])
            
            # Validación de Yape/Plin (Requerimiento 6)
            ref_pago = ""
            if pago in ["Yape", "Plin"]:
                ref_pago = st.text_input("📱 Número de Aprobación / Referencia de Pago (Obligatorio)")
            
            if st.button("🏁 PROCESAR VENTA E IMPRIMIR", type="primary"):
                if pago in ["Yape", "Plin"] and not ref_pago:
                    st.error("🛑 Debes ingresar el número de referencia del Yape/Plin para continuar.")
                else:
                    try:
                        t_num = f"AJ-{int(time.time())}"
                        # Insertar con empleado, turno y ref
                        res_cab = supabase.table("ventas_cabecera").insert({
                            "ticket_numero": t_num, "total_venta": total_venta, "metodo_pago": pago, "tipo_comprobante": "Ticket",
                            "empleado_id": st.session_state.empleado_id, "turno_id": st.session_state.turno_id, "referencia_pago": ref_pago
                        }).execute()
                        v_id = res_cab.data[0]['id']
                        
                        items_html = ""
                        for item in st.session_state.carrito:
                            supabase.table("ventas_detalle").insert({"venta_id": v_id, "producto_id": item['id'], "cantidad": item['cant'], "precio_unitario": item['precio'], "subtotal": item['precio'] * item['cant']}).execute()
                            stk = supabase.table("productos").select("stock_actual").eq("codigo_barras", item['id']).execute()
                            supabase.table("productos").update({"stock_actual": stk.data[0]['stock_actual'] - item['cant']}).eq("codigo_barras", item['id']).execute()
                            items_html += f"{item['nombre'][:20]:<20} <br> {item['cant']:>2} x S/. {item['precio']:.2f} = S/. {item['precio']*item['cant']:.2f}<br><br>"
                        
                        # Generación del HTML Crudo del Ticket (Requerimiento 4 y 5)
                        fecha_tk = datetime.now().strftime('%d/%m/%Y %H:%M')
                        cuerpo_ticket = f"""
                        --------------------------------<br>
                        TICKET: {t_num}<br>
                        FECHA: {fecha_tk}<br>
                        CAJERO: {st.session_state.empleado_nombre}<br>
                        --------------------------------<br>
                        {items_html}
                        --------------------------------<br>
                        <b>TOTAL PAGADO: S/. {total_venta:.2f}</b><br>
                        MÉTODO: {pago} {f'(Ref: {ref_pago})' if ref_pago else ''}<br>
                        --------------------------------<br>
                        """
                        
                        ticket_dual_js = f"""
                        <html><head><style>
                        body {{ font-family: 'Courier New', monospace; font-size: 14px; color: black; background: white; }}
                        .ticket-termico {{ padding: 15px; border: 1px dashed #333; width: 100%; max-width: 320px; margin: 0 auto; line-height: 1.2;}}
                        @media print {{ .page-break {{ page-break-after: always; }} }}
                        </style></head><body>
                        <div class="ticket-termico"><center><b>ACCESORIOS JORDAN</b><br>COPIA CLIENTE</center><br>{cuerpo_ticket}<center>¡Gracias por su compra!</center></div>
                        <div class="page-break"></div>
                        <div class="ticket-termico"><center><b>ACCESORIOS JORDAN</b><br>COPIA CONTROL INTERNO</center><br>{cuerpo_ticket}</div>
                        <script>window.onload = function() {{ window.print(); }}</script>
                        </body></html>
                        """
                        
                        # Guardar historial
                        supabase.table("ticket_historial").insert({"ticket_numero": t_num, "empleado_id": st.session_state.empleado_id, "html_payload": ticket_dual_js}).execute()
                        
                        st.session_state.last_ticket_html = ticket_dual_js
                        st.session_state.carrito = []
                        st.rerun() 
                    except Exception as e: st.error(ERROR_ADMIN)

# ==========================================
# 📦 MÓDULO 2: ALMACÉN PRO (SOLO ADMIN)
# ==========================================
elif menu == "📦 ALMACÉN PRO":
    st.subheader("Gestión de Inventario Maestro")
    t1, t2, t3 = st.tabs(["➕ Ingreso Mercadería", "⚙️ Configuración", "📋 Inventario General"])
    
    with t1:
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        with st.expander("📷 ABRIR ESCÁNER ALMACÉN", expanded=True):
            img_a = st.camera_input("Scanner Almacén", key=f"cam_almacen_{st.session_state.cam_a_key}")
            if img_a:
                code_a = scan_pos(img_a)
                if code_a: 
                    try:
                        check = supabase.table("productos").select("*, categorias(nombre), marcas(nombre)").eq("codigo_barras", code_a).execute()
                        if check.data:
                            p_ex = check.data[0]
                            st.markdown(f"""<div class="resumen-duplicado"><b>⚠️ ESTE PRODUCTO YA EXISTE</b><br><b>Nombre:</b> {p_ex['nombre']} | <b>Stock:</b> {p_ex['stock_actual']} ud.</div>""", unsafe_allow_html=True)
                            st.session_state.cam_a_key += 1 
                        else:
                            st.session_state.iny_alm_cod = code_a
                            # API UPC (Requerimiento 6)
                            st.session_state.api_nombre_sugerido = fetch_upc_api(code_a)
                            st.session_state.cam_a_key += 1; st.rerun() 
                    except: st.error(ERROR_ADMIN)
        
        cats, mars = load_data("categorias"), load_data("marcas")
        with st.form("form_nuevo", clear_on_submit=True):
            # API UPC Text input trigger if manually typed
            c_cod = st.text_input("Código de Barras", value=st.session_state.iny_alm_cod)
            c_nom = st.text_input("Nombre / Descripción del Accesorio", value=st.session_state.api_nombre_sugerido)
            f1, f2, f3 = st.columns(3)
            f_cat = f1.selectbox("Categoría", cats['nombre'].tolist() if not cats.empty else ["Vacío"])
            f_mar = f2.selectbox("Marca", mars['nombre'].tolist() if not mars.empty else ["Vacío"])
            f_cal = f3.selectbox("Calidad", ["Genérico", "Original", "AAA", "Alta Gama"])
            f4, f5, f6, f7 = st.columns(4)
            f_costo = f4.number_input("Costo Compra (S/.)", min_value=0.0, step=0.5)
            f_pmin = f6.number_input("Precio Mín. (S/.)", min_value=0.0, step=0.5)
            f_venta = f5.number_input("Precio Venta (S/.)", min_value=0.0, step=0.5)
            f_stock = f7.number_input("Stock Inicial", min_value=1, step=1)
            
            if st.form_submit_button("🚀 GUARDAR EN INVENTARIO", type="primary"):
                if c_cod and c_nom and not cats.empty and not mars.empty:
                    try:
                        if not supabase.table("productos").select("codigo_barras").eq("codigo_barras", c_cod).execute().data:
                            cid, mid = int(cats[cats['nombre'] == f_cat]['id'].iloc[0]), int(mars[mars['nombre'] == f_mar]['id'].iloc[0])
                            supabase.table("productos").insert({"codigo_barras": c_cod, "nombre": c_nom, "categoria_id": cid, "marca_id": mid, "calidad": f_cal, "costo_compra": f_costo, "precio_lista": f_venta, "precio_minimo": f_pmin, "stock_actual": f_stock, "stock_inicial": f_stock}).execute()
                            st.session_state.iny_alm_cod = ""; st.session_state.api_nombre_sugerido = ""; st.success("✅ Guardado."); time.sleep(1.5); st.rerun()
                        else: st.error("❌ Código ya existe.")
                    except: st.error(ERROR_ADMIN)
                else: st.warning("Rellena todos los campos.")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with t2:
        st.info("Configura Categorías y Marcas.")
    with t3:
        try:
            prods = supabase.table("productos").select("*, categorias(nombre), marcas(nombre)").execute()
            if prods.data: 
                df = pd.DataFrame(prods.data)
                df['Categoría'] = df['categorias'].apply(lambda x: x['nombre'] if isinstance(x, dict) else 'N/A')
                df['Marca'] = df['marcas'].apply(lambda x: x['nombre'] if isinstance(x, dict) else 'N/A')
                df['stock_inicial'] = df.apply(lambda row: row.get('stock_inicial') if pd.notnull(row.get('stock_inicial')) else row['stock_actual'], axis=1)
                df_show = df[['codigo_barras', 'nombre', 'Categoría', 'Marca', 'stock_inicial', 'stock_actual', 'costo_compra', 'precio_minimo', 'precio_lista']]
                st.dataframe(df_show, use_container_width=True)
                
                st.divider()
                st.write("### ⚡ Reabastecimiento Rápido (Suma de Stock)")
                col_r1, col_r2 = st.columns([3, 1])
                selected_prod = col_r1.selectbox("Seleccionar producto:", ["..."] + [f"{row['codigo_barras']} - {row['nombre']} (Stock: {row['stock_actual']})" for idx, row in df.iterrows()])
                add_stock = col_r2.number_input("Cantidad a sumar", min_value=1, step=1)
                if st.button("➕ Sumar al Stock Físico"):
                    if selected_prod != "...":
                        cod_up = selected_prod.split(" - ")[0]
                        c_stk, c_ini = int(df[df['codigo_barras'] == cod_up]['stock_actual'].iloc[0]), int(df[df['codigo_barras'] == cod_up]['stock_inicial'].iloc[0])
                        supabase.table("productos").update({"stock_actual": c_stk + add_stock, "stock_inicial": c_ini + add_stock}).eq("codigo_barras", cod_up).execute()
                        st.success("✅ Actualizado"); time.sleep(1.5); st.rerun() 
        except: pass

# ==========================================
# 🔄 MÓDULO 3: DEVOLUCIONES
# ==========================================
elif menu == "🔄 DEVOLUCIONES":
    st.subheader("Gestión de Devoluciones y Reembolsos")
    search_dev = st.text_input("Ingresa el Número de Ticket (AJ-...) o el Código de Barras")
    if search_dev:
        if "AJ-" in search_dev.upper():
            try:
                v_cab = supabase.table("ventas_cabecera").select("*").eq("ticket_numero", search_dev.upper()).execute()
                if v_cab.data:
                    st.success(f"✅ Ticket: Pago: {v_cab.data[0]['metodo_pago']}")
                    v_det = supabase.table("ventas_detalle").select("*, productos(nombre)").eq("venta_id", v_cab.data[0]['id']).execute()
                    for d in v_det.data:
                        col_d1, col_d2 = st.columns([3, 1])
                        col_d1.write(f"**{d['productos']['nombre']}** - Compró: {d['cantidad']} ud.")
                        if col_d2.button("Ejecutar Devolución", key=f"dev_{d['id']}"):
                            p_s = supabase.table("productos").select("stock_actual").eq("codigo_barras", d['producto_id']).execute()
                            supabase.table("productos").update({"stock_actual": p_s.data[0]['stock_actual'] + d['cantidad']}).eq("codigo_barras", d['producto_id']).execute()
                            supabase.table("devoluciones").insert({"empleado_id": st.session_state.empleado_id, "turno_id": st.session_state.turno_id, "producto_id": d['producto_id'], "cantidad": d['cantidad'], "motivo": "Devolución por Ticket", "dinero_devuelto": d['subtotal'], "estado_producto": "Vuelve a tienda"}).execute()
                            st.session_state.iny_dev_cod = ""; st.success("✅ Devuelto."); time.sleep(1.5); st.rerun()
            except: pass
        else:
            try:
                p_db = supabase.table("productos").select("*").eq("codigo_barras", search_dev).execute()
                if p_db.data:
                    p = p_db.data[0]
                    with st.form("form_dev_libre"):
                        col_f1, col_f2 = st.columns(2)
                        dev_cant = col_f1.number_input("Cantidad a regresar", min_value=1, step=1)
                        dinero_reembolsado = col_f2.number_input("Dinero devuelto por UND (S/.)", value=float(p['precio_lista']))
                        motivo_dev = st.text_input("Motivo (Obligatorio)")
                        if st.form_submit_button("🔁 EJECUTAR DEVOLUCIÓN"):
                            if motivo_dev:
                                supabase.table("productos").update({"stock_actual": p['stock_actual'] + dev_cant}).eq("codigo_barras", p['codigo_barras']).execute()
                                supabase.table("devoluciones").insert({"empleado_id": st.session_state.empleado_id, "turno_id": st.session_state.turno_id, "producto_id": p['codigo_barras'], "cantidad": dev_cant, "motivo": motivo_dev, "dinero_devuelto": dev_cant * dinero_reembolsado, "estado_producto": "Vuelve a tienda"}).execute()
                                st.success("✅ Devuelto."); time.sleep(1.5); st.rerun()
            except: pass

# ==========================================
# ⚠️ MÓDULO 4: MERMAS Y DAÑOS
# ==========================================
elif menu == "⚠️ MERMAS/DAÑOS":
    st.subheader("Dar de Baja Productos Dañados")
    m_cod = st.text_input("Código de Barras del Producto Dañado")
    if m_cod:
        try:
            p_inf = supabase.table("productos").select("*").eq("codigo_barras", m_cod).execute()
            if p_inf.data:
                p_merma = p_inf.data[0]
                with st.form("form_merma"):
                    m_cant = st.number_input("Cantidad a botar", min_value=1, max_value=int(p_merma['stock_actual']) if p_merma['stock_actual']>0 else 1)
                    m_mot = st.selectbox("Motivo", ["Roto al instalar/mostrar", "Falla de Fábrica", "Robo/Extravío"])
                    if st.form_submit_button("⚠️ CONFIRMAR PÉRDIDA"):
                        if p_merma['stock_actual'] >= m_cant:
                            supabase.table("productos").update({"stock_actual": p_merma['stock_actual'] - m_cant}).eq("codigo_barras", m_cod).execute()
                            supabase.table("mermas").insert({"empleado_id": st.session_state.empleado_id, "turno_id": st.session_state.turno_id, "producto_id": m_cod, "cantidad": m_cant, "motivo": m_mot, "perdida_monetaria": p_merma['costo_compra'] * m_cant}).execute()
                            st.success("✅ Baja exitosa."); time.sleep(1.5); st.rerun()
        except: pass

# ==========================================
# 🧾 MÓDULO NUEVO: REGISTRO DE TICKETS
# ==========================================
elif menu == "🧾 REGISTRO DE TICKETS":
    st.subheader("Historial de Comprobantes Emitidos")
    try:
        tks = supabase.table("ticket_historial").select("ticket_numero, fecha, html_payload").order("fecha", desc=True).limit(50).execute()
        if tks.data:
            df_tks = pd.DataFrame(tks.data)
            df_tks['fecha_format'] = pd.to_datetime(df_tks['fecha']).dt.strftime('%d/%m/%Y %H:%M')
            opciones = [f"{row['ticket_numero']} - {row['fecha_format']}" for _, row in df_tks.iterrows()]
            sel_tk = st.selectbox("Selecciona un ticket para visualizar / reimprimir", opciones)
            if sel_tk:
                tk_num = sel_tk.split(" - ")[0]
                html_raw = df_tks[df_tks['ticket_numero'] == tk_num]['html_payload'].iloc[0]
                # Modificamos el payload para mostrarlo visualmente sin ejecutar el script JS automático de impresión de nuevo
                html_safe = html_raw.replace("<script>window.onload = function() { window.print(); }</script>", "")
                st.components.v1.html(html_safe, height=600, scrolling=True)
        else: st.info("No hay tickets emitidos aún.")
    except: st.error(ERROR_ADMIN)

# ==========================================
# 📊 MÓDULO 5: REPORTES Y CIERRE (POR TURNO ACTIVO)
# ==========================================
elif menu == "📊 REPORTES (CAJA)" and st.session_state.empleado_rol == "Admin":
    st.subheader(f"Auditoría Contable - Turno N° {st.session_state.turno_id}")
    try:
        t_id = st.session_state.turno_id
        # Filtrar TODO exclusivamente por el turno actual
        detalles = supabase.table("ventas_detalle").select("*, productos(nombre, costo_compra), ventas_cabecera!inner(ticket_numero, turno_id)").eq("ventas_cabecera.turno_id", t_id).execute()
        devs = supabase.table("devoluciones").select("*, productos(costo_compra)").eq("turno_id", t_id).execute()
        mermas = supabase.table("mermas").select("*").eq("turno_id", t_id).execute()
        
        total_ventas_brutas, total_costo_vendido = 0.0, 0.0
        total_devoluciones, costo_recuperado_devs, total_perdida_mermas = 0.0, 0.0, 0.0
        
        if detalles.data:
            df_rep = pd.DataFrame(detalles.data)
            df_rep['Costo Unitario'] = df_rep['productos'].apply(lambda x: float(x['costo_compra']) if isinstance(x, dict) and x.get('costo_compra') else 0.0)
            df_rep['Costo Total'] = df_rep['Costo Unitario'] * df_rep['cantidad']
            total_ventas_brutas = df_rep['subtotal'].sum()
            total_costo_vendido = df_rep['Costo Total'].sum()
            
        if devs.data:
            df_devs = pd.DataFrame(devs.data)
            df_devs['Costo Unitario Dev'] = df_devs['productos'].apply(lambda x: float(x['costo_compra']) if isinstance(x, dict) and x.get('costo_compra') else 0.0)
            costo_recuperado_devs = (df_devs['Costo Unitario Dev'] * df_devs['cantidad']).sum()
            total_devoluciones = df_devs['dinero_devuelto'].sum()
            
        if mermas.data:
            df_mer = pd.DataFrame(mermas.data)
            total_perdida_mermas = df_mer['perdida_monetaria'].sum()
            
        capital_invertido_real = total_costo_vendido - costo_recuperado_devs
        
        # Recuperar el monto inicial con el que el vendedor abrió el turno
        t_data = supabase.table("turnos").select("monto_apertura").eq("turno_id", t_id).execute().data[0]
        efectivo_base = float(t_data['monto_apertura'])
        
        # Caja neta incluye el efectivo base inicial + ventas - devoluciones
        caja_esperada = efectivo_base + total_ventas_brutas - total_devoluciones
        ganancia_neta_real = total_ventas_brutas - total_devoluciones - capital_invertido_real - total_perdida_mermas
        
        st.markdown("##### 💵 Balance de Caja del Vendedor")
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"<div class='metric-box'><div class='metric-title'>Apertura</div><div class='metric-value'>S/. {efectivo_base:.2f}</div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='metric-box'><div class='metric-title'>Ventas Brutas</div><div class='metric-value'>S/. {total_ventas_brutas:.2f}</div></div>", unsafe_allow_html=True)
        c3.markdown(f"<div class='metric-box'><div class='metric-title'>Devoluciones</div><div class='metric-value metric-red'>- S/. {total_devoluciones:.2f}</div></div>", unsafe_allow_html=True)
        c4.markdown(f"<div class='metric-box'><div class='metric-title'>CAJA ESPERADA</div><div class='metric-value metric-green'>S/. {caja_esperada:.2f}</div></div>", unsafe_allow_html=True)
        
        st.markdown('<div class="cierre-box">', unsafe_allow_html=True)
        st.write("### 🛑 CORTAR CAJA DEL VENDEDOR")
        with st.form("form_cierre", clear_on_submit=True):
            monto_real = st.number_input("💵 ¿Cuánto efectivo y Yape hay físicamente en caja ahora mismo?", min_value=0.0, step=10.0)
            if st.form_submit_button("🔒 CERRAR TURNO", type="primary"):
                supabase.table("turnos").update({
                    "estado": "Cerrado", "fecha_cierre": datetime.now().isoformat(),
                    "monto_cierre_esperado": caja_esperada, "monto_cierre_real": monto_real
                }).eq("turno_id", t_id).execute()
                
                # Actualizar Inventario a Inicial
                prods_res = supabase.table("productos").select("codigo_barras, stock_actual").execute()
                for prod in prods_res.data:
                    supabase.table("productos").update({"stock_inicial": prod['stock_actual']}).eq("codigo_barras", prod['codigo_barras']).execute()
                
                st.session_state.turno_id = None
                st.success("✅ Turno Cerrado. Sesión finalizada.")
                time.sleep(2); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    except: st.error(ERROR_ADMIN)
