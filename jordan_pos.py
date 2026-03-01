import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client
import pandas as pd
from datetime import datetime
import time
import os
import bcrypt
import plotly.express as px

# ==========================================
# 1. CONEXIÓN SEGURA A LA BASE DE DATOS
# ==========================================
URL_SUPABASE = st.secrets["SUPABASE_URL"]
KEY_SUPABASE = st.secrets["SUPABASE_KEY"]
supabase = create_client(URL_SUPABASE, KEY_SUPABASE)

st.set_page_config(page_title="JORDAN POS ERP", layout="wide", page_icon="📱", initial_sidebar_state="expanded")

ERROR_ADMIN = "🚨 Error del sistema. Contactar al administrador."

# ==========================================
# 2. SEGURIDAD Y ENCRIPTACIÓN (BCRYPT)
# ==========================================
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(input_password, stored_password):
    if stored_password.startswith("$2"): 
        return bcrypt.checkpw(input_password.encode('utf-8'), stored_password.encode('utf-8'))
    return input_password == stored_password

# ==========================================
# 3. DISEÑO VISUAL UX/UI
# ==========================================
st.markdown("""
    <style>
    :root { --primary-color: #3b82f6; --success-color: #10b981; --danger-color: #ef4444; --warning-color: #f59e0b; }
    .main-header { font-size: 24px; font-weight: 900; color: var(--primary-color); text-align: center; padding: 15px; border-bottom: 3px solid var(--primary-color); margin-bottom: 20px; background: transparent; border-radius: 8px;}
    .css-card { background: var(--background-color); padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-left: 5px solid var(--primary-color); margin-bottom: 15px; }
    .metric-box { background: var(--background-color); padding: 15px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); text-align: center; border: 1px solid #e2e8f0; transition: transform 0.2s;}
    .metric-box:hover { transform: translateY(-3px); box-shadow: 0 8px 15px rgba(0,0,0,0.1); }
    .metric-title { font-size: 11px; color: #64748b; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 5px;}
    .metric-value { font-size: 24px; font-weight: 900;}
    .metric-value-small { font-size: 18px; font-weight: 800;}
    .metric-green { color: var(--success-color); }
    .metric-red { color: var(--danger-color); }
    .metric-orange { color: var(--warning-color); }
    .metric-blue { color: var(--primary-color); }
    .metric-purple { color: #8b5cf6; }
    .qr-container { padding: 10px; border-radius: 10px; text-align: center; border: 2px dashed var(--primary-color); margin-bottom: 10px;}
    .qr-amount { font-size: 32px; font-weight: 900; color: #1e3a8a; margin-bottom: 10px;}
    .ticket-termico { background: white; color: black; font-family: 'Courier New', monospace; padding: 15px; border: 1px dashed #333; width: 100%; max-width: 320px; margin: 0 auto; line-height: 1.2; font-size: 13px; }
    .linea-corte { text-align: center; margin: 25px 0; border-bottom: 2px dashed #94a3b8; line-height: 0.1em; color: #64748b; font-size: 12px; font-weight: bold;}
    .linea-corte span { background: var(--background-color); padding: 0 10px; }
    .stButton>button { border-radius: 6px; font-weight: bold; transition: all 0.2s; }
    .btn-checkout>button { background-color: var(--success-color); color: white; height: 3em; font-size: 18px;}
    .btn-checkout>button:hover { background-color: #059669; color: white;}
    </style>
    """, unsafe_allow_html=True)

# INYECCIÓN JS PARA AUTOFOCUS EN VENTAS
components.html("""
    <script>
    const inputs = window.parent.document.querySelectorAll('input[type="text"]');
    if(inputs.length > 0) { inputs[0].focus(); }
    </script>
    """, height=0)

# ==========================================
# 4. MEMORIA DEL SISTEMA Y CACHÉ
# ==========================================
keys_to_init = {
    'logged_in': False, 'user_id': None, 'user_name': "", 'user_perms': [],
    'carrito': [], 'last_ticket_html': None, 'ticket_cierre': None,
    'iny_alm_cod': "", 'api_nombre_sugerido': ""
}
for key, value in keys_to_init.items():
    if key not in st.session_state: st.session_state[key] = value

@st.cache_data(ttl=300)
def load_data_cached(table):
    try: return pd.DataFrame(supabase.table(table).select("*").execute().data)
    except: return pd.DataFrame()

def load_data(table):
    try: return pd.DataFrame(supabase.table(table).select("*").execute().data)
    except: return pd.DataFrame()

def registrar_kardex(producto_id, usuario_id, tipo_movimiento, cantidad, motivo):
    try: supabase.table("movimientos_inventario").insert({"producto_id": str(producto_id), "usuario_id": usuario_id, "tipo_movimiento": tipo_movimiento, "cantidad": cantidad, "motivo": motivo}).execute()
    except: pass

def get_last_cierre_dt():
    try:
        c = supabase.table("cierres_caja").select("fecha_cierre").order("fecha_cierre", desc=True).limit(1).execute()
        if c.data: return pd.to_datetime(c.data[0]['fecha_cierre'], utc=True)
    except: pass
    return pd.to_datetime("2000-01-01T00:00:00Z", utc=True)

def procesar_codigo_venta(code):
    try:
        prod = supabase.table("productos").select("*").eq("codigo_barras", code).execute()
        if prod.data:
            p = prod.data[0]
            if p['stock_actual'] > 0:
                exist = False
                for item in st.session_state.carrito:
                    if item['id'] == code: 
                        if item['cant'] < p['stock_actual']: item['cant'] += 1; exist = True
                        else: st.warning(f"Stock máximo de {p['nombre']} alcanzado."); return True
                if not exist:
                    st.session_state.carrito.append({
                        'id': code, 'nombre': p['nombre'], 'precio': float(p['precio_lista']), 
                        'cant': 1, 'costo': float(p['costo_compra']), 'p_min': float(p['precio_minimo']),
                        'stock_max': p['stock_actual']
                    })
                st.toast(f"✅ Añadido: {p['nombre']}", icon="🛒")
                return True
            else: st.error("❌ Sin stock disponible.")
        else: st.warning("⚠️ Producto no encontrado.")
    except: st.error(ERROR_ADMIN)
    return False

def get_lista_usuarios():
    try:
        res = supabase.table("usuarios").select("id, nombre_completo, usuario").eq("estado", "Activo").execute()
        return res.data if res.data else []
    except: return []

def get_qr_image_path():
    for ext in ['.png', '.jpg', '.jpeg']:
        if os.path.exists(f"qr_yape{ext}"): return f"qr_yape{ext}"
    return None

# ==========================================
# 5. ESTRUCTURA PRINCIPAL Y SIDEBAR 
# ==========================================
st.markdown('<div class="main-header">📱 JORDAN POS | ERP CORPORATIVO</div>', unsafe_allow_html=True)

st.sidebar.markdown("### 🏢 Control de Personal")

# SIEMPRE VISIBLE: Registro de Asistencia
with st.sidebar.expander("⌚ Marcar Asistencia", expanded=True):
    with st.form("form_asistencia", clear_on_submit=True):
        usr_ast = st.text_input("Usuario Vendedor")
        pwd_ast = st.text_input("Clave", type="password")
        c_a1, c_a2 = st.columns(2)
        btn_in = c_a1.form_submit_button("🟢 Entrada")
        btn_out = c_a2.form_submit_button("🔴 Salida")
        if btn_in or btn_out:
            if usr_ast and pwd_ast:
                try:
                    u_d = supabase.table("usuarios").select("*").eq("usuario", usr_ast).eq("estado", "Activo").execute()
                    if u_d.data and verify_password(pwd_ast, u_d.data[0].get('clave')):
                        tipo = "Ingreso" if btn_in else "Salida"
                        supabase.table("asistencia").insert({"usuario_id": u_d.data[0]['id'], "tipo_marcacion": tipo}).execute()
                        st.success(f"✅ Asistencia registrada para {u_d.data[0]['nombre_completo']}")
                    else: st.error("❌ Credenciales inválidas.")
                except: pass

st.sidebar.divider()

if not st.session_state.logged_in:
    st.sidebar.markdown("#### 🔐 Acceso Administrativo")
    with st.sidebar.form("form_login"):
        l_usr = st.text_input("Usuario")
        l_pwd = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Iniciar Sesión", type="primary"):
            try:
                usr_data = supabase.table("usuarios").select("*").eq("usuario", l_usr).eq("estado", "Activo").execute()
                if usr_data.data and verify_password(l_pwd, usr_data.data[0].get('clave')):
                    st.session_state.logged_in = True
                    st.session_state.user_id = usr_data.data[0]['id']
                    st.session_state.user_name = usr_data.data[0]['nombre_completo']
                    st.session_state.user_perms = usr_data.data[0].get('permisos', [])
                    st.rerun()
                else: st.error("❌ Acceso Denegado.")
            except: st.error("Error de conexión.")
else:
    st.sidebar.success(f"👤 {st.session_state.user_name}")
    if st.sidebar.button("🚪 Cerrar Sesión"):
        st.session_state.logged_in = False
        st.session_state.user_id = None
        st.session_state.user_perms = []
        st.rerun()

# --- MENÚ DINÁMICO DE NAVEGACIÓN ---
# Ventas y Devoluciones SIEMPRE son visibles para todos
menu_options = ["🛒 VENTAS (POS)", "🔄 DEVOLUCIONES"]

# Módulos protegidos (Solo aparecen si inicias sesión y tienes permiso)
if st.session_state.logged_in:
    p = st.session_state.user_perms
    if "reportes" in p or "cierre_caja" in p: menu_options.insert(0, "📈 DASHBOARD GENERAL")
    menu_options.append("🤝 CLIENTES (CRM)")
    if "inventario_ver" in p: menu_options.append("📦 ALMACÉN Y COMPRAS")
    if "reportes" in p: menu_options.append("💵 GASTOS OPERATIVOS")
    if "mermas" in p: menu_options.append("⚠️ MERMAS")
    if "reportes" in p or "cierre_caja" in p: menu_options.append("📊 REPORTES Y CIERRE")
    if "gestion_usuarios" in p: menu_options.append("👥 RRHH (Vendedores)")

menu = st.sidebar.radio("Navegación", menu_options)

# ==========================================
# 📈 MÓDULO 0: DASHBOARD GENERAL (Solo Admin)
# ==========================================
if menu == "📈 DASHBOARD GENERAL":
    st.subheader("Panorama del Negocio")
    try:
        v_db = supabase.table("ventas_cabecera").select("total_venta, created_at").execute()
        if v_db.data:
            df_v = pd.DataFrame(v_db.data)
            df_v['fecha'] = pd.to_datetime(df_v['created_at']).dt.tz_convert('America/Lima').dt.date
            hoy = datetime.now().date()
            mes = datetime.now().month
            
            v_hoy = df_v[df_v['fecha'] == hoy]['total_venta'].sum()
            v_mes = df_v[pd.to_datetime(df_v['created_at']).dt.tz_convert('America/Lima').dt.month == mes]['total_venta'].sum()
            
            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(f"<div class='metric-box'><div class='metric-title'>Ventas Hoy</div><div class='metric-value metric-green'>S/. {v_hoy:.2f}</div></div>", unsafe_allow_html=True)
            c2.markdown(f"<div class='metric-box'><div class='metric-title'>Ventas Mes</div><div class='metric-value metric-blue'>S/. {v_mes:.2f}</div></div>", unsafe_allow_html=True)
            
            ultimos_7 = df_v[df_v['fecha'] >= (hoy - pd.Timedelta(days=7))]
            if not ultimos_7.empty:
                grafico_data = ultimos_7.groupby('fecha')['total_venta'].sum().reset_index()
                fig = px.bar(grafico_data, x='fecha', y='total_venta', title="Ventas Últimos 7 Días", text_auto='.2f', color_discrete_sequence=['#3b82f6'])
                st.plotly_chart(fig, use_container_width=True)
        else: st.info("No hay datos suficientes para el Dashboard.")
    except: pass

# ==========================================
# 🛒 MÓDULO 1: VENTAS (POS) - ACCESO LIBRE
# ==========================================
elif menu == "🛒 VENTAS (POS)":
    if st.session_state.last_ticket_html:
        components.html(st.session_state.last_ticket_html, width=0, height=0)
        st.session_state.last_ticket_html = None 

    col_v1, col_v2 = st.columns([1.3, 1.7])
    
    with col_v1:
        st.markdown("#### 🔍 Escanear / Buscar")
        with st.form("form_barcode", clear_on_submit=True):
            codigo = st.text_input("Código de Barras (Láser o Teclado)", key="pos_input")
            if st.form_submit_button("Añadir", use_container_width=True):
                if codigo: procesar_codigo_venta(codigo); st.rerun()

        st.divider()
        search = st.text_input("Búsqueda Manual")
        if search:
            try:
                res_s = supabase.table("productos").select("*, marcas(nombre)").ilike("nombre", f"%{search}%").execute()
                for p in res_s.data:
                    c_p1, c_p2 = st.columns([3, 1])
                    c_p1.write(f"**{p['nombre']}** - S/.{p['precio_lista']} (Stock: {p['stock_actual']})")
                    if c_p2.button("➕", key=f"btn_{p['codigo_barras']}"):
                        if procesar_codigo_venta(p['codigo_barras']): st.rerun()
            except: pass

    with col_v2:
        st.markdown("#### 🛍️ Carrito de Compras")
        if not st.session_state.carrito: 
            st.info("El carrito está vacío.")
        else:
            total_venta = 0.0
            costo_total = 0.0
            
            for i, item in enumerate(st.session_state.carrito):
                c1, c2, c3, c4 = st.columns([3, 1.5, 1.5, 1])
                c1.write(f"**{item['nombre']}**")
                
                nuevo_p = c2.number_input("S/.", min_value=float(item['p_min']), value=float(item['precio']), step=1.0, key=f"p_{i}", label_visibility="collapsed")
                st.session_state.carrito[i]['precio'] = nuevo_p
                
                with c3:
                    sc1, sc2, sc3 = st.columns([1,1,1])
                    if sc1.button("➖", key=f"m_{i}"):
                        if item['cant'] > 1: st.session_state.carrito[i]['cant'] -= 1; st.rerun()
                    sc2.write(f"**{item['cant']}**")
                    if sc3.button("➕", key=f"p_c_{i}"):
                        if item['cant'] < item['stock_max']: st.session_state.carrito[i]['cant'] += 1; st.rerun()
                        else: st.toast("Stock máximo")
                
                if c4.button("🗑️", key=f"d_{i}"):
                    st.session_state.carrito.pop(i); st.rerun()
                    
                subtotal = nuevo_p * item['cant']
                total_venta += subtotal
                costo_total += (item['costo'] * item['cant'])

            st.markdown(f"<div style='text-align:right;'><h1 style='color:#10b981; font-size:45px;'>TOTAL: S/. {total_venta:.2f}</h1></div>", unsafe_allow_html=True)
            
            # Solo muestra ganancia si está logueado y tiene permisos
            if st.session_state.logged_in and "reportes" in st.session_state.user_perms:
                st.caption(f"Margen ganancia estimado: S/. {total_venta - costo_total:.2f}")

            with st.expander("💸 PAGO Y FACTURACIÓN", expanded=True):
                # Vendedor (Obligatorio)
                lista_vendedores = get_lista_usuarios()
                vendedor_opciones = {v['usuario']: v['id'] for v in lista_vendedores}
                vendedor_seleccionado = st.selectbox("👤 Tu usuario (Vendedor):", ["Seleccionar..."] + list(vendedor_opciones.keys()))

                # Cliente (Opcional)
                try:
                    clientes_db = supabase.table("clientes").select("*").execute()
                    opciones_clientes = ["Público General (Sin registrar)"]
                    cliente_dict = {}
                    if clientes_db.data:
                        for r in clientes_db.data:
                            label = f"{r['dni_ruc']} - {r['nombre']}"
                            opciones_clientes.append(label)
                            cliente_dict[label] = r['id']
                except: opciones_clientes = ["Público General (Sin registrar)"]; cliente_dict = {}
                
                cliente_sel = st.selectbox("Cliente (Opcional):", opciones_clientes)
                
                cp1, cp2 = st.columns(2)
                pago = cp1.selectbox("Método de Pago", ["Efectivo", "Yape", "Plin", "Tarjeta VISA/MC"])
                
                vuelto = 0.0
                ref_pago = ""
                
                if pago == "Efectivo":
                    recibido = cp2.number_input("Efectivo Recibido (S/.)", min_value=0.0, value=float(total_venta), step=5.0)
                    vuelto = recibido - total_venta
                    if vuelto > 0: st.success(f"**VUELTO A ENTREGAR: S/. {vuelto:.2f}**")
                else:
                    ref_pago = cp2.text_input("N° de Referencia")

                st.markdown('<div class="btn-checkout">', unsafe_allow_html=True)
                if st.button("FINALIZAR VENTA E IMPRIMIR", use_container_width=True):
                    if vendedor_seleccionado == "Seleccionar...":
                        st.error("🛑 Selecciona tu usuario (Vendedor) primero.")
                    elif pago != "Efectivo" and not ref_pago:
                        st.error("🛑 Ingresa la referencia del pago digital.")
                    else:
                        try:
                            vendedor_id = vendedor_opciones[vendedor_seleccionado]
                            cli_id = cliente_dict.get(cliente_sel, None) if cliente_sel != "Público General (Sin registrar)" else None
                            t_num = f"AJ-{int(time.time())}"
                            
                            supabase.table("ventas_cabecera").insert({
                                "ticket_numero": t_num, "total_venta": total_venta, "metodo_pago": pago,
                                "usuario_id": vendedor_id, "referencia_pago": ref_pago,
                                "cliente_id": cli_id
                            }).execute()
                            v_res = supabase.table("ventas_cabecera").select("id").eq("ticket_numero", t_num).execute()
                            v_id = v_res.data[0]['id']
                            
                            items_html = ""
                            for it in st.session_state.carrito:
                                supabase.table("ventas_detalle").insert({"venta_id": v_id, "producto_id": it['id'], "cantidad": it['cant'], "precio_unitario": it['precio'], "subtotal": it['precio'] * it['cant']}).execute()
                                stk = supabase.table("productos").select("stock_actual").eq("codigo_barras", it['id']).execute()
                                supabase.table("productos").update({"stock_actual": stk.data[0]['stock_actual'] - it['cant']}).eq("codigo_barras", it['id']).execute()
                                
                                registrar_kardex(it['id'], vendedor_id, "SALIDA_VENTA", it['cant'], f"Ticket {t_num}")
                                items_html += f"{it['nombre'][:20]} <br> {it['cant']} x S/. {it['precio']:.2f} = S/. {it['precio']*it['cant']:.2f}<br>"
                            
                            fecha_tk = datetime.now().strftime('%d/%m/%Y %H:%M')
                            c_base = f"""--------------------------------<br>TICKET: {t_num}<br>FECHA: {fecha_tk}<br>CAJERO: {vendedor_seleccionado}<br>CLIENTE: {cliente_sel.split(' - ')[0] if cli_id else 'General'}<br>--------------------------------<br>{items_html}--------------------------------<br><b>TOTAL PAGADO: S/. {total_venta:.2f}</b><br>MÉTODO: {pago}<br>"""
                            tk_html = f"""<div class="ticket-termico"><center><b>ACCESORIOS JORDAN</b><br>COPIA CLIENTE</center><br>{c_base}<center>¡Gracias!</center></div><div class="linea-corte"><span>✂️</span></div><div class="ticket-termico"><center><b>ACCESORIOS JORDAN</b><br>CONTROL</center><br>{c_base}</div><script>window.onload=function(){{window.print();}}</script>"""
                            
                            supabase.table("ticket_historial").insert({"ticket_numero": t_num, "usuario_id": vendedor_id, "html_payload": tk_html}).execute()
                            st.session_state.last_ticket_html = tk_html
                            st.session_state.carrito = []
                            st.rerun() 
                        except Exception as e: st.error(f"Error al facturar.")
                st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 🔄 MÓDULO 2: DEVOLUCIONES - ACCESO LIBRE
# ==========================================
elif menu == "🔄 DEVOLUCIONES":
    st.subheader("Gestión de Devoluciones")
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
                    vendedor_sel = st.selectbox("👤 Autoriza (Vendedor):", ["..."] + list(vendedor_opciones.keys()))
                    for d in v_det.data:
                        col_d1, col_d2 = st.columns([3, 1])
                        col_d1.write(f"**{d['productos']['nombre']}** - Compró: {d['cantidad']} ud.")
                        if col_d2.button("Devolver", key=f"dev_{d['id']}"):
                            if vendedor_sel != "...":
                                usr_id = vendedor_opciones[vendedor_sel]
                                p_s = supabase.table("productos").select("stock_actual").eq("codigo_barras", d['producto_id']).execute()
                                supabase.table("productos").update({"stock_actual": p_s.data[0]['stock_actual'] + d['cantidad']}).eq("codigo_barras", d['producto_id']).execute()
                                supabase.table("devoluciones").insert({"usuario_id": usr_id, "producto_id": d['producto_id'], "cantidad": d['cantidad'], "motivo": "Devolución Ticket", "dinero_devuelto": d['subtotal'], "estado_producto": "Vuelve a tienda"}).execute()
                                registrar_kardex(d['producto_id'], usr_id, "INGRESO_DEVOLUCION", d['cantidad'], f"Ticket {search_dev.upper()}")
                                st.success("✅ Devuelto."); time.sleep(1); st.rerun()
                            else: st.error("Selecciona tu usuario.")
            except: pass
        else:
            try:
                p_db = supabase.table("productos").select("*").eq("codigo_barras", search_dev).execute()
                if p_db.data:
                    p = p_db.data[0]
                    with st.form("form_dev_libre"):
                        vendedor_sel = st.selectbox("👤 Autoriza (Vendedor):", ["..."] + list(vendedor_opciones.keys()))
                        c1, c2 = st.columns(2)
                        d_cant = c1.number_input("Cantidad", min_value=1, step=1)
                        d_dinero = c2.number_input("Devuelto (S/.)", value=float(p['precio_lista']))
                        m_dev = st.text_input("Motivo")
                        if st.form_submit_button("🔁 DEVOLVER"):
                            if m_dev and vendedor_sel != "...":
                                usr_id = vendedor_opciones[vendedor_sel]
                                supabase.table("productos").update({"stock_actual": p['stock_actual'] + d_cant}).eq("codigo_barras", p['codigo_barras']).execute()
                                supabase.table("devoluciones").insert({"usuario_id": usr_id, "producto_id": p['codigo_barras'], "cantidad": d_cant, "motivo": m_dev, "dinero_devuelto": d_cant * d_dinero, "estado_producto": "Vuelve a tienda"}).execute()
                                registrar_kardex(p['codigo_barras'], usr_id, "INGRESO_DEVOLUCION", d_cant, m_dev)
                                st.success("✅ Devuelto."); time.sleep(1); st.rerun()
                            else: st.error("Falta motivo o usuario.")
            except: pass

# ==========================================
# 🤝 MÓDULO 3: CLIENTES (CRM)
# ==========================================
elif menu == "🤝 CLIENTES (CRM)":
    st.subheader("Base de Datos de Clientes")
    t1, t2 = st.tabs(["📋 Lista de Clientes", "➕ Nuevo Cliente"])
    
    with t1:
        try:
            cls_df = load_data("clientes")
            if not cls_df.empty: st.dataframe(cls_df[['dni_ruc', 'nombre', 'telefono', 'created_at']], use_container_width=True)
            else: st.info("No hay clientes registrados.")
        except: st.error("Asegúrate de ejecutar el código SQL para crear la tabla de clientes.")
        
    with t2:
        with st.form("form_cli"):
            doc = st.text_input("DNI o RUC (Único)")
            nom = st.text_input("Nombre / Razón Social")
            tel = st.text_input("Celular")
            if st.form_submit_button("Guardar Cliente", type="primary"):
                if doc and nom:
                    try:
                        supabase.table("clientes").insert({"dni_ruc": doc, "nombre": nom, "telefono": tel}).execute()
                        st.success("✅ Cliente guardado."); time.sleep(1); st.rerun()
                    except: st.error("Error: El DNI/RUC ya existe.")

# ==========================================
# 💵 MÓDULO 4: GASTOS OPERATIVOS
# ==========================================
elif menu == "💵 GASTOS OPERATIVOS" and "reportes" in st.session_state.user_perms:
    st.subheader("Salidas de Dinero (Caja Chica)")
    st.info("Todo lo que registres aquí se restará de tu Efectivo Neto en el cierre de caja.")
    
    t1, t2 = st.tabs(["📝 Registrar Gasto", "📋 Historial Hoy"])
    
    with t1:
        with st.form("form_gasto"):
            tipo = st.selectbox("Categoría", ["Alimentación", "Pasajes/Movilidad", "Pago Servicios", "Compras Menores", "Otro"])
            desc = st.text_input("Descripción breve")
            monto = st.number_input("Monto retirado de caja (S/.)", min_value=0.1, step=1.0)
            if st.form_submit_button("Confirmar Salida de Dinero", type="primary"):
                try:
                    supabase.table("gastos").insert({"usuario_id": st.session_state.user_id, "tipo_gasto": tipo, "descripcion": desc, "monto": monto}).execute()
                    st.success("✅ Gasto registrado."); time.sleep(1); st.rerun()
                except: st.error("Asegúrate de ejecutar el código SQL para crear la tabla de gastos.")
                
    with t2:
        try:
            hoy = datetime.now().date().isoformat()
            gst = supabase.table("gastos").select("*, usuarios(nombre_completo)").gte("fecha", hoy).execute()
            if gst.data:
                df_g = pd.DataFrame(gst.data)
                df_g['Usuario'] = df_g['usuarios'].apply(lambda x: x['nombre_completo'] if isinstance(x, dict) else '')
                st.dataframe(df_g[['tipo_gasto', 'descripcion', 'monto', 'Usuario']], use_container_width=True)
                st.warning(f"**Total Gastado Hoy: S/. {df_g['monto'].sum():.2f}**")
        except: pass

# ==========================================
# 📦 MÓDULO 5: ALMACÉN Y COMPRAS
# ==========================================
elif menu == "📦 ALMACÉN Y COMPRAS" and "inventario_ver" in st.session_state.user_perms:
    st.subheader("Inventario Maestro y Compras")
    t1, t2, t3, t4 = st.tabs(["📋 Inventario General", "➕ Crear Producto", "⚙️ Catálogos", "📓 KARDEX"])
    
    with t1:
        prods = supabase.table("productos").select("*, categorias(nombre), marcas(nombre)").execute()
        if prods.data: 
            df = pd.DataFrame(prods.data)
            df['Categoría'] = df['categorias'].apply(lambda x: x['nombre'] if isinstance(x, dict) else 'N/A')
            df['Marca'] = df['marcas'].apply(lambda x: x['nombre'] if isinstance(x, dict) else 'N/A')
            df['Margen %'] = ((df['precio_lista'] - df['costo_compra']) / df['costo_compra'] * 100).fillna(0).round(1).astype(str) + "%"
            
            if 'stock_minimo' not in df.columns: df['stock_minimo'] = 5
            
            def highlight_stock(row):
                if row['stock_actual'] <= row['stock_minimo']: return ['background-color: #fef2f2; color: #dc2626'] * len(row)
                return [''] * len(row)
            
            df_show = df[['codigo_barras', 'nombre', 'Categoría', 'Marca', 'costo_compra', 'precio_lista', 'Margen %', 'stock_actual', 'stock_minimo']]
            st.dataframe(df_show.style.apply(highlight_stock, axis=1), use_container_width=True)
            
            if "inventario_modificar" in st.session_state.user_perms:
                st.divider()
                st.write("#### ⚡ Reabastecimiento Rápido")
                with st.form("form_add_stock"):
                    col_r1, col_r2 = st.columns([3, 1])
                    sel_p = col_r1.selectbox("Producto:", ["..."] + [f"{r['codigo_barras']} - {r['nombre']}" for _, r in df.iterrows()])
                    add_qty = col_r2.number_input("Cantidad entrante", min_value=1, step=1)
                    if st.form_submit_button("➕ Sumar Stock", type="primary"):
                        if sel_p != "...":
                            c_up = sel_p.split(" - ")[0]
                            c_stk = int(df[df['codigo_barras'] == c_up]['stock_actual'].iloc[0])
                            supabase.table("productos").update({"stock_actual": c_stk + add_qty}).eq("codigo_barras", c_up).execute()
                            registrar_kardex(c_up, st.session_state.user_id, "INGRESO_REPOSICION", add_qty, "Reabastecimiento")
                            st.success("✅ Stock actualizado."); time.sleep(1); st.rerun()

    with t2:
        if "inventario_agregar" in st.session_state.user_perms:
            cats, mars = load_data_cached("categorias"), load_data_cached("marcas")
            cals, comps = load_data_cached("calidades"), load_data_cached("compatibilidades")

            with st.form("form_nuevo", clear_on_submit=True):
                c_cod = st.text_input("Código de Barras (Láser)")
                c_nom = st.text_input("Nombre del Producto")
                f1, f2, f3, f8 = st.columns(4)
                f_cat = f1.selectbox("Categoría", cats['nombre'].tolist() if not cats.empty else [])
                f_mar = f2.selectbox("Marca", mars['nombre'].tolist() if not mars.empty else [])
                f_cal = f3.selectbox("Calidad", cals['nombre'].tolist() if not cals.empty else [])
                f_comp = f8.selectbox("Compatibilidad", comps['nombre'].tolist() if not comps.empty else [])
                
                f4, f5, f6, f7 = st.columns(4)
                f_costo = f4.number_input("Costo (S/.)", min_value=0.0)
                f_venta = f5.number_input("Precio Venta (S/.)", min_value=0.0)
                f_stock = f6.number_input("Stock Inicial", min_value=0)
                f_smin = f7.number_input("Stock Mínimo (Alerta)", value=5)
                
                if st.form_submit_button("🚀 CREAR PRODUCTO", type="primary"):
                    if c_cod and c_nom:
                        cid = int(cats[cats['nombre'] == f_cat]['id'].iloc[0])
                        mid = int(mars[mars['nombre'] == f_mar]['id'].iloc[0])
                        try:
                            supabase.table("productos").insert({"codigo_barras": c_cod, "nombre": c_nom, "categoria_id": cid, "marca_id": mid, "calidad": f_cal, "compatibilidad": f_comp, "costo_compra": f_costo, "precio_lista": f_venta, "precio_minimo": f_venta, "stock_actual": f_stock, "stock_inicial": f_stock, "stock_minimo": f_smin}).execute()
                            if f_stock > 0: registrar_kardex(c_cod, st.session_state.user_id, "INGRESO_COMPRA", f_stock, "Alta")
                            st.success("✅ Creado."); time.sleep(1); st.rerun()
                        except: st.error("El código ya existe o faltan datos.")

    with t3:
        st.write("Catálogos de Clasificación")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            with st.form("fc"): v = st.text_input("Categoría"); st.form_submit_button("Guardar Cat")
        with c2:
            with st.form("fm"): v = st.text_input("Marca"); st.form_submit_button("Guardar Mar")
        with c3:
            with st.form("fcal"): v = st.text_input("Calidad"); st.form_submit_button("Guardar Cal")
        with c4:
            with st.form("fcom"): v = st.text_input("Compatibilidad"); st.form_submit_button("Guardar Comp")

    with t4:
        k_data = supabase.table("movimientos_inventario").select("*, usuarios(nombre_completo)").order("timestamp", desc=True).limit(50).execute()
        if k_data.data:
            df_k = pd.DataFrame(k_data.data)
            df_k['Usuario'] = df_k['usuarios'].apply(lambda x: x.get('nombre_completo', 'Sys'))
            df_k['Fecha'] = pd.to_datetime(df_k['timestamp']).dt.tz_convert('America/Lima').dt.strftime('%d/%m %H:%M')
            st.dataframe(df_k[['Fecha', 'producto_id', 'tipo_movimiento', 'cantidad', 'Usuario']], use_container_width=True)

# ==========================================
# ⚠️ MÓDULO 6: MERMAS
# ==========================================
elif menu == "⚠️ MERMAS" and "mermas" in st.session_state.user_perms:
    st.subheader("Dar de Baja Productos Dañados")
    m_cod = st.text_input("Código de Barras")
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
                            registrar_kardex(m_cod, st.session_state.user_id, "SALIDA_MERMA", m_cant, m_mot)
                            st.success("✅ Baja exitosa."); time.sleep(1); st.rerun()
        except: pass

# ==========================================
# 👥 MÓDULO 7: GESTIÓN DE VENDEDORES (RRHH INTEGRAL)
# ==========================================
elif menu == "👥 RRHH (Vendedores)" and "gestion_usuarios" in st.session_state.user_perms:
    st.subheader("Panel de Control Gerencial")
    
    t_u1, t_u2, t_u3, t_u4, t_u5 = st.tabs(["📋 Activos", "➕ Crear Nuevo", "🔑 Password", "🗑️ Baja / Alta", "📊 Análisis (RRHH)"])
    
    usrs_db = supabase.table("usuarios").select("id, nombre_completo, usuario, clave, turno, permisos, estado").execute()
    df_u, df_activos, df_inactivos = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    if usrs_db.data:
        df_u = pd.DataFrame(usrs_db.data)
        df_u['permisos'] = df_u['permisos'].apply(lambda x: ", ".join(x) if isinstance(x, list) else str(x))
        df_activos = df_u[df_u['estado'] == 'Activo']
        df_inactivos = df_u[df_u['estado'] == 'Inactivo']
    
    with t_u1:
        if not df_activos.empty: st.dataframe(df_activos[['nombre_completo', 'usuario', 'turno', 'permisos']], use_container_width=True)
            
    with t_u2:
        with st.form("form_new_user", clear_on_submit=True):
            n_nombre = st.text_input("Nombre Completo")
            n_user = st.text_input("Usuario (Login)")
            n_pass = st.text_input("Contraseña")
            n_turno = st.selectbox("Turno", ["Mañana", "Tarde", "Completo", "Rotativo"])
            n_perms = st.multiselect("Permisos:", ["mermas", "inventario_ver", "inventario_agregar", "inventario_modificar", "inventario_eliminar", "reportes", "cierre_caja", "gestion_usuarios"])
            if st.form_submit_button("Crear Vendedor", type="primary"):
                if n_nombre and n_user and n_pass:
                    try:
                        hashed_pw = hash_password(n_pass)
                        supabase.table("usuarios").insert({"nombre_completo": n_nombre, "usuario": n_user, "clave": hashed_pw, "turno": n_turno, "permisos": n_perms, "estado": "Activo"}).execute()
                        st.success("✅ Creado."); time.sleep(1.5); st.rerun()
                    except: st.error("❌ El Usuario ya existe.")

    with t_u3:
        if not df_activos.empty:
            with st.form("reset_pwd"):
                c_u = st.selectbox("Usuario:", df_activos['usuario'].tolist())
                n_pwd = st.text_input("Escribe Nueva Contraseña")
                if st.form_submit_button("Actualizar", type="primary"):
                    if n_pwd:
                        hashed_pw = hash_password(n_pwd)
                        supabase.table("usuarios").update({"clave": hashed_pw}).eq("usuario", c_u).execute()
                        st.success("✅ Actualizado."); time.sleep(1); st.rerun()

    with t_u4:
        c1, c2 = st.columns(2)
        with c1:
            if not df_activos.empty:
                v_b = df_activos[df_activos['usuario'] != 'admin']['usuario'].tolist()
                if v_b:
                    u_del = st.selectbox("Inhabilitar:", v_b)
                    if st.button("🗑️ INHABILITAR"):
                        supabase.table("usuarios").update({"estado": "Inactivo"}).eq("usuario", u_del).execute(); st.rerun()
        with c2:
            if not df_inactivos.empty:
                u_react = st.selectbox("Reactivar:", df_inactivos['usuario'].tolist())
                if st.button("✅ ACTIVAR", type="primary"):
                    supabase.table("usuarios").update({"estado": "Activo"}).eq("usuario", u_react).execute(); st.rerun()

    with t_u5:
        if not df_activos.empty:
            sel_u_nombre = st.selectbox("Analizar rendimiento de:", df_activos['nombre_completo'].tolist())
            sel_u_id = df_activos[df_activos['nombre_completo'] == sel_u_nombre]['id'].iloc[0]
            try:
                ast_db = supabase.table("asistencia").select("*").eq("usuario_id", sel_u_id).execute()
                v_det = supabase.table("ventas_detalle").select("subtotal, cantidad, productos(costo_compra), ventas_cabecera(created_at, ticket_numero, usuario_id)").execute()
                
                df_a = pd.DataFrame(ast_db.data) if ast_db.data else pd.DataFrame()
                df_v = pd.DataFrame()
                
                if v_det.data:
                    df_v = pd.DataFrame(v_det.data)
                    df_v['ts'] = pd.to_datetime(df_v['ventas_cabecera'].apply(lambda x: x.get('created_at', '2000-01-01') if isinstance(x, dict) else '2000-01-01')).dt.tz_convert('America/Lima')
                    df_v['usr_id'] = df_v['ventas_cabecera'].apply(lambda x: x.get('usuario_id', 0) if isinstance(x, dict) else 0)
                    df_v['costo_unit'] = df_v['productos'].apply(lambda x: float(x.get('costo_compra', 0)) if isinstance(x, dict) else 0.0)
                    df_v['costo_tot'] = df_v['costo_unit'] * df_v['cantidad']
                    df_v = df_v[df_v['usr_id'] == sel_u_id]

                if not df_a.empty:
                    df_a['ts'] = pd.to_datetime(df_a['timestamp']).dt.tz_convert('America/Lima')
                    df_a['date'] = df_a['ts'].dt.date
                    df_a['month'] = df_a['ts'].dt.month

                st.markdown("---")
                filtro_fecha = st.date_input("📆 Buscar Rendimiento por Día:", value=datetime.now().date())
                
                h_in, h_out, hrs_hoy = "--:--", "--:--", 0.0
                v_hoy_ventas, v_hoy_costo, v_hoy_utilidad = 0.0, 0.0, 0.0
                
                if not df_a.empty:
                    df_hoy_a = df_a[df_a['date'] == filtro_fecha]
                    if not df_hoy_a.empty:
                        i_ts = df_hoy_a[df_hoy_a['tipo_marcacion'] == 'Ingreso']['ts']
                        s_ts = df_hoy_a[df_hoy_a['tipo_marcacion'] == 'Salida']['ts']
                        if not i_ts.empty: h_in = i_ts.min().strftime('%I:%M %p')
                        if not s_ts.empty: h_out = s_ts.max().strftime('%I:%M %p')
                        if not i_ts.empty and not s_ts.empty: hrs_hoy = (s_ts.max() - i_ts.min()).total_seconds() / 3600

                if not df_v.empty:
                    df_hoy_v = df_v[df_v['ts'].dt.date == filtro_fecha]
                    v_hoy_ventas = df_hoy_v['subtotal'].sum()
                    v_hoy_utilidad = v_hoy_ventas - df_hoy_v['costo_tot'].sum()
                
                c1, c2, c3, c4 = st.columns(4)
                c1.markdown(f"<div class='metric-box'><div class='metric-title'>Hora Entrada</div><div class='metric-value-small'>{h_in}</div></div>", unsafe_allow_html=True)
                c2.markdown(f"<div class='metric-box'><div class='metric-title'>Hora Salida</div><div class='metric-value-small'>{h_out}</div></div>", unsafe_allow_html=True)
                c3.markdown(f"<div class='metric-box'><div class='metric-title'>Ventas del Día</div><div class='metric-value-small metric-green'>S/. {v_hoy_ventas:.2f}</div></div>", unsafe_allow_html=True)
                c4.markdown(f"<div class='metric-box' style='border:2px solid #8b5cf6;'><div class='metric-title'>UTILIDAD NETA</div><div class='metric-value-small metric-purple'>S/. {v_hoy_utilidad:.2f}</div></div>", unsafe_allow_html=True)
            except: pass

# ==========================================
# 📊 MÓDULO 8: REPORTES Y CIERRE (CON ALERTAS Y GASTOS)
# ==========================================
elif menu == "📊 REPORTES Y CIERRE" and ("cierre_caja" in st.session_state.user_perms or "reportes" in st.session_state.user_perms):
    st.subheader("Auditoría Financiera y Cierre")
    
    if st.session_state.ticket_cierre:
        tk = st.session_state.ticket_cierre
        st.success("✅ Caja cerrada.")
        st.markdown(f"""
        <div class="ticket-termico">
            <center><b>ACCESORIOS JORDAN</b><br><b>REPORTE Z</b></center>
            --------------------------------<br>
            FECHA CIERRE: {tk['fecha']}<br>
            CAJERO: {st.session_state.user_name}<br>
            --------------------------------<br>
            <b>💰 INGRESOS BRUTOS: S/. {tk['tot_ventas']:.2f}</b><br>
            - Efectivo: S/. {tk['ventas_efectivo']:.2f}<br>
            - Digital: S/. {tk['ventas_digital']:.2f}<br>
            Cant. Vendida: {tk['cant_vendida']} ud.<br>
            --------------------------------<br>
            <b>📉 COSTOS Y SALIDAS:</b><br>
            Capital Inv: S/. {tk['capital_inv']:.2f}<br>
            Gastos Efec: S/. {tk['tot_gastos']:.2f}<br>
            Devoluciones: S/. {tk['tot_dev']:.2f}<br>
            --------------------------------<br>
            <b>🏦 CAJA EFECTIVA FINAL: S/. {tk['caja_efectivo']:.2f}</b><br>
            UTILIDAD NETA: S/. {tk['utilidad']:.2f}<br>
            --------------------------------<br>
            {tk['alertas_stock']}
        </div>
        """, unsafe_allow_html=True)
        if st.button("🧹 Iniciar Nuevo Turno", type="primary"):
            st.session_state.ticket_cierre = None
            st.rerun()
    else:
        try:
            last_cierre = get_last_cierre_dt()
            st.caption(f"Desde: {last_cierre.strftime('%d/%m/%Y %H:%M')}")
            
            cab = supabase.table("ventas_cabecera").select("*").gte("created_at", last_cierre.isoformat()).execute()
            det = supabase.table("ventas_detalle").select("*, productos(costo_compra)").gte("created_at", last_cierre.isoformat()).execute()
            gst = supabase.table("gastos").select("monto").gte("fecha", last_cierre.isoformat()).execute()
            
            tot_v, v_efe, v_dig, tot_costo, tot_gst = 0.0, 0.0, 0.0, 0.0, 0.0
            c_ven = 0
            
            if cab.data:
                df_c = pd.DataFrame(cab.data)
                v_efe = df_c[df_c['metodo_pago'] == 'Efectivo']['total_venta'].sum()
                v_dig = df_c[df_c['metodo_pago'] != 'Efectivo']['total_venta'].sum()
                tot_v = v_efe + v_dig
            
            if det.data:
                df_d = pd.DataFrame(det.data)
                tot_costo = (df_d['productos'].apply(lambda x: float(x.get('costo_compra',0))) * df_d['cantidad']).sum()
                c_ven = df_d['cantidad'].sum()
                
            if gst.data: tot_gst = sum(g['monto'] for g in gst.data)
            
            caja_efectivo = v_efe - tot_gst
            utilidad = tot_v - tot_costo - tot_gst
            
            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(f"<div class='metric-box'><div class='metric-title'>Ventas</div><div class='metric-value'>S/.{tot_v:.2f}</div></div>", unsafe_allow_html=True)
            c2.markdown(f"<div class='metric-box'><div class='metric-title'>Efectivo</div><div class='metric-value'>S/.{v_efe:.2f}</div></div>", unsafe_allow_html=True)
            c3.markdown(f"<div class='metric-box'><div class='metric-title'>Gastos (-)</div><div class='metric-value metric-red'>S/.{tot_gst:.2f}</div></div>", unsafe_allow_html=True)
            c4.markdown(f"<div class='metric-box' style='border:2px solid #10b981;'><div class='metric-title'>EFECTIVO CAJA</div><div class='metric-value metric-green'>S/.{caja_efectivo:.2f}</div></div>", unsafe_allow_html=True)
            
            st.divider()
            if "cierre_caja" in st.session_state.user_perms:
                with st.form("f_cierre"):
                    st.write("Generar Reporte Z")
                    if st.form_submit_button("🔒 APROBAR CIERRE", type="primary"):
                        supabase.table("cierres_caja").insert({"total_ventas": tot_v, "utilidad": utilidad}).execute()
                        
                        # ALERTA DE STOCK <= 20
                        bajos = supabase.table("productos").select("nombre, stock_actual").lte("stock_actual", 20).execute()
                        alert_html = ""
                        if bajos.data:
                            alert_html = "<b>⚠️ ALERTAS STOCK (<=20):</b><br>"
                            for b in bajos.data: alert_html += f"- {b['nombre']}: {b['stock_actual']} ud<br>"
                            alert_html += "--------------------------------<br>"
                            
                        st.session_state.ticket_cierre = {
                            'fecha': datetime.now().strftime('%d/%m %H:%M'),
                            'cant_vendida': c_ven, 'tot_ventas': tot_v, 'ventas_efectivo': v_efe, 'ventas_digital': v_dig,
                            'capital_inv': tot_costo, 'tot_dev': 0, 'tot_merma': 0, 'tot_gastos': tot_gst,
                            'caja_efectivo': caja_efectivo, 'utilidad': utilidad, 'alertas_stock': alert_html
                        }
                        st.rerun()
        except: pass
