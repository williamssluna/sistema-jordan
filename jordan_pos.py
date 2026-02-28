import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client
import pandas as pd
from datetime import datetime
import time
import requests
import json
import os

# ==========================================
# 1. CONEXIÓN AL CEREBRO DE BASE DE DATOS
# ==========================================
URL_SUPABASE = "https://degzltrjrzqbahdonmmb.supabase.co"
KEY_SUPABASE = "sb_publishable_td5_vXX42LYc8PlTAbBgVg_-xCp-94r"
supabase = create_client(URL_SUPABASE, KEY_SUPABASE)

st.set_page_config(page_title="JORDAN POS ERP", layout="wide", page_icon="📱")

ERROR_ADMIN = "🚨 Error del sistema. Contactar al administrador."

# ==========================================
# 2. SEGURIDAD Y REGLAS DE NEGOCIO
# ==========================================
def verify_password(input_password, stored_password):
    return input_password == stored_password

# ==========================================
# 3. DISEÑO VISUAL UX/UI (CSS MEJORADO)
# ==========================================
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    .main-header { font-size: 28px; font-weight: 900; color: #1e3a8a; text-align: center; padding: 20px; border-bottom: 4px solid #3b82f6; margin-bottom: 25px; background: white; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.05);}
    .css-card { background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border-left: 6px solid #3b82f6; margin-bottom: 20px; }
    
    .metric-box { background: linear-gradient(145deg, #ffffff 0%, #f1f5f9 100%); padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); text-align: center; border: 1px solid #e2e8f0; transition: transform 0.2s ease, box-shadow 0.2s ease; margin-bottom: 15px;}
    .metric-box:hover { transform: translateY(-5px); box-shadow: 0 10px 20px rgba(0,0,0,0.1); }
    .metric-title { font-size: 13px; color: #64748b; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;}
    .metric-value { font-size: 28px; font-weight: 900; color: #0f172a;}
    .metric-value-small { font-size: 20px; font-weight: 800; color: #0f172a;}
    .metric-green { color: #10b981; }
    .metric-red { color: #ef4444; }
    .metric-orange { color: #f59e0b; }
    .metric-blue { color: #3b82f6; }
    
    .qr-container { background: white; padding: 15px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); text-align: center; border: 2px dashed #3b82f6; margin-bottom: 15px;}
    .qr-amount { font-size: 32px; font-weight: 900; color: #1e3a8a; margin-bottom: 10px;}
    
    .ticket-termico { background: white; color: black; font-family: 'Courier New', monospace; padding: 15px; border: 1px dashed #333; width: 100%; max-width: 320px; margin: 0 auto; line-height: 1.3; font-size: 14px; }
    .linea-corte { text-align: center; margin: 25px 0; border-bottom: 2px dashed #94a3b8; line-height: 0.1em; color: #64748b; font-size: 12px; font-weight: bold;}
    .linea-corte span { background: #f8fafc; padding: 0 10px; }
    .stButton>button { border-radius: 8px; font-weight: bold; height: 3.5em; width: 100%; transition: all 0.2s;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 4. MEMORIA DEL SISTEMA Y ESTADO (SESSION)
# ==========================================
keys_to_init = {
    'logged_in': False, 'user_id': None, 'user_name': "", 'user_perms': [],
    'carrito': [], 'last_ticket_html': None, 'ticket_cierre': None,
    'api_nombre_sugerido': ""
}
for key, value in keys_to_init.items():
    if key not in st.session_state: st.session_state[key] = value

# ==========================================
# 5. FUNCIONES DE APOYO Y MOTOR PRINCIPAL
# ==========================================
def render_dashboard_cards(ventas, devoluciones, caja_neta, capital, mermas, utilidad):
    st.markdown("##### 💵 Balance Físico de Caja")
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"<div class='metric-box'><div class='metric-title'>Ventas Brutas</div><div class='metric-value'>S/. {ventas:.2f}</div></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='metric-box'><div class='metric-title'>Dinero Devuelto</div><div class='metric-value metric-red'>- S/. {devoluciones:.2f}</div></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='metric-box'><div class='metric-title'>CAJA NETA</div><div class='metric-value metric-green'>S/. {caja_neta:.2f}</div></div>", unsafe_allow_html=True)
    
    st.write("")
    st.markdown("##### 📈 Rendimiento Operativo (Utilidad)")
    c4, c5, c6 = st.columns(3)
    c4.markdown(f"<div class='metric-box'><div class='metric-title'>Capital Invertido (Costo)</div><div class='metric-value metric-orange'>S/. {capital:.2f}</div></div>", unsafe_allow_html=True)
    c5.markdown(f"<div class='metric-box'><div class='metric-title'>Mermas (Pérdidas)</div><div class='metric-value metric-red'>- S/. {mermas:.2f}</div></div>", unsafe_allow_html=True)
    c6.markdown(f"<div class='metric-box'><div class='metric-title'>UTILIDAD NETA PURA</div><div class='metric-value metric-green'>S/. {utilidad:.2f}</div></div>", unsafe_allow_html=True)

def get_last_cierre_dt():
    try:
        c_db = supabase.table("cierres_caja").select("fecha_cierre").order("fecha_cierre", desc=True).limit(1).execute()
        if c_db.data: return pd.to_datetime(c_db.data[0]['fecha_cierre'], utc=True)
    except: pass
    return pd.to_datetime("2000-01-01T00:00:00Z", utc=True)

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
    except Exception as e: st.error(f"Error de BD: {e}")
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

def get_qr_image_path():
    # Busca la imagen unificada qr_yape.png o .jpg (Servirá para Yape y Plin)
    extensions = ['.png', '.jpg', '.jpeg']
    for ext in extensions:
        path = f"qr_yape{ext}"
        if os.path.exists(path):
            return path
    return None

# ==========================================
# 6. ESTRUCTURA PRINCIPAL Y SIDEBAR (ERP)
# ==========================================
st.markdown('<div class="main-header">📱 ACCESORIOS JORDAN | SMART ERP</div>', unsafe_allow_html=True)

menu_options = ["🛒 VENTAS", "🔄 DEVOLUCIONES"]

st.sidebar.markdown("### 🏢 Control de Personal")

with st.sidebar.expander("⌚ Marcar Asistencia", expanded=False):
    with st.form("form_asistencia", clear_on_submit=True):
        usr_ast = st.text_input("Usuario")
        pwd_ast = st.text_input("Contraseña", type="password")
        c_a1, c_a2 = st.columns(2)
        btn_in = c_a1.form_submit_button("🟢 Entrada")
        btn_out = c_a2.form_submit_button("🔴 Salida")
        if btn_in or btn_out:
            if usr_ast and pwd_ast:
                try:
                    usr_data = supabase.table("usuarios").select("*").eq("usuario", usr_ast).execute()
                    if usr_data.data and verify_password(pwd_ast, usr_data.data[0].get('clave')):
                        tipo = "Ingreso" if btn_in else "Salida"
                        supabase.table("asistencia").insert({"usuario_id": usr_data.data[0]['id'], "tipo_marcacion": tipo}).execute()
                        st.success(f"✅ {tipo} registrado para {usr_data.data[0]['nombre_completo']}")
                    else:
                        st.error("❌ Usuario o Contraseña incorrectos.")
                except Exception as e:
                    st.error(f"❌ Error al registrar asistencia.")
            else:
                st.warning("⚠️ Ingresa tu usuario y contraseña.")

st.sidebar.divider()

if not st.session_state.logged_in:
    st.sidebar.markdown("#### 🔐 Acceso Administrativo")
    with st.sidebar.form("form_login"):
        l_usr = st.text_input("Usuario Administrador / Encargado")
        l_pwd = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Iniciar Sesión", type="primary"):
            try:
                usr_data = supabase.table("usuarios").select("*").eq("usuario", l_usr).execute()
                if usr_data.data and verify_password(l_pwd, usr_data.data[0].get('clave')):
                    st.session_state.logged_in = True
                    st.session_state.user_id = usr_data.data[0]['id']
                    st.session_state.user_name = usr_data.data[0]['nombre_completo']
                    st.session_state.user_perms = usr_data.data[0].get('permisos', [])
                    st.rerun()
                else: st.error("❌ Acceso Denegado.")
            except Exception as e: st.error("Error de conexión.")
else:
    st.sidebar.success(f"👤 Conectado: {st.session_state.user_name}")
    if st.sidebar.button("🚪 Cerrar Sesión Administrativa"):
        st.session_state.logged_in = False
        st.session_state.user_id = None
        st.session_state.user_perms = []
        st.rerun()

if st.session_state.logged_in:
    p = st.session_state.user_perms
    if "mermas" in p: menu_options.append("⚠️ MERMAS/DAÑOS")
    if "inventario_ver" in p: menu_options.append("📦 ALMACÉN")
    if "reportes" in p: menu_options.append("🧾 TICKETS")
    if "cierre_caja" in p or "reportes" in p: menu_options.append("📊 REPORTES")
    if "gestion_usuarios" in p: menu_options.append("👥 USUARIOS")

menu = st.sidebar.radio("Navegación", menu_options)

# ==========================================
# 🛒 MÓDULO 1: VENTAS 
# ==========================================
if menu == "🛒 VENTAS":
    if st.session_state.last_ticket_html:
        components.html(st.session_state.last_ticket_html, width=0, height=0)
        st.success("🖨️ Imprimiendo ticket térmico doble...")
        st.session_state.last_ticket_html = None 

    col_v1, col_v2 = st.columns([1.5, 1.4])
    with col_v1:
        st.subheader("🔍 Ingreso Rápido (Láser o Teclado)")
        with st.form("form_manual_barcode", clear_on_submit=True):
            st.info("👇 Haz clic en la casilla de abajo y dispara el lector láser.")
            col_mb1, col_mb2 = st.columns([3, 1])
            manual_code = col_mb1.text_input("Código Numérico", key="codigo_venta_laser")
            add_manual = col_mb2.form_submit_button("➕ Procesar")
            if add_manual and manual_code:
                if procesar_codigo_venta(manual_code): time.sleep(0.5); st.rerun()

        st.divider()
        st.write("Búsqueda Manual (Si no hay código de barras)")
        search = st.text_input("Escribe el Nombre del Producto")
        if search:
            try:
                res_s = supabase.table("productos").select("*, marcas(nombre)").ilike("nombre", f"%{search}%").execute()
                if res_s.data:
                    for p in res_s.data:
                        c_p1, c_p2, c_p3 = st.columns([3, 1, 1])
                        compat = p.get('compatibilidad', 'Universal')
                        c_p1.write(f"**{p['nombre']}** ({compat}) - Stock: {p['stock_actual']}")
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
            
            lista_vendedores = get_lista_usuarios()
            vendedor_opciones = {v['usuario']: v['id'] for v in lista_vendedores}
            vendedor_seleccionado = st.selectbox("👤 Tu usuario (Vendedor):", ["Seleccionar..."] + list(vendedor_opciones.keys()))
            
            pago = st.selectbox("Medio de Pago", ["Efectivo", "Yape", "Plin", "Tarjeta VISA/MC"])
            
            # --- QR UNIFICADO ESTÁTICO ---
            ref_pago = ""
            if pago in ["Yape", "Plin"]:
                st.markdown(f"""
                <div class="qr-container">
                    <div>Muéstrale la pantalla al cliente para el pago:</div>
                    <div class="qr-amount">S/. {total_venta:.2f}</div>
                </div>
                """, unsafe_allow_html=True)
                
                qr_path = get_qr_image_path()
                col_q1, col_q2, col_q3 = st.columns([1,2,1])
                with col_q2:
                    if qr_path:
                        st.image(qr_path, use_container_width=True)
                    else:
                        st.info("ℹ️ Sube la imagen 'qr_yape.png' a GitHub y aparecerá aquí automáticamente para Yape y Plin.")
                
                ref_pago = st.text_input("📱 Número de Aprobación (Obligatorio)")
                
            elif pago == "Tarjeta VISA/MC":
                ref_pago = st.text_input("💳 N° de Referencia del Equipo (Obligatorio)")
            
            if st.button("🏁 PROCESAR VENTA", type="primary"):
                if vendedor_seleccionado == "Seleccionar...":
                    st.error("🛑 Selecciona tu usuario primero.")
                elif pago in ["Yape", "Plin", "Tarjeta VISA/MC"] and not ref_pago:
                    st.error(f"🛑 Ingresa la referencia del pago.")
                else:
                    try:
                        vendedor_id = vendedor_opciones[vendedor_seleccionado]
                        t_num = f"AJ-{int(time.time())}"
                        
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
                        
                        fecha_tk = datetime.now().strftime('%d/%m/%Y %H:%M')
                        cuerpo_base = f"""--------------------------------<br>
TICKET: {t_num}<br>
FECHA: {fecha_tk}<br>
CAJERO: {vendedor_seleccionado}<br>
--------------------------------<br>
{items_html}--------------------------------<br>
<b>TOTAL PAGADO: S/. {total_venta:.2f}</b><br>
MÉTODO: {pago} {f'(Ref: {ref_pago})' if ref_pago else ''}<br>
--------------------------------<br>"""
                        
                        ticket_dual_html = f"""<div class="ticket-termico">
<center><b>ACCESORIOS JORDAN</b></center>
<center><b>COPIA CLIENTE</b></center><br>
{cuerpo_base}
<center>¡Gracias por su compra!</center>
</div>
<div class="linea-corte"><span>✂️ CORTAR AQUÍ ✂️</span></div>
<div class="ticket-termico">
<center><b>ACCESORIOS JORDAN</b></center>
<center><b>COPIA CONTROL INTERNO</b></center><br>
{cuerpo_base}
<center>Registro de caja</center>
</div>
<script>window.onload = function() {{ window.print(); }}</script>"""
                        
                        supabase.table("ticket_historial").insert({"ticket_numero": t_num, "usuario_id": vendedor_id, "html_payload": ticket_dual_html}).execute()
                        st.session_state.last_ticket_html = ticket_dual_html
                        st.session_state.carrito = []
                        st.rerun() 
                    except Exception as e: st.error(f"🚨 Error crítico al procesar la venta: {e}")

        if st.session_state.last_ticket_html:
            st.success("✅ Venta procesada exitosamente. Aquí están los tickets.")
            st.markdown(st.session_state.last_ticket_html.replace("<script>window.onload = function() { window.print(); }</script>", ""), unsafe_allow_html=True)
            if st.button("🧹 Limpiar Pantalla (Nuevo Cliente)", type="primary"):
                st.session_state.last_ticket_html = None
                st.rerun()

# ==========================================
# 🔄 MÓDULO 3: DEVOLUCIONES
# ==========================================
elif menu == "🔄 DEVOLUCIONES":
    st.subheader("Gestión de Devoluciones")
    st.info("Usa el lector láser para apuntar al código de barras del producto devuelto.")
    search_dev = st.text_input("Código de Barras o N° de Ticket")
    lista_vendedores = get_lista_usuarios()
    vendedor_opciones = {v['usuario']: v['id'] for v in lista_vendedores}
    
    if search_dev:
        if "AJ-" in search_dev.upper():
            try:
                v_cab = supabase.table("ventas_cabecera").select("*").eq("ticket_numero", search_dev.upper()).execute()
                if v_cab.data:
                    st.success(f"✅ Ticket: Pago: {v_cab.data[0]['metodo_pago']}")
                    v_det = supabase.table("ventas_detalle").select("*, productos(nombre)").eq("venta_id", v_cab.data[0]['id']).execute()
                    vendedor_sel = st.selectbox("👤 Usuario que autoriza:", ["..."] + list(vendedor_opciones.keys()))
                    for d in v_det.data:
                        col_d1, col_d2 = st.columns([3, 1])
                        col_d1.write(f"**{d['productos']['nombre']}** - Compró: {d['cantidad']} ud.")
                        if col_d2.button("Devolver", key=f"dev_{d['id']}"):
                            if vendedor_sel != "...":
                                p_s = supabase.table("productos").select("stock_actual").eq("codigo_barras", d['producto_id']).execute()
                                supabase.table("productos").update({"stock_actual": p_s.data[0]['stock_actual'] + d['cantidad']}).eq("codigo_barras", d['producto_id']).execute()
                                supabase.table("devoluciones").insert({"usuario_id": vendedor_opciones[vendedor_sel], "producto_id": d['producto_id'], "cantidad": d['cantidad'], "motivo": "Devolución Ticket", "dinero_devuelto": d['subtotal'], "estado_producto": "Vuelve a tienda"}).execute()
                                st.success("✅ Devuelto."); time.sleep(1); st.rerun()
                            else: st.error("Selecciona usuario.")
            except: pass
        else:
            try:
                p_db = supabase.table("productos").select("*").eq("codigo_barras", search_dev).execute()
                if p_db.data:
                    p = p_db.data[0]
                    with st.form("form_dev_libre"):
                        vendedor_sel = st.selectbox("👤 Usuario que autoriza:", ["..."] + list(vendedor_opciones.keys()))
                        c1, c2 = st.columns(2)
                        d_cant = c1.number_input("Cantidad", min_value=1, step=1)
                        d_dinero = c2.number_input("Dinero devuelto UND (S/.)", value=float(p['precio_lista']))
                        m_dev = st.text_input("Motivo")
                        if st.form_submit_button("🔁 DEVOLVER"):
                            if m_dev and vendedor_sel != "...":
                                supabase.table("productos").update({"stock_actual": p['stock_actual'] + d_cant}).eq("codigo_barras", p['codigo_barras']).execute()
                                supabase.table("devoluciones").insert({"usuario_id": vendedor_opciones[vendedor_sel], "producto_id": p['codigo_barras'], "cantidad": d_cant, "motivo": m_dev, "dinero_devuelto": d_cant * d_dinero, "estado_producto": "Vuelve a tienda"}).execute()
                                st.success("✅ Devuelto."); time.sleep(1); st.rerun()
                            else: st.error("Falta motivo o usuario.")
            except: pass

# ==========================================
# 📦 MÓDULO 2: ALMACÉN
# ==========================================
elif menu == "📦 ALMACÉN" and "inventario_ver" in st.session_state.user_perms:
    st.subheader("Gestión de Inventario Maestro")
    t1, t2, t3 = st.tabs(["➕ Ingreso Mercadería", "⚙️ Configuración Catálogos", "📋 Inventario General"])
    
    with t1:
        if "inventario_agregar" in st.session_state.user_perms:
            st.markdown('<div class="css-card">', unsafe_allow_html=True)
            st.info("👇 Haz clic en la casilla de abajo y dispara el lector láser para ingresar mercadería.")
            with st.form("form_nuevo_trigger", clear_on_submit=False):
                col_a1, col_a2 = st.columns([3, 1])
                code_a = col_a1.text_input("Dispara el Láser Aquí", key="trigger_almacen")
                if col_a2.form_submit_button("🔍 Cargar Código"):
                    if code_a:
                        check = supabase.table("productos").select("*").eq("codigo_barras", code_a).execute()
                        if check.data:
                            st.error("⚠️ EL PRODUCTO YA EXISTE. Ve a la pestaña Inventario para sumar stock.")
                        else:
                            st.session_state.iny_alm_cod = code_a
                            st.session_state.api_nombre_sugerido = fetch_upc_api(code_a)
            
            cats, mars = load_data("categorias"), load_data("marcas")
            with st.form("form_nuevo", clear_on_submit=True):
                c_cod = st.text_input("Código de Barras Registrado", value=st.session_state.iny_alm_cod)
                c_nom = st.text_input("Nombre del Producto", value=st.session_state.api_nombre_sugerido)
                f1, f2, f3, f8 = st.columns(4)
                f_cat = f1.selectbox("Categoría", cats['nombre'].tolist() if not cats.empty else ["Vacío"])
                f_mar = f2.selectbox("Marca", mars['nombre'].tolist() if not mars.empty else ["Vacío"])
                f_cal = f3.selectbox("Calidad", ["Original", "Genérico", "AAA", "Premium", "OEM"])
                
                opciones_comp = ["Universal", "iPhone", "Samsung", "Xiaomi", "Motorola", "Huawei", "Honor", "Oppo", "Otro"]
                f_comp = f8.selectbox("Compatibilidad", opciones_comp)
                
                f4, f5, f6, f7 = st.columns(4)
                f_costo = f4.number_input("Costo Compra (S/.)", min_value=0.0, step=0.5)
                f_pmin = f6.number_input("Precio Mín. (S/.)", min_value=0.0, step=0.5)
                f_venta = f5.number_input("Precio Venta (S/.)", min_value=0.0, step=0.5)
                f_stock = f7.number_input("Stock Inicial", min_value=1, step=1)
                
                if st.form_submit_button("🚀 GUARDAR EN BASE DE DATOS", type="primary"):
                    if c_cod and c_nom and not cats.empty and not mars.empty:
                        cid, mid = int(cats[cats['nombre'] == f_cat]['id'].iloc[0]), int(mars[mars['nombre'] == f_mar]['id'].iloc[0])
                        supabase.table("productos").insert({"codigo_barras": c_cod, "nombre": c_nom, "categoria_id": cid, "marca_id": mid, "calidad": f_cal, "compatibilidad": f_comp, "costo_compra": f_costo, "precio_lista": f_venta, "precio_minimo": f_pmin, "stock_actual": f_stock, "stock_inicial": f_stock}).execute()
                        st.session_state.iny_alm_cod = ""; st.session_state.api_nombre_sugerido = ""; st.success("✅ Guardado."); time.sleep(1.5); st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        else: st.error("🚫 No tienes permisos.")
    
    with t2:
        if "inventario_agregar" in st.session_state.user_perms or "inventario_modificar" in st.session_state.user_perms:
            st.write("### Catálogos del Sistema")
            st.info("Agrega las marcas y categorías necesarias (ej. Categorías: Fundas, Cargadores, Audífonos, Micas).")
            c_left, c_right = st.columns(2)
            with c_left:
                st.markdown('<div class="css-card">', unsafe_allow_html=True)
                st.write("#### 📂 Categorías")
                with st.form("f_cat", clear_on_submit=True):
                    new_c = st.text_input("Crear Categoría")
                    if st.form_submit_button("➕ Guardar", type="primary") and new_c: 
                        supabase.table("categorias").insert({"nombre": new_c}).execute(); st.rerun()
                cats_df = load_data("categorias")
                if not cats_df.empty:
                    del_c = st.selectbox("Eliminar Categoría", ["..."] + cats_df['nombre'].tolist())
                    if st.button("🗑️ Borrar", key="b_c") and del_c != "...": 
                        supabase.table("categorias").delete().eq("nombre", del_c).execute(); st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
            with c_right:
                st.markdown('<div class="css-card">', unsafe_allow_html=True)
                st.write("#### ®️ Marcas")
                with st.form("f_mar", clear_on_submit=True):
                    new_m = st.text_input("Crear Marca")
                    if st.form_submit_button("➕ Guardar", type="primary") and new_m: 
                        supabase.table("marcas").insert({"nombre": new_m}).execute(); st.rerun()
                mars_df = load_data("marcas")
                if not mars_df.empty:
                    del_m = st.selectbox("Eliminar Marca", ["..."] + mars_df['nombre'].tolist())
                    if st.button("🗑️ Borrar", key="b_m") and del_m != "...": 
                        supabase.table("marcas").delete().eq("nombre", del_m).execute(); st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
        else: st.error("🚫 Sin permisos.")

    with t3:
        try:
            prods = supabase.table("productos").select("*, categorias(nombre), marcas(nombre)").execute()
            if prods.data: 
                df = pd.DataFrame(prods.data)
                df['Categoría'] = df['categorias'].apply(lambda x: x['nombre'] if isinstance(x, dict) else 'N/A')
                df['Marca'] = df['marcas'].apply(lambda x: x['nombre'] if isinstance(x, dict) else 'N/A')
                if 'compatibilidad' not in df.columns: df['compatibilidad'] = 'Universal'
                df['stock_inicial'] = df.apply(lambda row: row.get('stock_inicial') if pd.notnull(row.get('stock_inicial')) else row['stock_actual'], axis=1)
                
                if "inventario_modificar" in st.session_state.user_perms:
                    st.write("### ⚡ Reabastecimiento Rápido")
                    with st.form("form_add_stock", clear_on_submit=True):
                        col_r1, col_r2 = st.columns([3, 1])
                        selected_prod = col_r1.selectbox("Seleccionar producto:", ["..."] + [f"{row['codigo_barras']} - {row['nombre']} (Stock Act: {row['stock_actual']})" for idx, row in df.iterrows()])
                        add_stock = col_r2.number_input("Cantidad que llegó", min_value=1, step=1)
                        if st.form_submit_button("➕ Sumar Stock", type="primary"):
                            if selected_prod != "...":
                                cod_up = selected_prod.split(" - ")[0]
                                c_stk, c_ini = int(df[df['codigo_barras'] == cod_up]['stock_actual'].iloc[0]), int(df[df['codigo_barras'] == cod_up]['stock_inicial'].iloc[0])
                                supabase.table("productos").update({"stock_actual": c_stk + add_stock, "stock_inicial": c_ini + add_stock}).eq("codigo_barras", cod_up).execute()
                                st.success("✅ Actualizado."); time.sleep(0.5); st.rerun() 
                
                st.divider()
                df_show = df[['codigo_barras', 'nombre', 'Categoría', 'Marca', 'compatibilidad', 'stock_inicial', 'stock_actual', 'costo_compra', 'precio_lista']]
                st.dataframe(df_show, use_container_width=True)
        except: pass

# ==========================================
# ⚠️ MÓDULO 4: MERMAS
# ==========================================
elif menu == "⚠️ MERMAS/DAÑOS" and "mermas" in st.session_state.user_perms:
    st.subheader("Dar de Baja Productos Dañados")
    m_cod = st.text_input("Código de Barras (Dispara láser)")
    if m_cod:
        try:
            p_inf = supabase.table("productos").select("*").eq("codigo_barras", m_cod).execute()
            if p_inf.data:
                p_merma = p_inf.data[0]
                with st.form("form_merma"):
                    m_cant = st.number_input("Cantidad a botar", min_value=1, max_value=int(p_merma['stock_actual']) if p_merma['stock_actual']>0 else 1)
                    m_mot = st.selectbox("Motivo", ["Roto al instalar", "Falla de Fábrica", "Robo/Extravío"])
                    if st.form_submit_button("⚠️ CONFIRMAR PÉRDIDA"):
                        if p_merma['stock_actual'] >= m_cant:
                            supabase.table("productos").update({"stock_actual": p_merma['stock_actual'] - m_cant}).eq("codigo_barras", m_cod).execute()
                            supabase.table("mermas").insert({"usuario_id": st.session_state.user_id, "producto_id": m_cod, "cantidad": m_cant, "motivo": m_mot, "perdida_monetaria": p_merma['costo_compra'] * m_cant}).execute()
                            st.success("✅ Baja exitosa."); time.sleep(1); st.rerun()
        except: pass

# ==========================================
# 🧾 MÓDULO: REGISTRO DE TICKETS
# ==========================================
elif menu == "🧾 TICKETS" and "reportes" in st.session_state.user_perms:
    st.subheader("Historial de Comprobantes Emitidos")
    try:
        tks = supabase.table("ticket_historial").select("ticket_numero, fecha, html_payload").order("fecha", desc=True).limit(50).execute()
        if tks.data:
            df_tks = pd.DataFrame(tks.data)
            df_tks['fecha_format'] = pd.to_datetime(df_tks['fecha']).dt.strftime('%d/%m/%Y %H:%M')
            opciones = [f"{row['ticket_numero']} - {row['fecha_format']}" for _, row in df_tks.iterrows()]
            sel_tk = st.selectbox("Selecciona un ticket", opciones)
            if sel_tk:
                tk_num = sel_tk.split(" - ")[0]
                html_raw = df_tks[df_tks['ticket_numero'] == tk_num]['html_payload'].iloc[0]
                st.markdown(html_raw.replace("<script>window.onload = function() { window.print(); }</script>", ""), unsafe_allow_html=True)
    except: pass

# ==========================================
# 👥 MÓDULO: GESTIÓN DE USUARIOS (RRHH)
# ==========================================
elif menu == "👥 USUARIOS" and "gestion_usuarios" in st.session_state.user_perms:
    st.subheader("Panel de Control Gerencial (RRHH)")
    t_u1, t_u2, t_u3, t_u4 = st.tabs(["📋 Usuarios", "➕ Crear Nuevo", "⚙️ Permisos", "📊 Dashboard Vendedores"])
    
    with t_u1:
        usrs = supabase.table("usuarios").select("id, nombre_completo, usuario, clave, turno, permisos").execute()
        if usrs.data:
            df_u = pd.DataFrame(usrs.data)
            df_u['permisos'] = df_u['permisos'].apply(lambda x: ", ".join(x) if isinstance(x, list) else str(x))
            st.dataframe(df_u[['id', 'nombre_completo', 'usuario', 'clave', 'turno', 'permisos']], use_container_width=True)
            
    with t_u2:
        with st.form("form_new_user", clear_on_submit=True):
            n_nombre = st.text_input("Nombre Completo")
            n_user = st.text_input("Usuario (Login)")
            n_pass = st.text_input("Contraseña")
            n_turno = st.selectbox("Turno", ["Mañana", "Tarde", "Completo", "Rotativo"])
            n_perms = st.multiselect("Permisos:", ["mermas", "inventario_ver", "inventario_agregar", "inventario_modificar", "inventario_eliminar", "reportes", "cierre_caja", "gestion_usuarios"])
            if st.form_submit_button("Crear Usuario", type="primary"):
                if n_nombre and n_user and n_pass:
                    supabase.table("usuarios").insert({"nombre_completo": n_nombre, "usuario": n_user, "clave": n_pass, "turno": n_turno, "permisos": n_perms}).execute()
                    st.success("✅ Creado."); time.sleep(1); st.rerun()

    with t_u3:
        if usrs.data:
            user_to_edit = st.selectbox("Seleccionar usuario a editar:", df_u['usuario'].tolist())
            raw_perms = supabase.table("usuarios").select("permisos").eq("usuario", user_to_edit).execute().data[0]['permisos']
            curr_perms = raw_perms if isinstance(raw_perms, list) else []
            with st.form("form_edit_perms"):
                lista_permisos = ["mermas", "inventario_ver", "inventario_agregar", "inventario_modificar", "inventario_eliminar", "reportes", "cierre_caja", "gestion_usuarios"]
                valid_curr = [p for p in curr_perms if p in lista_permisos]
                new_perms = st.multiselect("Permisos Asignados (Borra o agrega):", lista_permisos, default=valid_curr)
                if st.form_submit_button("💾 Guardar Permisos", type="primary"):
                    supabase.table("usuarios").update({"permisos": new_perms}).eq("usuario", user_to_edit).execute()
                    st.success("✅ Actualizado."); time.sleep(1); st.rerun()

    with t_u4:
        st.write("#### 🎯 Análisis de Rendimiento y Asistencia")
        if usrs.data:
            sel_u_nombre = st.selectbox("Selecciona un vendedor para analizar:", df_u['nombre_completo'].tolist())
            sel_u_id = df_u[df_u['nombre_completo'] == sel_u_nombre]['id'].iloc[0]
            
            try:
                today_date = datetime.now().date()
                curr_month = datetime.now().month
                
                ast_db = supabase.table("asistencia").select("*").eq("usuario_id", sel_u_id).execute()
                df_a = pd.DataFrame(ast_db.data)
                h_in, h_out, hrs_hoy, dias_mes, hrs_mes = "--:--", "--:--", 0.0, 0, 0.0
                
                if not df_a.empty:
                    df_a['ts'] = pd.to_datetime(df_a['timestamp']).dt.tz_convert('America/Lima')
                    df_a['date'] = df_a['ts'].dt.date
                    df_a['month'] = df_a['ts'].dt.month
                    
                    df_hoy = df_a[df_a['date'] == today_date]
                    if not df_hoy.empty:
                        i_ts = df_hoy[df_hoy['tipo_marcacion'] == 'Ingreso']['ts']
                        s_ts = df_hoy[df_hoy['tipo_marcacion'] == 'Salida']['ts']
                        if not i_ts.empty: h_in = i_ts.min().strftime('%I:%M %p')
                        if not s_ts.empty: h_out = s_ts.max().strftime('%I:%M %p')
                        if not i_ts.empty and not s_ts.empty:
                            hrs_hoy = (s_ts.max() - i_ts.min()).total_seconds() / 3600
                    
                    df_mes = df_a[df_a['month'] == curr_month]
                    if not df_mes.empty:
                        dias_mes = df_mes['date'].nunique()
                        for d, grp in df_mes.groupby('date'):
                            i_ts = grp[grp['tipo_marcacion'] == 'Ingreso']['ts']
                            s_ts = grp[grp['tipo_marcacion'] == 'Salida']['ts']
                            if not i_ts.empty and not s_ts.empty:
                                hrs_mes += (s_ts.max() - i_ts.min()).total_seconds() / 3600

                v_db = supabase.table("ventas_cabecera").select("total_venta, created_at").eq("usuario_id", sel_u_id).execute()
                df_v = pd.DataFrame(v_db.data)
                v_hoy, v_mes = 0.0, 0.0
                if not df_v.empty:
                    df_v['ts'] = pd.to_datetime(df_v['created_at']).dt.tz_convert('America/Lima')
                    df_v['date'] = df_v['ts'].dt.date
                    df_v['month'] = df_v['ts'].dt.month
                    v_hoy = df_v[df_v['date'] == today_date]['total_venta'].sum()
                    v_mes = df_v[df_v['month'] == curr_month]['total_venta'].sum()
                
                st.markdown(f"**Métricas del Día (Hoy)**")
                c1, c2, c3, c4 = st.columns(4)
                c1.markdown(f"<div class='metric-box'><div class='metric-title'>Hora Entrada</div><div class='metric-value-small'>{h_in}</div></div>", unsafe_allow_html=True)
                c2.markdown(f"<div class='metric-box'><div class='metric-title'>Hora Salida</div><div class='metric-value-small'>{h_out}</div></div>", unsafe_allow_html=True)
                c3.markdown(f"<div class='metric-box'><div class='metric-title'>Horas Trabajadas</div><div class='metric-value-small'>{hrs_hoy:.1f} Hrs</div></div>", unsafe_allow_html=True)
                c4.markdown(f"<div class='metric-box'><div class='metric-title'>Ventas Hoy</div><div class='metric-value-small metric-green'>S/. {v_hoy:.2f}</div></div>", unsafe_allow_html=True)
                
                st.markdown(f"**Acumulado del Mes Actual**")
                c5, c6, c7 = st.columns(3)
                c5.markdown(f"<div class='metric-box'><div class='metric-title'>Días Asistidos</div><div class='metric-value-small'>{dias_mes} Días</div></div>", unsafe_allow_html=True)
                c6.markdown(f"<div class='metric-box'><div class='metric-title'>Horas Totales</div><div class='metric-value-small'>{hrs_mes:.1f} Hrs</div></div>", unsafe_allow_html=True)
                c7.markdown(f"<div class='metric-box'><div class='metric-title'>Total Recaudado</div><div class='metric-value-small metric-blue'>S/. {v_mes:.2f}</div></div>", unsafe_allow_html=True)
            except: st.info("Generando cálculos...")

# ==========================================
# 📊 MÓDULO 5: REPORTES Y CIERRE DE CAJA
# ==========================================
elif menu == "📊 REPORTES" and ("cierre_caja" in st.session_state.user_perms or "reportes" in st.session_state.user_perms):
    st.subheader("Auditoría Financiera y Cierre")
    
    if st.session_state.ticket_cierre:
        tk = st.session_state.ticket_cierre
        st.success("✅ Caja cerrada. Visualización reseteada a 0.")
        ticket_z_html = f"""
        <div class="ticket-termico">
            <center><b>ACCESORIOS JORDAN</b></center>
            <center><b>REPORTE Z (FIN DE TURNO)</b></center>
            --------------------------------<br>
            FECHA CIERRE: {tk['fecha']}<br>
            CAJERO RESPONSABLE: {st.session_state.user_name}<br>
            --------------------------------<br>
            <b>💰 VENTAS Y COSTOS:</b><br>
            Ingresos Brutos: S/. {tk['tot_ventas']:.2f}<br>
            Capital Invertido: S/. {tk['capital_inv']:.2f}<br>
            Cant. Vendida: {tk['cant_vendida']} ud.<br>
            --------------------------------<br>
            <b>🔄 DEVOLUCIONES:</b><br>
            Dinero Reembolsado: S/. {tk['tot_dev']:.2f}<br>
            Cant. Devuelta: {tk['cant_devuelta']} ud.<br>
            --------------------------------<br>
            <b>⚠️ MERMAS (DAÑOS):</b><br>
            Pérdida de Capital: S/. {tk['tot_merma']:.2f}<br>
            Cant. Mermada: {tk['cant_merma']} ud.<br>
            --------------------------------<br>
            <b>🏦 CUADRE DE EFECTIVO FINAL:</b><br>
            EFECTIVO EN CAJA: S/. {tk['caja_neta']:.2f}<br>
            UTILIDAD NETA PURA: S/. {tk['utilidad']:.2f}<br>
            --------------------------------<br>
            <center>Corte finalizado. Stock Actualizado.</center>
        </div>
        """
        st.markdown(ticket_z_html, unsafe_allow_html=True)
        if st.button("🧹 Iniciar Nuevo Turno", type="primary"):
            st.session_state.ticket_cierre = None
            st.rerun()

    else:
        try:
            last_cierre_dt = get_last_cierre_dt()
            st.caption(f"⏱️ Monitoreando operaciones desde: {last_cierre_dt.strftime('%d/%m/%Y %H:%M')}")

            detalles = supabase.table("ventas_detalle").select("*, productos(costo_compra), ventas_cabecera(created_at, usuario_id)").execute()
            devs = supabase.table("devoluciones").select("*, productos(costo_compra)").execute()
            mermas = supabase.table("mermas").select("*").execute()
            usuarios_db = supabase.table("usuarios").select("id, nombre_completo").execute()
            user_dict = {u['id']: u['nombre_completo'] for u in usuarios_db.data} if usuarios_db.data else {}
            
            tot_ventas, tot_costo, tot_devs, costo_recup, tot_merma = 0.0, 0.0, 0.0, 0.0, 0.0
            cant_ven, cant_dev, cant_mer = 0, 0, 0
            df_rep_filtered = pd.DataFrame()
            
            if detalles.data:
                df_rep = pd.DataFrame(detalles.data)
                df_rep['created_dt'] = pd.to_datetime(df_rep['ventas_cabecera'].apply(lambda x: x['created_at'] if isinstance(x, dict) else '2000-01-01'), utc=True)
                df_rep_filtered = df_rep[df_rep['created_dt'] > last_cierre_dt]
                if not df_rep_filtered.empty:
                    df_rep_filtered['Costo'] = df_rep_filtered['productos'].apply(lambda x: float(x['costo_compra']) if isinstance(x, dict) else 0.0) * df_rep_filtered['cantidad']
                    tot_ventas = df_rep_filtered['subtotal'].sum()
                    tot_costo = df_rep_filtered['Costo'].sum()
                    cant_ven = int(df_rep_filtered['cantidad'].sum())
                    df_rep_filtered['Vendedor'] = df_rep_filtered['ventas_cabecera'].apply(lambda x: user_dict.get(x.get('usuario_id'), 'Desconocido') if isinstance(x, dict) else 'Desconocido')
                
            if devs.data:
                df_dev = pd.DataFrame(devs.data)
                df_dev['created_dt'] = pd.to_datetime(df_dev['created_at'], utc=True)
                df_dev_filt = df_dev[df_dev['created_dt'] > last_cierre_dt]
                if not df_dev_filt.empty:
                    df_dev_filt['Costo'] = df_dev_filt['productos'].apply(lambda x: float(x['costo_compra']) if isinstance(x, dict) else 0.0) * df_dev_filt['cantidad']
                    tot_devs = df_dev_filt['dinero_devuelto'].sum()
                    costo_recup = df_dev_filt['Costo'].sum()
                    cant_dev = int(df_dev_filt['cantidad'].sum())

            if mermas.data:
                df_mer = pd.DataFrame(mermas.data)
                df_mer['created_dt'] = pd.to_datetime(df_mer['created_at'], utc=True)
                df_mer_filt = df_mer[df_mer['created_dt'] > last_cierre_dt]
                if not df_mer_filt.empty:
                    tot_merma = df_mer_filt['perdida_monetaria'].sum()
                    cant_mer = int(df_mer_filt['cantidad'].sum())
                
            caja_esperada = tot_ventas - tot_devs
            capital_real = tot_costo - costo_recup
            utilidad_pura = caja_esperada - capital_real - tot_merma
            
            if "reportes" in st.session_state.user_perms:
                tab_gen, tab_ven = st.tabs(["📊 Resumen General del Turno", "👤 Rendimiento por Vendedor"])
                
                with tab_gen:
                    render_dashboard_cards(tot_ventas, tot_devs, caja_esperada, capital_real, tot_merma, utilidad_pura)
                
                with tab_ven:
                    st.write("Selecciona un vendedor para ver sus métricas exactas del turno actual:")
                    if not df_rep_filtered.empty:
                        vendedores_activos = df_rep_filtered['Vendedor'].unique()
                        sel_v = st.selectbox("Vendedor:", vendedores_activos)
                        
                        df_v_ventas = df_rep_filtered[df_rep_filtered['Vendedor'] == sel_v]
                        v_ventas = df_v_ventas['subtotal'].sum()
                        v_costo = df_v_ventas['Costo'].sum()
                        v_utilidad = v_ventas - v_costo
                        
                        c1, c2, c3 = st.columns(3)
                        c1.markdown(f"<div class='metric-box'><div class='metric-title'>Ventas de {sel_v}</div><div class='metric-value'>S/. {v_ventas:.2f}</div></div>", unsafe_allow_html=True)
                        c2.markdown(f"<div class='metric-box'><div class='metric-title'>Costo Mercadería</div><div class='metric-value metric-orange'>- S/. {v_costo:.2f}</div></div>", unsafe_allow_html=True)
                        c3.markdown(f"<div class='metric-box'><div class='metric-title'>Ganancia (Utilidad)</div><div class='metric-value metric-green'>S/. {v_utilidad:.2f}</div></div>", unsafe_allow_html=True)
                    else: st.info("No hay ventas registradas en este turno.")
                    
            st.divider()
            
            if "cierre_caja" in st.session_state.user_perms:
                st.markdown('<div class="cierre-box">', unsafe_allow_html=True)
                st.write("### 🛑 EJECUTAR CIERRE DE CAJA (FIN DE TURNO)")
                with st.form("form_cierre", clear_on_submit=True):
                    st.write("Al realizar el corte Z, los reportes visuales se pondrán a S/. 0.00 y tu Stock Actual se convertirá automáticamente en tu nuevo Stock Inicial.")
                    if st.form_submit_button("🔒 APROBAR CIERRE DE CAJA DIRECTO", type="primary"):
                        supabase.table("cierres_caja").insert({"total_ventas": tot_ventas, "total_devoluciones": tot_devs, "utilidad": utilidad_pura, "total_mermas": tot_merma}).execute()
                        
                        prods_res = supabase.table("productos").select("codigo_barras, stock_actual").execute()
                        if prods_res.data:
                            for prod in prods_res.data:
                                supabase.table("productos").update({"stock_inicial": prod['stock_actual']}).eq("codigo_barras", prod['codigo_barras']).execute()
                        
                        st.session_state.ticket_cierre = {
                            'fecha': datetime.now().strftime('%d/%m/%Y %H:%M'),
                            'cant_vendida': cant_ven, 'tot_ventas': tot_ventas, 'capital_inv': capital_real,
                            'cant_devuelta': cant_dev, 'tot_dev': tot_devs,
                            'cant_merma': cant_mer, 'tot_merma': tot_merma,
                            'caja_neta': caja_esperada, 'utilidad': utilidad_pura
                        }
                        st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
        except Exception as e: st.error(f"Error al cargar reportes.")
