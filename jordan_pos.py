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
import json

# ==========================================
# 1. CONEXIÓN AL CEREBRO DE BASE DE DATOS
# ==========================================
URL_SUPABASE = "https://degzltrjrzqbahdonmmb.supabase.co"
KEY_SUPABASE = "sb_publishable_td5_vXX42LYc8PlTAbBgVg_-xCp-94r"
supabase = create_client(URL_SUPABASE, KEY_SUPABASE)

st.set_page_config(page_title="JORDAN POS ERP", layout="wide", page_icon="📱")

ERROR_ADMIN = "🚨 Error del sistema. Contactar al administrador."

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
    'logged_in': False, 'user_id': None, 'user_name': "", 'user_perms': [], 'turno_id': None,
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

def get_lista_usuarios():
    try:
        res = supabase.table("usuarios").select("id, nombre_completo, usuario").eq("estado", "Activo").execute()
        return res.data if res.data else []
    except: return []

# ==========================================
# 5. ESTRUCTURA PRINCIPAL Y SIDEBAR (ERP)
# ==========================================
st.markdown('<div class="main-header">📱 ACCESORIOS JORDAN | ERP AVANZADO</div>', unsafe_allow_html=True)

# --- MENÚ BASE (Siempre Abierto para Vendedores) ---
menu_options = ["🛒 VENTAS (POS)", "🔄 DEVOLUCIONES"]

# --- SIDEBAR: ASISTENCIA Y LOGIN DE MÓDULOS ---
st.sidebar.markdown("### 🏢 Control de Personal")

# 1. Asistencia (Corregido con validación de contraseña visible)
with st.sidebar.expander("⌚ Marcar Asistencia", expanded=False):
    with st.form("form_asistencia", clear_on_submit=True):
        usr_ast = st.text_input("Usuario")
        pwd_ast = st.text_input("Contraseña", type="password")
        c_a1, c_a2 = st.columns(2)
        btn_in = c_a1.form_submit_button("🟢 Entrada")
        btn_out = c_a2.form_submit_button("🔴 Salida")
        if btn_in or btn_out:
            if usr_ast and pwd_ast:
                usr_data = supabase.table("usuarios").select("*").eq("usuario", usr_ast).execute()
                if usr_data.data and usr_data.data[0].get('clave') == pwd_ast:
                    tipo = "Ingreso" if btn_in else "Salida"
                    supabase.table("asistencia").insert({"usuario_id": usr_data.data[0]['id'], "tipo_marcacion": tipo}).execute()
                    st.success(f"✅ {tipo} registrado para {usr_data.data[0]['nombre_completo']}")
                else:
                    st.error("❌ Usuario o Contraseña incorrectos.")
            else:
                st.warning("⚠️ Ingresa tu usuario y contraseña.")

st.sidebar.divider()

# 2. Login para Módulos de Administración
if not st.session_state.logged_in:
    st.sidebar.markdown("#### 🔐 Acceso a Módulos Restringidos")
    with st.sidebar.form("form_login"):
        l_usr = st.text_input("Usuario Administrador / Encargado")
        l_pwd = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Iniciar Sesión", type="primary"):
            usr_data = supabase.table("usuarios").select("*").eq("usuario", l_usr).execute()
            # Validación con contraseña en texto plano (columna 'clave')
            if usr_data.data and usr_data.data[0].get('clave') == l_pwd:
                st.session_state.logged_in = True
                st.session_state.user_id = usr_data.data[0]['id']
                st.session_state.user_name = usr_data.data[0]['nombre_completo']
                st.session_state.user_perms = usr_data.data[0].get('permisos', [])
                st.rerun()
            else:
                st.error("❌ Acceso Denegado. Revisa tus credenciales.")
else:
    st.sidebar.success(f"👤 Conectado: {st.session_state.user_name}")
    if st.sidebar.button("🚪 Cerrar Sesión Administrativa"):
        st.session_state.logged_in = False
        st.session_state.user_id = None
        st.session_state.user_perms = []
        st.rerun()

# --- CONSTRUCCIÓN DINÁMICA DEL MENÚ SEGÚN PERMISOS ---
if st.session_state.logged_in:
    p = st.session_state.user_perms
    if "mermas" in p: menu_options.append("⚠️ MERMAS/DAÑOS")
    if "inventario_ver" in p: menu_options.append("📦 ALMACÉN PRO")
    if "reportes" in p: menu_options.append("🧾 REGISTRO DE TICKETS")
    if "cierre_caja" in p or "reportes" in p: menu_options.append("📊 REPORTES (CAJA)")
    if "gestion_usuarios" in p: menu_options.append("👥 GESTIÓN DE USUARIOS")

menu = st.sidebar.radio("Navegación", menu_options)

# ==========================================
# 🛒 MÓDULO 1: VENTAS (ABIERTO A TODOS)
# ==========================================
if menu == "🛒 VENTAS (POS)":
    # Impresión JS Automática Silenciosa
    if st.session_state.last_ticket_html:
        components.html(st.session_state.last_ticket_html, width=0, height=0)
        st.success("🖨️ Imprimiendo ticket térmico doble...")
        st.session_state.last_ticket_html = None 

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
            
            # --- IDENTIFICACIÓN DEL VENDEDOR EN EL MOSTRADOR COMPARTIDO ---
            lista_vendedores = get_lista_usuarios()
            vendedor_opciones = {f"{v['nombre_completo']} ({v['usuario']})": v['id'] for v in lista_vendedores}
            vendedor_seleccionado = st.selectbox("👤 ¿Quién está realizando esta venta?", ["Seleccionar Vendedor..."] + list(vendedor_opciones.keys()))
            
            pago = st.selectbox("Medio de Pago", ["Efectivo", "Yape", "Plin", "Tarjeta VISA/MC"])
            
            ref_pago = ""
            if pago in ["Yape", "Plin"]:
                ref_pago = st.text_input("📱 Número de Aprobación / Referencia de Pago (Obligatorio)")
            
            if st.button("🏁 PROCESAR VENTA E IMPRIMIR", type="primary"):
                if vendedor_seleccionado == "Seleccionar Vendedor...":
                    st.error("🛑 Debes seleccionar tu usuario para registrar la venta.")
                elif pago in ["Yape", "Plin"] and not ref_pago:
                    st.error("🛑 Debes ingresar el número de referencia del Yape/Plin para continuar.")
                else:
                    try:
                        vendedor_id = vendedor_opciones[vendedor_seleccionado]
                        t_num = f"AJ-{int(time.time())}"
                        
                        # Guardar Venta (Cabecera)
                        res_cab = supabase.table("ventas_cabecera").insert({
                            "ticket_numero": t_num, "total_venta": total_venta, "metodo_pago": pago, "tipo_comprobante": "Ticket",
                            "usuario_id": vendedor_id, "referencia_pago": ref_pago
                        }).execute()
                        v_id = res_cab.data[0]['id']
                        
                        items_html = ""
                        for item in st.session_state.carrito:
                            supabase.table("ventas_detalle").insert({"venta_id": v_id, "producto_id": item['id'], "cantidad": item['cant'], "precio_unitario": item['precio'], "subtotal": item['precio'] * item['cant']}).execute()
                            stk = supabase.table("productos").select("stock_actual").eq("codigo_barras", item['id']).execute()
                            supabase.table("productos").update({"stock_actual": stk.data[0]['stock_actual'] - item['cant']}).eq("codigo_barras", item['id']).execute()
                            items_html += f"{item['nombre'][:20]:<20} <br> {item['cant']:>2} x S/. {item['precio']:.2f} = S/. {item['precio']*item['cant']:.2f}<br><br>"
                        
                        # HTML para Impresión Dual
                        fecha_tk = datetime.now().strftime('%d/%m/%Y %H:%M')
                        nombre_vendedor_ticket = vendedor_seleccionado.split(" (")[0]
                        cuerpo_ticket = f"""
                        --------------------------------<br>
                        TICKET: {t_num}<br>
                        FECHA: {fecha_tk}<br>
                        CAJERO: {nombre_vendedor_ticket}<br>
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
                        
                        supabase.table("ticket_historial").insert({"ticket_numero": t_num, "usuario_id": vendedor_id, "html_payload": ticket_dual_js}).execute()
                        
                        st.session_state.last_ticket_html = ticket_dual_js
                        st.session_state.carrito = []
                        st.rerun() 
                    except Exception as e: st.error(ERROR_ADMIN)

# ==========================================
# 🔄 MÓDULO 3: DEVOLUCIONES (ABIERTO A TODOS)
# ==========================================
elif menu == "🔄 DEVOLUCIONES":
    st.subheader("Gestión de Devoluciones y Reembolsos")
    search_dev = st.text_input("Ingresa el Número de Ticket (AJ-...) o el Código de Barras")
    
    lista_vendedores = get_lista_usuarios()
    vendedor_opciones = {f"{v['nombre_completo']} ({v['usuario']})": v['id'] for v in lista_vendedores}
    
    if search_dev:
        if "AJ-" in search_dev.upper():
            try:
                v_cab = supabase.table("ventas_cabecera").select("*").eq("ticket_numero", search_dev.upper()).execute()
                if v_cab.data:
                    st.success(f"✅ Ticket: Pago: {v_cab.data[0]['metodo_pago']}")
                    v_det = supabase.table("ventas_detalle").select("*, productos(nombre)").eq("venta_id", v_cab.data[0]['id']).execute()
                    
                    vendedor_seleccionado = st.selectbox("👤 Vendedor que autoriza la devolución:", ["Seleccionar Vendedor..."] + list(vendedor_opciones.keys()))
                    
                    for d in v_det.data:
                        col_d1, col_d2 = st.columns([3, 1])
                        col_d1.write(f"**{d['productos']['nombre']}** - Compró: {d['cantidad']} ud.")
                        if col_d2.button("Ejecutar Devolución", key=f"dev_{d['id']}"):
                            if vendedor_seleccionado != "Seleccionar Vendedor...":
                                p_s = supabase.table("productos").select("stock_actual").eq("codigo_barras", d['producto_id']).execute()
                                supabase.table("productos").update({"stock_actual": p_s.data[0]['stock_actual'] + d['cantidad']}).eq("codigo_barras", d['producto_id']).execute()
                                supabase.table("devoluciones").insert({
                                    "usuario_id": vendedor_opciones[vendedor_seleccionado], 
                                    "producto_id": d['producto_id'], "cantidad": d['cantidad'], 
                                    "motivo": "Devolución por Ticket", "dinero_devuelto": d['subtotal'], "estado_producto": "Vuelve a tienda"
                                }).execute()
                                st.session_state.iny_dev_cod = ""; st.success("✅ Devuelto."); time.sleep(1.5); st.rerun()
                            else: st.error("Selecciona tu usuario para proceder.")
            except: pass
        else:
            try:
                p_db = supabase.table("productos").select("*").eq("codigo_barras", search_dev).execute()
                if p_db.data:
                    p = p_db.data[0]
                    with st.form("form_dev_libre"):
                        vendedor_seleccionado = st.selectbox("👤 Vendedor que autoriza:", ["Seleccionar Vendedor..."] + list(vendedor_opciones.keys()))
                        col_f1, col_f2 = st.columns(2)
                        dev_cant = col_f1.number_input("Cantidad a regresar", min_value=1, step=1)
                        dinero_reembolsado = col_f2.number_input("Dinero devuelto por UND (S/.)", value=float(p['precio_lista']))
                        motivo_dev = st.text_input("Motivo (Obligatorio)")
                        if st.form_submit_button("🔁 EJECUTAR DEVOLUCIÓN"):
                            if motivo_dev and vendedor_seleccionado != "Seleccionar Vendedor...":
                                supabase.table("productos").update({"stock_actual": p['stock_actual'] + dev_cant}).eq("codigo_barras", p['codigo_barras']).execute()
                                supabase.table("devoluciones").insert({"usuario_id": vendedor_opciones[vendedor_seleccionado], "producto_id": p['codigo_barras'], "cantidad": dev_cant, "motivo": motivo_dev, "dinero_devuelto": dev_cant * dinero_reembolsado, "estado_producto": "Vuelve a tienda"}).execute()
                                st.success("✅ Devuelto."); time.sleep(1.5); st.rerun()
                            else: st.error("Falta motivo o seleccionar usuario.")
            except: pass

# ==========================================
# 📦 MÓDULO 2: ALMACÉN PRO (RESTRINGIDO)
# ==========================================
elif menu == "📦 ALMACÉN PRO" and "inventario_ver" in st.session_state.user_perms:
    st.subheader("Gestión de Inventario Maestro")
    t1, t2, t3 = st.tabs(["➕ Ingreso Mercadería", "⚙️ Configuración", "📋 Inventario General"])
    
    with t1:
        if "inventario_agregar" in st.session_state.user_perms:
            st.markdown('<div class="css-card">', unsafe_allow_html=True)
            with st.expander("📷 ABRIR ESCÁNER ALMACÉN", expanded=True):
                img_a = st.camera_input("Scanner Almacén", key=f"cam_almacen_{st.session_state.cam_a_key}")
                if img_a:
                    code_a = scan_pos(img_a)
                    if code_a: 
                        check = supabase.table("productos").select("*, categorias(nombre), marcas(nombre)").eq("codigo_barras", code_a).execute()
                        if check.data:
                            st.error("⚠️ EL PRODUCTO YA EXISTE. Ve a la pestaña Inventario para sumar stock.")
                            st.session_state.cam_a_key += 1 
                        else:
                            st.session_state.iny_alm_cod = code_a
                            st.session_state.api_nombre_sugerido = fetch_upc_api(code_a) # API UPC
                            st.session_state.cam_a_key += 1; st.rerun() 
            
            cats, mars = load_data("categorias"), load_data("marcas")
            with st.form("form_nuevo", clear_on_submit=True):
                c_cod = st.text_input("Código de Barras", value=st.session_state.iny_alm_cod)
                c_nom = st.text_input("Nombre del Producto", value=st.session_state.api_nombre_sugerido)
                f1, f2, f3 = st.columns(3)
                f_cat = f1.selectbox("Categoría", cats['nombre'].tolist() if not cats.empty else ["Vacío"])
                f_mar = f2.selectbox("Marca", mars['nombre'].tolist() if not mars.empty else ["Vacío"])
                f_cal = f3.selectbox("Calidad", ["Genérico", "Original", "AAA", "Alta Gama"])
                f4, f5, f6, f7 = st.columns(4)
                f_costo = f4.number_input("Costo Compra (S/.)", min_value=0.0, step=0.5)
                f_pmin = f6.number_input("Precio Mín. (S/.)", min_value=0.0, step=0.5)
                f_venta = f5.number_input("Precio Venta (S/.)", min_value=0.0, step=0.5)
                f_stock = f7.number_input("Stock Inicial", min_value=1, step=1)
                
                if st.form_submit_button("🚀 GUARDAR PRODUCTO", type="primary"):
                    if c_cod and c_nom and not cats.empty and not mars.empty:
                        cid, mid = int(cats[cats['nombre'] == f_cat]['id'].iloc[0]), int(mars[mars['nombre'] == f_mar]['id'].iloc[0])
                        supabase.table("productos").insert({"codigo_barras": c_cod, "nombre": c_nom, "categoria_id": cid, "marca_id": mid, "calidad": f_cal, "costo_compra": f_costo, "precio_lista": f_venta, "precio_minimo": f_pmin, "stock_actual": f_stock, "stock_inicial": f_stock}).execute()
                        st.session_state.iny_alm_cod = ""; st.session_state.api_nombre_sugerido = ""; st.success("✅ Guardado."); time.sleep(1.5); st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.error("🚫 No tienes permisos para AGREGAR productos al inventario.")
    
    with t2:
        if "inventario_agregar" in st.session_state.user_perms:
            st.info("Desde aquí puedes configurar tus listas desplegables.")
        else:
            st.error("🚫 No tienes permisos para modificar configuraciones.")

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
                
                if "inventario_modificar" in st.session_state.user_perms:
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
# ⚠️ MÓDULO 4: MERMAS Y DAÑOS
# ==========================================
elif menu == "⚠️ MERMAS/DAÑOS" and "mermas" in st.session_state.user_perms:
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
                            supabase.table("mermas").insert({"usuario_id": st.session_state.user_id, "producto_id": m_cod, "cantidad": m_cant, "motivo": m_mot, "perdida_monetaria": p_merma['costo_compra'] * m_cant}).execute()
                            st.success("✅ Baja exitosa."); time.sleep(1.5); st.rerun()
        except: pass

# ==========================================
# 🧾 MÓDULO: REGISTRO DE TICKETS
# ==========================================
elif menu == "🧾 REGISTRO DE TICKETS" and "reportes" in st.session_state.user_perms:
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
                html_safe = html_raw.replace("<script>window.onload = function() { window.print(); }</script>", "")
                st.components.v1.html(html_safe, height=600, scrolling=True)
        else: st.info("No hay tickets emitidos aún.")
    except: st.error(ERROR_ADMIN)

# ==========================================
# 👥 MÓDULO NUEVO: GESTIÓN DE USUARIOS (SÓLO ADMIN)
# ==========================================
elif menu == "👥 GESTIÓN DE USUARIOS" and "gestion_usuarios" in st.session_state.user_perms:
    st.subheader("Panel de Control de Accesos y Roles (RBAC)")
    t_u1, t_u2 = st.tabs(["📋 Usuarios Activos", "➕ Crear Nuevo Usuario"])
    
    with t_u1:
        # Aquí traemos la columna 'clave' para que el administrador PUEDA VER LAS CONTRASEÑAS en texto plano.
        usrs = supabase.table("usuarios").select("id, nombre_completo, usuario, clave, turno, permisos, estado").execute()
        if usrs.data:
            df_u = pd.DataFrame(usrs.data)
            st.write("Visualización de Usuarios (Contraseñas Visibles para el Administrador)")
            st.dataframe(df_u[['id', 'nombre_completo', 'usuario', 'clave', 'turno', 'estado']], use_container_width=True)
            
            st.divider()
            st.write("#### 🔑 Actualizar Contraseña de un Usuario")
            with st.form("reset_pwd"):
                c_u = st.selectbox("Selecciona el Usuario:", df_u['usuario'].tolist())
                n_pwd = st.text_input("Escribe la Nueva Contraseña (Visible)")
                if st.form_submit_button("Actualizar Contraseña", type="primary"):
                    if n_pwd:
                        supabase.table("usuarios").update({"clave": n_pwd}).eq("usuario", c_u).execute()
                        st.success(f"✅ Contraseña actualizada correctamente para {c_u}.")
                        time.sleep(1); st.rerun()
                    else:
                        st.error("Debes ingresar una contraseña válida.")
        else: st.info("No hay usuarios.")
        
    with t_u2:
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        with st.form("form_new_user", clear_on_submit=True):
            n_nombre = st.text_input("Nombre Completo")
            n_user = st.text_input("Nombre de Usuario (Para Login)")
            # Guardamos la contraseña en formato visible
            n_pass = st.text_input("Contraseña de Acceso")
            n_turno = st.selectbox("Turno de Trabajo", ["Mañana", "Tarde", "Completo", "Rotativo"])
            
            st.write("#### Asignación de Permisos Dinámicos")
            lista_permisos = [
                "mermas", "inventario_ver", "inventario_agregar", "inventario_modificar", 
                "inventario_eliminar", "reportes", "cierre_caja", "gestion_usuarios"
            ]
            n_perms = st.multiselect("Selecciona los módulos a los que tendrá acceso:", lista_permisos)
            
            if st.form_submit_button("Crear Usuario Seguro", type="primary"):
                if n_nombre and n_user and n_pass:
                    try:
                        # Se guarda 'clave' en lugar del hash para que el admin pueda verla
                        supabase.table("usuarios").insert({
                            "nombre_completo": n_nombre, "usuario": n_user, "clave": n_pass,
                            "turno": n_turno, "permisos": json.dumps(n_perms)
                        }).execute()
                        st.success(f"✅ Usuario {n_user} creado con éxito.")
                        time.sleep(1.5); st.rerun()
                    except: st.error("❌ El nombre de usuario ya existe o hubo un error de conexión.")
                else: st.warning("Rellena todos los campos básicos.")
        st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 📊 MÓDULO 5: REPORTES Y CIERRE DE CAJA
# ==========================================
elif menu == "📊 REPORTES (CAJA)" and ("cierre_caja" in st.session_state.user_perms or "reportes" in st.session_state.user_perms):
    st.subheader("Auditoría Contable")
    
    if "reportes" in st.session_state.user_perms:
        st.write("#### 📈 Ventas Totales por Vendedor (Histórico Global)")
        try:
            v_hist = supabase.table("ventas_cabecera").select("total_venta, usuarios(nombre_completo)").execute()
            if v_hist.data:
                df_vh = pd.DataFrame(v_hist.data)
                df_vh['Vendedor'] = df_vh['usuarios'].apply(lambda x: x['nombre_completo'] if isinstance(x, dict) else 'Desconocido')
                df_agrupado = df_vh.groupby('Vendedor')['total_venta'].sum().reset_index()
                df_agrupado.columns = ['Vendedor', 'Total Recaudado (S/.)']
                st.dataframe(df_agrupado, use_container_width=True)
        except: pass
    
    st.divider()
    
    if "cierre_caja" in st.session_state.user_perms:
        st.write("#### 🛑 CORTAR CAJA Y GENERAR TICKET Z")
        try:
            try:
                c_db = supabase.table("cierres_caja").select("fecha_cierre").order("fecha_cierre", desc=True).limit(1).execute()
                last_cierre_dt = pd.to_datetime(c_db.data[0]['fecha_cierre'], utc=True) if c_db.data else pd.to_datetime("2000-01-01T00:00:00Z", utc=True)
            except: last_cierre_dt = pd.to_datetime("2000-01-01T00:00:00Z", utc=True)

            detalles = supabase.table("ventas_detalle").select("*, productos(costo_compra), ventas_cabecera(created_at)").execute()
            devs = supabase.table("devoluciones").select("*, productos(costo_compra)").execute()
            
            tot_ventas, tot_devs = 0.0, 0.0
            
            if detalles.data:
                df_rep = pd.DataFrame(detalles.data)
                df_rep['created_dt'] = pd.to_datetime(df_rep['ventas_cabecera'].apply(lambda x: x['created_at'] if isinstance(x, dict) else '2000-01-01'), utc=True)
                df_filt = df_rep[df_rep['created_dt'] > last_cierre_dt]
                tot_ventas = df_filt['subtotal'].sum() if not df_filt.empty else 0.0
                
            if devs.data:
                df_dev = pd.DataFrame(devs.data)
                df_dev['created_dt'] = pd.to_datetime(df_dev['created_at'], utc=True)
                df_dev_filt = df_dev[df_dev['created_dt'] > last_cierre_dt]
                tot_devs = df_dev_filt['dinero_devuelto'].sum() if not df_dev_filt.empty else 0.0
                
            caja_esperada = tot_ventas - tot_devs
            
            st.info(f"**Efectivo Neto Esperado en Caja:** S/. {caja_esperada:.2f}")
            
            with st.form("form_cierre", clear_on_submit=True):
                st.write("Al realizar el corte Z, los reportes se pondrán a S/. 0.00 y el Stock Actual se volverá el Stock Inicial.")
                if st.form_submit_button("🔒 APROBAR CIERRE DE CAJA DIRECTO", type="primary"):
                    supabase.table("cierres_caja").insert({"total_ventas": tot_ventas, "total_devoluciones": tot_devs}).execute()
                    prods_res = supabase.table("productos").select("codigo_barras, stock_actual").execute()
                    if prods_res.data:
                        for prod in prods_res.data:
                            supabase.table("productos").update({"stock_inicial": prod['stock_actual']}).eq("codigo_barras", prod['codigo_barras']).execute()
                    st.success("✅ Turno cerrado y caja limpiada exitosamente.")
                    time.sleep(2); st.rerun()
        except: st.error("Error al calcular el corte de caja.")
