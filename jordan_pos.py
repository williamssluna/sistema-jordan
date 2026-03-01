import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client
import pandas as pd
from datetime import datetime
import time
import os
import bcrypt

# ==========================================
# 1. CONEXIÓN SEGURA A LA BASE DE DATOS
# ==========================================
URL_SUPABASE = st.secrets["SUPABASE_URL"]
KEY_SUPABASE = st.secrets["SUPABASE_KEY"]
supabase = create_client(URL_SUPABASE, KEY_SUPABASE)

st.set_page_config(page_title="JORDAN POS ERP", layout="wide", page_icon="📱")

ERROR_ADMIN = "🚨 Error del sistema. Contactar al administrador."

# ==========================================
# 2. SEGURIDAD Y ENCRIPTACIÓN (BCRYPT)
# ==========================================
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(input_password, stored_password):
    if stored_password.startswith("$2"): 
        return bcrypt.checkpw(input_password.encode('utf-8'), stored_password.encode('utf-8'))
    else:
        return input_password == stored_password

# ==========================================
# 3. DISEÑO VISUAL UX/UI
# ==========================================
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    .main-header { font-size: 28px; font-weight: 900; color: #1e3a8a; text-align: center; padding: 20px; border-bottom: 4px solid #3b82f6; margin-bottom: 25px; background: white; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.05);}
    .css-card { background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border-left: 6px solid #3b82f6; margin-bottom: 20px; }
    .metric-box { background: linear-gradient(145deg, #ffffff 0%, #f1f5f9 100%); padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); text-align: center; border: 1px solid #e2e8f0; transition: transform 0.2s ease, box-shadow 0.2s ease; margin-bottom: 15px;}
    .metric-box:hover { transform: translateY(-5px); box-shadow: 0 10px 20px rgba(0,0,0,0.1); }
    .metric-title { font-size: 12px; color: #64748b; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;}
    .metric-value { font-size: 26px; font-weight: 900; color: #0f172a;}
    .metric-value-small { font-size: 20px; font-weight: 800; color: #0f172a;}
    .metric-green { color: #10b981; }
    .metric-red { color: #ef4444; }
    .metric-orange { color: #f59e0b; }
    .metric-blue { color: #3b82f6; }
    .metric-purple { color: #8b5cf6; }
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
    'iny_alm_cod': "", 'iny_dev_cod': "", 'iny_merma_cod': "",
    'api_nombre_sugerido': ""
}
for key, value in keys_to_init.items():
    if key not in st.session_state: st.session_state[key] = value

# ==========================================
# 5. FUNCIONES DE APOYO (KARDEX INCLUIDO)
# ==========================================
def registrar_kardex(producto_id, usuario_id, tipo_movimiento, cantidad, motivo):
    try:
        supabase.table("movimientos_inventario").insert({
            "producto_id": str(producto_id),
            "usuario_id": usuario_id,
            "tipo_movimiento": tipo_movimiento,
            "cantidad": cantidad,
            "motivo": motivo
        }).execute()
    except Exception as e:
        print(f"Error guardando Kardex: {e}")

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

def get_lista_usuarios():
    try:
        res = supabase.table("usuarios").select("id, nombre_completo, usuario").eq("estado", "Activo").execute()
        return res.data if res.data else []
    except: return []

def get_qr_image_path():
    extensions = ['.png', '.jpg', '.jpeg']
    for ext in extensions:
        path = f"qr_yape{ext}"
        if os.path.exists(path):
            return path
    return None

# ==========================================
# 6. ESTRUCTURA PRINCIPAL Y SIDEBAR
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
                    usr_data = supabase.table("usuarios").select("*").eq("usuario", usr_ast).eq("estado", "Activo").execute()
                    if usr_data.data and verify_password(pwd_ast, usr_data.data[0].get('clave')):
                        tipo = "Ingreso" if btn_in else "Salida"
                        supabase.table("asistencia").insert({"usuario_id": usr_data.data[0]['id'], "tipo_marcacion": tipo}).execute()
                        st.success(f"✅ {tipo} registrado para {usr_data.data[0]['nombre_completo']}")
                    else:
                        st.error("❌ Usuario o Contraseña incorrectos (O usuario inactivo).")
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
                usr_data = supabase.table("usuarios").select("*").eq("usuario", l_usr).eq("estado", "Activo").execute()
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
    if "gestion_usuarios" in p: menu_options.append("👥 VENDEDORES")

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
        st.write("Búsqueda Manual")
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
                    if qr_path: st.image(qr_path, use_container_width=True)
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
                            
                            registrar_kardex(item['id'], vendedor_id, "SALIDA_VENTA", item['cant'], f"Ticket {t_num}")
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
                    except Exception as e: st.error(f"🚨 Error crítico al procesar la venta.")

        if st.session_state.last_ticket_html:
            st.success("✅ Venta procesada exitosamente.")
            st.markdown(st.session_state.last_ticket_html.replace("<script>window.onload = function() { window.print(); }</script>", ""), unsafe_allow_html=True)
            if st.button("🧹 Limpiar Pantalla (Nuevo Cliente)", type="primary"):
                st.session_state.last_ticket_html = None
                st.rerun()

# ==========================================
# 🔄 MÓDULO 3: DEVOLUCIONES
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
                    vendedor_sel = st.selectbox("👤 Usuario que autoriza:", ["..."] + list(vendedor_opciones.keys()))
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
                                st.session_state.iny_dev_cod = ""; st.success("✅ Devuelto."); time.sleep(1); st.rerun()
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
                                usr_id = vendedor_opciones[vendedor_sel]
                                supabase.table("productos").update({"stock_actual": p['stock_actual'] + d_cant}).eq("codigo_barras", p['codigo_barras']).execute()
                                supabase.table("devoluciones").insert({"usuario_id": usr_id, "producto_id": p['codigo_barras'], "cantidad": d_cant, "motivo": m_dev, "dinero_devuelto": d_cant * d_dinero, "estado_producto": "Vuelve a tienda"}).execute()
                                registrar_kardex(p['codigo_barras'], usr_id, "INGRESO_DEVOLUCION", d_cant, m_dev)
                                st.success("✅ Devuelto."); time.sleep(1); st.rerun()
                            else: st.error("Falta motivo o usuario.")
            except: pass

# ==========================================
# 📦 MÓDULO 2: ALMACÉN
# ==========================================
elif menu == "📦 ALMACÉN" and "inventario_ver" in st.session_state.user_perms:
    st.subheader("Gestión de Inventario Maestro")
    t1, t2, t3, t4 = st.tabs(["➕ Ingreso", "⚙️ Catálogos", "📋 Inventario", "📓 KARDEX"])
    
    with t1:
        if "inventario_agregar" in st.session_state.user_perms:
            st.markdown('<div class="css-card">', unsafe_allow_html=True)
            with st.form("form_nuevo_trigger", clear_on_submit=False):
                col_a1, col_a2 = st.columns([3, 1])
                code_a = col_a1.text_input("Dispara el Láser Aquí", key="trigger_almacen")
                if col_a2.form_submit_button("🔍 Buscar"):
                    if code_a:
                        check = supabase.table("productos").select("*").eq("codigo_barras", code_a).execute()
                        if check.data:
                            st.error("⚠️ EL PRODUCTO YA EXISTE. Ve a la pestaña Inventario para sumar stock.")
                        else:
                            st.session_state.iny_alm_cod = code_a
            
            cats, mars, cals, comps = load_data("categorias"), load_data("marcas"), load_data("calidades"), load_data("compatibilidades")

            with st.form("form_nuevo", clear_on_submit=True):
                c_cod = st.text_input("Código de Barras", value=st.session_state.iny_alm_cod)
                c_nom = st.text_input("Nombre del Producto")
                f1, f2, f3, f8 = st.columns(4)
                f_cat = f1.selectbox("Categoría", cats['nombre'].tolist() if not cats.empty else ["Vacío"])
                f_mar = f2.selectbox("Marca", mars['nombre'].tolist() if not mars.empty else ["Vacío"])
                f_cal = f3.selectbox("Calidad", cals['nombre'].tolist() if not cals.empty else ["Original"])
                f_comp = f8.selectbox("Compat", comps['nombre'].tolist() if not comps.empty else ["Universal"])
                
                f4, f5, f6, f7 = st.columns(4)
                f_costo = f4.number_input("Costo (S/.)", min_value=0.0, step=0.5)
                f_pmin = f6.number_input("Precio Mín (S/.)", min_value=0.0, step=0.5)
                f_venta = f5.number_input("Precio Venta (S/.)", min_value=0.0, step=0.5)
                f_stock = f7.number_input("Stock Inicial", min_value=1, step=1)
                
                if st.form_submit_button("🚀 GUARDAR EN BD", type="primary"):
                    if c_cod and c_nom and not cats.empty and not mars.empty:
                        cid, mid = int(cats[cats['nombre'] == f_cat]['id'].iloc[0]), int(mars[mars['nombre'] == f_mar]['id'].iloc[0])
                        supabase.table("productos").insert({"codigo_barras": c_cod, "nombre": c_nom, "categoria_id": cid, "marca_id": mid, "calidad": f_cal, "compatibilidad": f_comp, "costo_compra": f_costo, "precio_lista": f_venta, "precio_minimo": f_pmin, "stock_actual": f_stock, "stock_inicial": f_stock}).execute()
                        registrar_kardex(c_cod, st.session_state.user_id, "INGRESO_COMPRA", f_stock, "Registro Inicial")
                        st.session_state.iny_alm_cod = ""; st.success("✅ Guardado."); time.sleep(1.5); st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
    
    with t2:
        if "inventario_agregar" in st.session_state.user_perms or "inventario_modificar" in st.session_state.user_perms:
            c_left, c_right = st.columns(2)
            c_left2, c_right2 = st.columns(2)
            with c_left:
                st.markdown('<div class="css-card">', unsafe_allow_html=True)
                with st.form("f_cat", clear_on_submit=True):
                    new_c = st.text_input("Crear Categoría")
                    if st.form_submit_button("➕ Guardar") and new_c: supabase.table("categorias").insert({"nombre": new_c}).execute(); st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
            with c_right:
                st.markdown('<div class="css-card">', unsafe_allow_html=True)
                with st.form("f_mar", clear_on_submit=True):
                    new_m = st.text_input("Crear Marca")
                    if st.form_submit_button("➕ Guardar") and new_m: supabase.table("marcas").insert({"nombre": new_m}).execute(); st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
            with c_left2:
                st.markdown('<div class="css-card">', unsafe_allow_html=True)
                with st.form("f_cal", clear_on_submit=True):
                    new_cal = st.text_input("Crear Calidad")
                    if st.form_submit_button("➕ Guardar") and new_cal: supabase.table("calidades").insert({"nombre": new_cal}).execute(); st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
            with c_right2:
                st.markdown('<div class="css-card">', unsafe_allow_html=True)
                with st.form("f_comp", clear_on_submit=True):
                    new_comp = st.text_input("Crear Compatibilidad")
                    if st.form_submit_button("➕ Guardar") and new_comp: supabase.table("compatibilidades").insert({"nombre": new_comp}).execute(); st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

    with t3:
        try:
            prods = supabase.table("productos").select("*, categorias(nombre), marcas(nombre)").execute()
            if prods.data: 
                df = pd.DataFrame(prods.data)
                df['Categoría'] = df['categorias'].apply(lambda x: x['nombre'] if isinstance(x, dict) else 'N/A')
                df['Marca'] = df['marcas'].apply(lambda x: x['nombre'] if isinstance(x, dict) else 'N/A')
                if 'compatibilidad' not in df.columns: df['compatibilidad'] = 'Universal'
                
                if "inventario_modificar" in st.session_state.user_perms:
                    st.write("### ⚡ Reabastecimiento")
                    with st.form("form_add_stock", clear_on_submit=True):
                        col_r1, col_r2 = st.columns([3, 1])
                        selected_prod = col_r1.selectbox("Producto:", ["..."] + [f"{row['codigo_barras']} - {row['nombre']}" for idx, row in df.iterrows()])
                        add_stock = col_r2.number_input("Cantidad", min_value=1, step=1)
                        if st.form_submit_button("➕ Sumar Stock", type="primary"):
                            if selected_prod != "...":
                                cod_up = selected_prod.split(" - ")[0]
                                c_stk = int(df[df['codigo_barras'] == cod_up]['stock_actual'].iloc[0])
                                c_ini = int(df[df['codigo_barras'] == cod_up]['stock_inicial'].iloc[0])
                                supabase.table("productos").update({"stock_actual": c_stk + add_stock, "stock_inicial": c_ini + add_stock}).eq("codigo_barras", cod_up).execute()
                                registrar_kardex(cod_up, st.session_state.user_id, "INGRESO_COMPRA", add_stock, "Reabastecimiento")
                                st.success("✅ Actualizado."); time.sleep(0.5); st.rerun() 
                
                st.divider()
                st.dataframe(df[['codigo_barras', 'nombre', 'Categoría', 'Marca', 'compatibilidad', 'stock_actual', 'precio_lista']], use_container_width=True)
        except: pass

    with t4:
        st.write("#### 📓 Movimientos de Inventario (Kardex)")
        try:
            k_data = supabase.table("movimientos_inventario").select("*, usuarios(nombre_completo)").order("timestamp", desc=True).limit(100).execute()
            if k_data.data:
                df_k = pd.DataFrame(k_data.data)
                df_k['Responsable'] = df_k['usuarios'].apply(lambda x: x['nombre_completo'] if isinstance(x, dict) else 'Sistema')
                df_k['Fecha'] = pd.to_datetime(df_k['timestamp']).dt.tz_convert('America/Lima').dt.strftime('%d/%m/%Y %H:%M')
                st.dataframe(df_k[['Fecha', 'producto_id', 'tipo_movimiento', 'cantidad', 'motivo', 'Responsable']], use_container_width=True)
            else: st.info("Aún no hay movimientos registrados.")
        except Exception as e: st.error("No se pudo cargar el Kardex.")

# ==========================================
# ⚠️ MÓDULO 4: MERMAS
# ==========================================
elif menu == "⚠️ MERMAS/DAÑOS" and "mermas" in st.session_state.user_perms:
    st.subheader("Dar de Baja Productos")
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
# 🧾 MÓDULO: REGISTRO DE TICKETS
# ==========================================
elif menu == "🧾 TICKETS" and "reportes" in st.session_state.user_perms:
    st.subheader("Historial de Comprobantes")
    try:
        tks = supabase.table("ticket_historial").select("ticket_numero, fecha, html_payload").order("fecha", desc=True).limit(50).execute()
        if tks.data:
            df_tks = pd.DataFrame(tks.data)
            df_tks['fecha_format'] = pd.to_datetime(df_tks['fecha']).dt.strftime('%d/%m/%Y %H:%M')
            opciones = [f"{row['ticket_numero']} - {row['fecha_format']}" for _, row in df_tks.iterrows()]
            sel_tk = st.selectbox("Ver ticket:", opciones)
            if sel_tk:
                tk_num = sel_tk.split(" - ")[0]
                html_raw = df_tks[df_tks['ticket_numero'] == tk_num]['html_payload'].iloc[0]
                st.markdown(html_raw.replace("<script>window.onload = function() { window.print(); }</script>", ""), unsafe_allow_html=True)
    except: pass

# ==========================================
# 👥 MÓDULO: GESTIÓN DE VENDEDORES
# ==========================================
elif menu == "👥 VENDEDORES" and "gestion_usuarios" in st.session_state.user_perms:
    st.subheader("Panel de Control Gerencial")
    
    t_u1, t_u2, t_u3, t_u4, t_u5 = st.tabs(["📋 Activos", "➕ Crear Nuevo", "🔑 Reset Password", "🗑️ Dar Baja / Alta", "📊 Análisis Financiero"])
    
    usrs_db = supabase.table("usuarios").select("id, nombre_completo, usuario, clave, turno, permisos, estado").execute()
    df_u = pd.DataFrame()
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
                        supabase.table("usuarios").insert({
                            "nombre_completo": n_nombre, "usuario": n_user, "clave": hashed_pw, 
                            "turno": n_turno, "permisos": n_perms, "estado": "Activo"
                        }).execute()
                        st.success("✅ Vendedor creado."); time.sleep(1.5); st.rerun()
                    except Exception as e: st.error("❌ El Usuario ya existe.")

    with t_u3:
        st.write("#### 🔑 Forzar Nueva Contraseña")
        if not df_activos.empty:
            with st.form("reset_pwd"):
                c_u = st.selectbox("Usuario:", df_activos['usuario'].tolist())
                n_pwd = st.text_input("Escribe la Nueva Contraseña")
                if st.form_submit_button("Actualizar", type="primary"):
                    if n_pwd:
                        hashed_pw = hash_password(n_pwd)
                        supabase.table("usuarios").update({"clave": hashed_pw}).eq("usuario", c_u).execute()
                        st.success("✅ Actualizado."); time.sleep(1); st.rerun()

    with t_u4:
        c1, c2 = st.columns(2)
        with c1:
            st.write("#### 🗑️ Dar de Baja")
            if not df_activos.empty:
                v_borrables = df_activos[df_activos['usuario'] != 'admin']['usuario'].tolist()
                if v_borrables:
                    user_to_del = st.selectbox("Vendedor a Inhabilitar:", v_borrables)
                    if st.button("🗑️ INHABILITAR"):
                        supabase.table("usuarios").update({"estado": "Inactivo"}).eq("usuario", user_to_del).execute()
                        st.success("✅ Inhabilitado."); time.sleep(1); st.rerun()
        with c2:
            st.write("#### ♻️ Dar de Alta")
            if not df_inactivos.empty:
                user_to_react = st.selectbox("Vendedor a Reactivar:", df_inactivos['usuario'].tolist())
                if st.button("✅ ACTIVAR", type="primary"):
                    supabase.table("usuarios").update({"estado": "Activo"}).eq("usuario", user_to_react).execute()
                    st.success("✅ Reactivado."); time.sleep(1); st.rerun()

    # --- NUEVO ANÁLISIS FINANCIERO POR VENDEDOR ---
    with t_u5:
        if not df_activos.empty:
            st.info("📊 Calcula la utilidad neta exacta que este vendedor le genera a tu negocio hoy y este mes.")
            sel_u_nombre = st.selectbox("Selecciona un vendedor:", df_activos['nombre_completo'].tolist())
            sel_u_id = df_activos[df_activos['nombre_completo'] == sel_u_nombre]['id'].iloc[0]
            try:
                today_date = datetime.now().date()
                curr_month = datetime.now().month
                
                # --- ASISTENCIA ---
                ast_db = supabase.table("asistencia").select("*").eq("usuario_id", sel_u_id).execute()
                df_a = pd.DataFrame(ast_db.data)
                h_in, h_out, hrs_hoy = "--:--", "--:--", 0.0
                if not df_a.empty:
                    df_a['ts'] = pd.to_datetime(df_a['timestamp']).dt.tz_convert('America/Lima')
                    df_a['date'] = df_a['ts'].dt.date
                    df_hoy = df_a[df_a['date'] == today_date]
                    if not df_hoy.empty:
                        i_ts = df_hoy[df_hoy['tipo_marcacion'] == 'Ingreso']['ts']
                        s_ts = df_hoy[df_hoy['tipo_marcacion'] == 'Salida']['ts']
                        if not i_ts.empty: h_in = i_ts.min().strftime('%I:%M %p')
                        if not s_ts.empty: h_out = s_ts.max().strftime('%I:%M %p')
                        if not i_ts.empty and not s_ts.empty: hrs_hoy = (s_ts.max() - i_ts.min()).total_seconds() / 3600

                # --- FINANZAS REALES (Ventas vs Costos) ---
                v_det = supabase.table("ventas_detalle").select("subtotal, cantidad, productos(costo_compra), ventas_cabecera(created_at, usuario_id)").execute()
                v_hoy_ventas, v_hoy_costo, v_hoy_utilidad = 0.0, 0.0, 0.0
                
                if v_det.data:
                    df_v = pd.DataFrame(v_det.data)
                    df_v['ts'] = pd.to_datetime(df_v['ventas_cabecera'].apply(lambda x: x.get('created_at', '2000-01-01') if isinstance(x, dict) else '2000-01-01')).dt.tz_convert('America/Lima')
                    df_v['usr_id'] = df_v['ventas_cabecera'].apply(lambda x: x.get('usuario_id', 0) if isinstance(x, dict) else 0)
                    df_v['costo_unit'] = df_v['productos'].apply(lambda x: float(x.get('costo_compra', 0)) if isinstance(x, dict) else 0.0)
                    df_v['costo_tot'] = df_v['costo_unit'] * df_v['cantidad']
                    
                    df_v_usr = df_v[df_v['usr_id'] == sel_u_id]
                    df_hoy_v = df_v_usr[df_v_usr['ts'].dt.date == today_date]
                    
                    v_hoy_ventas = df_hoy_v['subtotal'].sum()
                    v_hoy_costo = df_hoy_v['costo_tot'].sum()
                    v_hoy_utilidad = v_hoy_ventas - v_hoy_costo
                
                st.markdown(f"**Métricas del Día (Hoy)**")
                c1, c2, c3, c4 = st.columns(4)
                c1.markdown(f"<div class='metric-box'><div class='metric-title'>Ventas Brutas</div><div class='metric-value-small metric-green'>S/. {v_hoy_ventas:.2f}</div></div>", unsafe_allow_html=True)
                c2.markdown(f"<div class='metric-box'><div class='metric-title'>Costo (Capital)</div><div class='metric-value-small metric-orange'>S/. {v_hoy_costo:.2f}</div></div>", unsafe_allow_html=True)
                c3.markdown(f"<div class='metric-box' style='border:2px solid #8b5cf6;'><div class='metric-title'>Utilidad Neta</div><div class='metric-value-small metric-purple'>S/. {v_hoy_utilidad:.2f}</div></div>", unsafe_allow_html=True)
                c4.markdown(f"<div class='metric-box'><div class='metric-title'>Horas Trabajo</div><div class='metric-value-small'>{hrs_hoy:.1f} Hrs</div></div>", unsafe_allow_html=True)
            except Exception as e: pass

# ==========================================
# 📊 MÓDULO 5: REPORTES Y CIERRE
# ==========================================
elif menu == "📊 REPORTES" and ("cierre_caja" in st.session_state.user_perms or "reportes" in st.session_state.user_perms):
    st.subheader("Auditoría Financiera y Cierre")
    
    if st.session_state.ticket_cierre:
        tk = st.session_state.ticket_cierre
        st.success("✅ Caja cerrada.")
        
        # --- TICKET Z RESTAURADO COMPLETO ---
        st.markdown(f"""
        <div class="ticket-termico">
            <center><b>ACCESORIOS JORDAN</b><br><b>REPORTE Z (FIN TURNO)</b></center>
            --------------------------------<br>
            FECHA CIERRE: {tk['fecha']}<br>
            CAJERO: {st.session_state.user_name}<br>
            --------------------------------<br>
            <b>💰 INGRESOS BRUTOS: S/. {tk['tot_ventas']:.2f}</b><br>
            - En Efectivo: S/. {tk['ventas_efectivo']:.2f}<br>
            - En Digital: S/. {tk['ventas_digital']:.2f}<br>
            Cant. Vendida: {tk['cant_vendida']} ud.<br>
            --------------------------------<br>
            <b>📉 COSTOS Y MERMAS:</b><br>
            Capital Invertido: S/. {tk['capital_inv']:.2f}<br>
            Mermas (Daños): S/. {tk['tot_merma']:.2f}<br>
            --------------------------------<br>
            <b>🔄 DEVOLUCIONES:</b><br>
            Dinero Reembolsado: S/. {tk['tot_dev']:.2f}<br>
            --------------------------------<br>
            <b>🏦 CUADRE FINAL (A RENDIR):</b><br>
            EFECTIVO EN CAJA: S/. {tk['caja_efectivo']:.2f}<br>
            UTILIDAD NETA: S/. {tk['utilidad']:.2f}<br>
            --------------------------------<br>
        </div>
        """, unsafe_allow_html=True)
        if st.button("🧹 Iniciar Nuevo Turno", type="primary"):
            st.session_state.ticket_cierre = None
            st.rerun()
    else:
        try:
            last_cierre_dt = get_last_cierre_dt()
            st.caption(f"⏱️ Monitoreando operaciones desde: {last_cierre_dt.strftime('%d/%m/%Y %H:%M')}")
            
            cabeceras = supabase.table("ventas_cabecera").select("*").gte("created_at", last_cierre_dt.isoformat()).execute()
            detalles = supabase.table("ventas_detalle").select("*, productos(costo_compra), ventas_cabecera(created_at, usuario_id)").execute()
            devs = supabase.table("devoluciones").select("*, productos(costo_compra)").gte("created_at", last_cierre_dt.isoformat()).execute()
            mermas = supabase.table("mermas").select("*").gte("created_at", last_cierre_dt.isoformat()).execute()
            
            tot_ventas, ventas_efectivo, ventas_digital, tot_costo, tot_devs, costo_recup, tot_merma = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
            cant_ven = 0
            
            if cabeceras.data:
                df_cab = pd.DataFrame(cabeceras.data)
                ventas_efectivo = df_cab[df_cab['metodo_pago'] == 'Efectivo']['total_venta'].sum()
                ventas_digital = df_cab[df_cab['metodo_pago'].isin(['Yape', 'Plin', 'Tarjeta VISA/MC'])]['total_venta'].sum()
                tot_ventas = df_cab['total_venta'].sum()

            if detalles.data:
                df_rep = pd.DataFrame(detalles.data)
                df_rep['created_dt'] = pd.to_datetime(df_rep['ventas_cabecera'].apply(lambda x: x['created_at'] if isinstance(x, dict) else '2000-01-01'), utc=True)
                df_rep_filtered = df_rep[df_rep['created_dt'] > last_cierre_dt]
                if not df_rep_filtered.empty:
                    df_rep_filtered['Costo'] = df_rep_filtered['productos'].apply(lambda x: float(x['costo_compra']) if isinstance(x, dict) else 0.0) * df_rep_filtered['cantidad']
                    tot_costo = df_rep_filtered['Costo'].sum()
                    cant_ven = int(df_rep_filtered['cantidad'].sum())
                
            if devs.data:
                df_dev_filt = pd.DataFrame(devs.data)
                if not df_dev_filt.empty:
                    df_dev_filt['Costo'] = df_dev_filt['productos'].apply(lambda x: float(x['costo_compra']) if isinstance(x, dict) else 0.0) * df_dev_filt['cantidad']
                    tot_devs = df_dev_filt['dinero_devuelto'].sum()
                    costo_recup = df_dev_filt['Costo'].sum()

            if mermas.data:
                df_mer_filt = pd.DataFrame(mermas.data)
                if not df_mer_filt.empty:
                    tot_merma = df_mer_filt['perdida_monetaria'].sum()
                
            caja_efectivo_pura = ventas_efectivo - tot_devs
            capital_real = tot_costo - costo_recup
            utilidad_pura = (tot_ventas - tot_devs) - capital_real - tot_merma
            
            if "reportes" in st.session_state.user_perms:
                st.markdown("##### 💵 Balance Financiero (Dónde está el dinero)")
                c1, c2, c3, c4 = st.columns(4)
                c1.markdown(f"<div class='metric-box' style='border:2px solid #3b82f6;'><div class='metric-title'>TOTAL BRUTO</div><div class='metric-value metric-blue'>S/. {tot_ventas:.2f}</div></div>", unsafe_allow_html=True)
                c2.markdown(f"<div class='metric-box'><div class='metric-title'>Efectivo</div><div class='metric-value'>S/. {ventas_efectivo:.2f}</div></div>", unsafe_allow_html=True)
                c3.markdown(f"<div class='metric-box'><div class='metric-title'>Digital (Yape/Tarj)</div><div class='metric-value metric-purple'>S/. {ventas_digital:.2f}</div></div>", unsafe_allow_html=True)
                c4.markdown(f"<div class='metric-box' style='border:2px solid #10b981;'><div class='metric-title'>CAJA EFECTIVA</div><div class='metric-value metric-green'>S/. {caja_efectivo_pura:.2f}</div></div>", unsafe_allow_html=True)
                
                st.write("")
                st.markdown("##### 📈 Rendimiento Operativo (Utilidad Global)")
                c5, c6, c7 = st.columns(3)
                c5.markdown(f"<div class='metric-box'><div class='metric-title'>Capital Invertido (Costo)</div><div class='metric-value metric-orange'>S/. {capital_real:.2f}</div></div>", unsafe_allow_html=True)
                c6.markdown(f"<div class='metric-box'><div class='metric-title'>Mermas (Pérdidas)</div><div class='metric-value metric-red'>- S/. {tot_merma:.2f}</div></div>", unsafe_allow_html=True)
                c7.markdown(f"<div class='metric-box'><div class='metric-title'>UTILIDAD NETA PURA</div><div class='metric-value metric-green'>S/. {utilidad_pura:.2f}</div></div>", unsafe_allow_html=True)
            
            if "cierre_caja" in st.session_state.user_perms:
                st.markdown('<div class="cierre-box">', unsafe_allow_html=True)
                with st.form("form_cierre", clear_on_submit=True):
                    if st.form_submit_button("🔒 APROBAR CIERRE DE CAJA", type="primary"):
                        supabase.table("cierres_caja").insert({"total_ventas": tot_ventas, "total_devoluciones": tot_devs, "utilidad": utilidad_pura, "total_mermas": tot_merma}).execute()
                        st.session_state.ticket_cierre = {
                            'fecha': datetime.now().strftime('%d/%m/%Y %H:%M'),
                            'cant_vendida': cant_ven, 'tot_ventas': tot_ventas, 
                            'ventas_efectivo': ventas_efectivo, 'ventas_digital': ventas_digital,
                            'capital_inv': capital_real,
                            'tot_dev': tot_devs, 'tot_merma': tot_merma,
                            'caja_efectivo': caja_efectivo_pura, 'utilidad': utilidad_pura
                        }
                        st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
        except Exception as e: st.error(f"Error al cargar reportes.")
