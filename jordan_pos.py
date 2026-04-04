import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client
import pandas as pd
from datetime import datetime
import time
import os
import bcrypt
import plotly.express as px
import plotly.graph_objects as go

# ==========================================
# 1. CONEXIÓN SEGURA A LA BASE DE DATOS
# ==========================================
URL_SUPABASE = st.secrets["SUPABASE_URL"]
KEY_SUPABASE = st.secrets["SUPABASE_KEY"]
supabase = create_client(URL_SUPABASE, KEY_SUPABASE)

st.set_page_config(page_title="JORDAN POS ERP", layout="wide", page_icon="📱", initial_sidebar_state="expanded")

# ==========================================
# 1.5 RELOJ INTERNO (FORZAR HORA PERÚ)
# ==========================================
def get_now():
    return pd.Timestamp.now('America/Lima').to_pydatetime()

# ==========================================
# 2. SEGURIDAD Y ENCRIPTACIÓN
# ==========================================
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(input_password, stored_password):
    if stored_password.startswith("$2"): 
        return bcrypt.checkpw(input_password.encode('utf-8'), stored_password.encode('utf-8'))
    return input_password == stored_password

# ==========================================
# 3. DISEÑO VISUAL UX/UI (ESTILO PREMIUM)
# ==========================================
st.markdown("""
    <style>
    :root { --primary-color: #00b4d8; --success-color: #00b4d8; --danger-color: #ef4444; --warning-color: #f59e0b; }
    .main-header { font-size: 26px; font-weight: 900; color: #1e293b; padding: 15px; border-bottom: 2px solid #e2e8f0; margin-bottom: 20px; background: transparent;}
    .css-card { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); border-left: 5px solid var(--primary-color); margin-bottom: 15px; }
    .metric-box { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); text-align: center; border: 1px solid #f1f5f9; transition: transform 0.2s;}
    .metric-box:hover { transform: translateY(-3px); box-shadow: 0 8px 15px rgba(0,0,0,0.1); }
    .metric-title { font-size: 12px; color: #64748b; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 5px;}
    .metric-value { font-size: 26px; font-weight: 900; color: #0f172a;}
    .metric-value-small { font-size: 18px; font-weight: 800; color: #0f172a;}
    .metric-green { color: #10b981; }
    .metric-red { color: #ef4444; }
    .metric-orange { color: #f59e0b; }
    .metric-blue { color: #3b82f6; }
    .metric-purple { color: #8b5cf6; }
    .ticket-termico { background: white; color: black; font-family: 'Courier New', monospace; padding: 15px; border: 1px dashed #333; width: 100%; max-width: 320px; margin: 0 auto; line-height: 1.2; font-size: 13px; }
    .linea-corte { text-align: center; margin: 25px 0; border-bottom: 2px dashed #94a3b8; color: #64748b; font-size: 12px; font-weight: bold;}
    .btn-checkout>button { background-color: #00b4d8; color: white; height: 3.5em; font-size: 18px; border-radius: 8px;}
    .btn-checkout>button:hover { background-color: #0096c7; color: white;}
    div[data-testid="stNumberInput"] button { background-color: #f1f5f9; }
    </style>
    """, unsafe_allow_html=True)

components.html("""
    <script>
    const inputs = window.parent.document.querySelectorAll('input[type="text"]');
    if(inputs.length > 0) { inputs[0].focus(); }
    </script>
    """, height=0)

# ==========================================
# 4. FUNCIONES MAESTRAS Y MOTOR DE COSTOS
# ==========================================
keys_to_init = {
    'logged_in': False, 'user_id': None, 'user_name': "", 'user_perms': [],
    'carrito': [], 'last_ticket_html': None, 'print_trigger': False, 'ticket_cierre': None
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

def get_lista_usuarios():
    try:
        res = supabase.table("usuarios").select("id, nombre_completo, usuario").eq("estado", "Activo").execute()
        return res.data if res.data else []
    except: return []

def registrar_kardex(producto_id, usuario_id, tipo_movimiento, cantidad, motivo):
    try: supabase.table("movimientos_inventario").insert({"producto_id": str(producto_id), "usuario_id": usuario_id, "tipo_movimiento": tipo_movimiento, "cantidad": cantidad, "motivo": motivo}).execute()
    except: pass

def get_last_cierre_dt():
    try:
        c = supabase.table("cierres_caja").select("*").order("fecha_cierre", desc=True).limit(1).execute()
        if c.data: return pd.to_datetime(c.data[0]['fecha_cierre'], utc=True)
    except: pass
    return pd.to_datetime("2000-01-01T00:00:00Z", utc=True)

# 🛡️ MOTOR MATEMÁTICO 100% SEGURO (VERSIÓN 5.2 - COSTEO HISTÓRICO)
def calcular_costo_y_cantidad_ventas(cab_data):
    if not cab_data: return 0.0, 0
    try:
        df_cab = pd.DataFrame(cab_data)
        
        valid_ids = []
        if 'id' in df_cab.columns:
            valid_ids.extend(df_cab['id'].astype(str).tolist())
        if 'ticket_numero' in df_cab.columns:
            valid_ids.extend(df_cab['ticket_numero'].astype(str).tolist())
            
        if not valid_ids: return 0.0, 0

        det_res = supabase.table("ventas_detalle").select("*").order("id", desc=True).limit(8000).execute()
        if not det_res.data: return 0.0, 0
        
        df_det = pd.DataFrame(det_res.data)
        df_det['venta_id_str'] = df_det['venta_id'].astype(str)
        
        df_det_filtered = df_det[df_det['venta_id_str'].isin(valid_ids)]
        
        if df_det_filtered.empty: return 0.0, 0
        
        cant_total = int(df_det_filtered['cantidad'].sum())
        
        # 🛡️ LÓGICA DE BLINDAJE: Si la tabla tiene la columna histórica, la usamos
        if 'costo_unitario_historico' in df_det_filtered.columns:
            df_det_filtered['costo_unitario_historico'] = df_det_filtered['costo_unitario_historico'].fillna(0.0).astype(float)
            
            # Para ventas súper antiguas (antes del blindaje), buscamos el costo como respaldo
            ventas_sin_costo = df_det_filtered[df_det_filtered['costo_unitario_historico'] == 0]
            if not ventas_sin_costo.empty:
                prod_ids = ventas_sin_costo['producto_id'].astype(str).unique().tolist()
                p_res = supabase.table("productos").select("codigo_barras, costo_compra").in_("codigo_barras", prod_ids).execute()
                c_map = {str(p['codigo_barras']): float(p.get('costo_compra', 0)) for p in p_res.data} if p_res.data else {}
                df_det_filtered.loc[df_det_filtered['costo_unitario_historico'] == 0, 'costo_unitario_historico'] = df_det_filtered['producto_id'].astype(str).apply(lambda x: c_map.get(x, 0.0))
            
            costo_total = float((df_det_filtered['costo_unitario_historico'] * df_det_filtered['cantidad']).sum())
        else:
            # Respaldo por si no se aplicó el código SQL en Supabase
            prod_ids = df_det_filtered['producto_id'].astype(str).unique().tolist()
            p_res = supabase.table("productos").select("codigo_barras, costo_compra").in_("codigo_barras", prod_ids).execute()
            c_map = {str(p['codigo_barras']): float(p.get('costo_compra', 0)) for p in p_res.data} if p_res.data else {}
            df_det_filtered['costo_unit'] = df_det_filtered['producto_id'].astype(str).apply(lambda x: c_map.get(x, 0.0))
            costo_total = float((df_det_filtered['costo_unit'] * df_det_filtered['cantidad']).sum())
        
        return costo_total, cant_total
    except Exception as e:
        return 0.0, 0

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
    except: st.error("Error de base de datos.")
    return False

# ==========================================
# 5. SIDEBAR Y ACCESOS
# ==========================================
st.sidebar.markdown("### 🏢 Accesos del Sistema")

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

menu_options = ["🛒 VENTAS (POS)", "🔄 DEVOLUCIONES"]
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
# 📈 MÓDULO 0: DASHBOARD GENERAL
# ==========================================
if menu == "📈 DASHBOARD GENERAL":
    st.markdown('<div class="main-header">Panel de Control General</div>', unsafe_allow_html=True)
    try:
        v_db = supabase.table("ventas_cabecera").select("*").execute()
        if v_db.data:
            df_v = pd.DataFrame(v_db.data)
            df_v['fecha'] = pd.to_datetime(df_v['created_at']).dt.tz_convert('America/Lima').dt.date
            
            hoy = get_now().date()
            mes = get_now().month
            
            v_hoy = df_v[df_v['fecha'] == hoy]['total_venta'].sum()
            df_mes = df_v[pd.to_datetime(df_v['created_at']).dt.tz_convert('America/Lima').dt.month == mes]
            v_mes = df_mes['total_venta'].sum()
            pedidos_mes = len(df_mes)
            ticket_promedio = v_mes / pedidos_mes if pedidos_mes > 0 else 0
            
            col_dash1, col_dash2, col_dash3 = st.columns([1, 1, 2])
            
            with col_dash1:
                fig_g1 = go.Figure(go.Indicator(
                    mode = "gauge+number",
                    value = v_mes,
                    title = {'text': "Ventas del Mes (S/.)"},
                    gauge = {'axis': {'range': [None, max(v_mes*1.5, 1000)]}, 'bar': {'color': "#00b4d8"}}
                ))
                fig_g1.update_layout(height=250, margin=dict(l=10, r=10, t=40, b=10))
                st.plotly_chart(fig_g1, use_container_width=True)

            with col_dash2:
                fig_g2 = go.Figure(go.Indicator(
                    mode = "gauge+number",
                    value = v_hoy,
                    title = {'text': "Ventas de Hoy (S/.)"},
                    gauge = {'axis': {'range': [None, max(v_hoy*2, 100)]}, 'bar': {'color': "#10b981"}}
                ))
                fig_g2.update_layout(height=250, margin=dict(l=10, r=10, t=40, b=10))
                st.plotly_chart(fig_g2, use_container_width=True)

            with col_dash3:
                ultimos_7 = df_v[df_v['fecha'] >= (hoy - pd.Timedelta(days=7))]
                if not ultimos_7.empty:
                    grafico_data = ultimos_7.groupby('fecha')['total_venta'].sum().reset_index()
                    fig_area = px.area(grafico_data, x='fecha', y='total_venta', title="Evolución de Ventas (Últimos 7 Días)", markers=True)
                    fig_area.update_traces(line_shape='spline', fillcolor='rgba(0, 180, 216, 0.2)', line_color='#00b4d8')
                    fig_area.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=250, margin=dict(l=0, r=0, t=40, b=0))
                    st.plotly_chart(fig_area, use_container_width=True)

            st.divider()
            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(f"<div class='metric-box'><div class='metric-title'>Ticket Promedio</div><div class='metric-value metric-blue'>S/. {ticket_promedio:.2f}</div></div>", unsafe_allow_html=True)
            c2.markdown(f"<div class='metric-box'><div class='metric-title'>Total Pedidos (Mes)</div><div class='metric-value'>{pedidos_mes}</div></div>", unsafe_allow_html=True)
            c3.markdown(f"<div class='metric-box'><div class='metric-title'>Ventas Hoy</div><div class='metric-value metric-green'>S/. {v_hoy:.2f}</div></div>", unsafe_allow_html=True)
            c4.markdown(f"<div class='metric-box' style='border-color:#8b5cf6;'><div class='metric-title'>Ventas Totales Mes</div><div class='metric-value metric-purple'>S/. {v_mes:.2f}</div></div>", unsafe_allow_html=True)
        else: st.info("No hay ventas registradas aún.")
    except: pass

# ==========================================
# 🛒 MÓDULO 1: VENTAS (POS)
# ==========================================
elif menu == "🛒 VENTAS (POS)":
    st.markdown('<div class="main-header">Punto de Venta (POS)</div>', unsafe_allow_html=True)
    if st.session_state.last_ticket_html:
        st.success("✅ Venta procesada exitosamente. Ticket generado:")
        html_visible = st.session_state.last_ticket_html.replace("<script>window.onload=function(){window.print();}</script>", "")
        st.markdown(html_visible, unsafe_allow_html=True)
        if st.session_state.print_trigger:
            components.html(st.session_state.last_ticket_html, height=0)
            st.session_state.print_trigger = False
        if st.button("🧹 Atender Siguiente Cliente", type="primary"):
            st.session_state.last_ticket_html = None
            st.rerun()

    col_v1, col_v2 = st.columns([1.2, 1.8])
    
    with col_v1:
        st.write("**🔍 Búsqueda Rápida**")
        with st.form("form_barcode", clear_on_submit=True):
            codigo = st.text_input("Dispara el Láser (Código Numérico):", key="pos_input")
            if st.form_submit_button("Añadir por Láser", use_container_width=True):
                if codigo: procesar_codigo_venta(codigo); st.rerun()

        st.divider()
        st.write("**Búsqueda Manual (Autocompletado)**")
        prods_df = load_data_cached("productos")
        if not prods_df.empty:
            nombres_prods = prods_df['nombre'].tolist()
            search_nom = st.selectbox("Escribe el nombre del producto:", ["..."] + nombres_prods)
            if search_nom != "...":
                p_sel = prods_df[prods_df['nombre'] == search_nom].iloc[0]
                c_p1, c_p2 = st.columns([3, 1])
                c_p1.write(f"**{p_sel['nombre']}** - S/.{p_sel['precio_lista']} (Stock: {p_sel['stock_actual']})")
                if c_p2.button("Añadir", key="btn_add_nom"):
                    if procesar_codigo_venta(p_sel['codigo_barras']): st.rerun()

    with col_v2:
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        st.write("#### 🛍️ Carrito de Compras")
        if not st.session_state.carrito: 
            st.info("El carrito está vacío.")
        else:
            total_venta = 0.0
            costo_total = 0.0
            
            st.markdown("<div style='font-size:12px; color:gray; font-weight:bold; display:flex;'><div style='width:45%;'>Producto</div><div style='width:25%; text-align:center;'>Precio Final</div><div style='width:20%; text-align:center;'>Cant.</div></div>", unsafe_allow_html=True)
            st.write("")

            for i, item in enumerate(st.session_state.carrito):
                c1, c2, c3, c4 = st.columns([4, 2.5, 2.5, 1])
                c1.markdown(f"<div style='padding-top:8px;'><b>{item['nombre']}</b></div>", unsafe_allow_html=True)
                
                nuevo_p = c2.number_input("Precio", min_value=float(item['p_min']), value=float(item['precio']), step=1.0, key=f"p_{i}", label_visibility="collapsed")
                st.session_state.carrito[i]['precio'] = nuevo_p
                
                nueva_c = c3.number_input("Cant.", min_value=1, max_value=int(item['stock_max']), value=int(item['cant']), step=1, key=f"c_{i}", label_visibility="collapsed")
                st.session_state.carrito[i]['cant'] = nueva_c
                
                if c4.button("🗑️", key=f"d_{i}"):
                    st.session_state.carrito.pop(i); st.rerun()
                    
                subtotal = nuevo_p * nueva_c
                total_venta += subtotal
                costo_total += (item['costo'] * nueva_c)

            st.markdown(f"<div style='text-align:right; margin-top:20px;'><h1 style='color:#00b4d8; font-size:45px;'>TOTAL: S/. {total_venta:.2f}</h1></div>", unsafe_allow_html=True)

            with st.expander("💸 PAGO Y FACTURACIÓN", expanded=True):
                lista_vendedores = get_lista_usuarios()
                vendedor_opciones = {v['usuario']: v['id'] for v in lista_vendedores}
                vendedor_seleccionado = st.selectbox("👤 Vendedor a cargo:", ["Seleccionar..."] + list(vendedor_opciones.keys()))

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
                ref_pago = ""
                if pago != "Efectivo":
                    ref_pago = cp2.text_input("N° de Referencia (Obligatorio para digitales)")

                st.markdown('<div class="btn-checkout">', unsafe_allow_html=True)
                
                if st.button("FINALIZAR VENTA E IMPRIMIR", use_container_width=True):
                    if vendedor_seleccionado == "Seleccionar...": st.error("🛑 Selecciona tu usuario (Vendedor).")
                    elif pago != "Efectivo" and not ref_pago: st.error("🛑 Ingresa la referencia del pago.")
                    else:
                        try:
                            vendedor_id = vendedor_opciones[vendedor_seleccionado]
                            t_num = f"AJ-{int(time.time())}"
                            
                            datos_insert = {
                                "ticket_numero": t_num, 
                                "total_venta": total_venta, 
                                "metodo_pago": pago, 
                                "tipo_comprobante": "Ticket",
                                "usuario_id": vendedor_id, 
                                "referencia_pago": ref_pago
                            }
                            cli_id = cliente_dict.get(cliente_sel, None) if cliente_sel != "Público General (Sin registrar)" else None
                            if cli_id is not None: datos_insert["cliente_id"] = cli_id
                            
                            try: supabase.table("ventas_cabecera").insert(datos_insert).execute()
                            except Exception:
                                if "cliente_id" in datos_insert: del datos_insert["cliente_id"]
                                supabase.table("ventas_cabecera").insert(datos_insert).execute()

                            v_res = supabase.table("ventas_cabecera").select("*").eq("ticket_numero", t_num).execute()
                            v_id = str(t_num) 
                            if v_res.data: v_id = str(v_res.data[0].get('id', t_num))
                            
                            items_html = ""
                            for it in st.session_state.carrito:
                                # 🛡️ AQUÍ ESTÁ LA MAGIA: Guardamos el costo exacto dentro del detalle (Fotografía)
                                try:
                                    supabase.table("ventas_detalle").insert({
                                        "venta_id": v_id, 
                                        "producto_id": str(it['id']), 
                                        "cantidad": it['cant'], 
                                        "precio_unitario": it['precio'], 
                                        "subtotal": it['precio'] * it['cant'],
                                        "costo_unitario_historico": it['costo'] # <- La fotografía
                                    }).execute()
                                except: pass 
                                
                                try:
                                    stk = supabase.table("productos").select("stock_actual").eq("codigo_barras", it['id']).execute()
                                    if stk.data: supabase.table("productos").update({"stock_actual": stk.data[0]['stock_actual'] - it['cant']}).eq("codigo_barras", it['id']).execute()
                                except: pass
                                
                                registrar_kardex(it['id'], vendedor_id, "SALIDA_VENTA", it['cant'], f"Ticket {t_num}")
                                items_html += f"{it['nombre'][:20]} <br> {it['cant']} x S/. {it['precio']:.2f} = S/. {it['precio']*it['cant']:.2f}<br>"
                            
                            fecha_tk = get_now().strftime('%d/%m/%Y %H:%M')
                            nom_cliente = cliente_sel.split(' - ')[0] if cli_id else 'General'
                            
                            c_base = f"--------------------------------<br>TICKET: {t_num}<br>FECHA: {fecha_tk}<br>CAJERO: {vendedor_seleccionado}<br>CLIENTE: {nom_cliente}<br>--------------------------------<br>{items_html}--------------------------------<br><b>TOTAL PAGADO: S/. {total_venta:.2f}</b><br>MÉTODO: {pago}<br>"
                            tk_html = f"<div class='ticket-termico' style='text-align:left;'><center><b>ACCESORIOS JORDAN</b><br>COPIA CLIENTE</center><br>{c_base}<center>¡Gracias por su compra!</center></div><div class='linea-corte'><span>✂️</span></div><div class='ticket-termico' style='text-align:left;'><center><b>ACCESORIOS JORDAN</b><br>CONTROL INTERNO</center><br>{c_base}</div><script>window.onload=function(){{window.print();}}</script>"
                            
                            try: supabase.table("ticket_historial").insert({"ticket_numero": t_num, "usuario_id": vendedor_id, "html_payload": tk_html}).execute()
                            except: pass
                            
                            st.session_state.last_ticket_html = tk_html
                            st.session_state.print_trigger = True
                            st.session_state.carrito = []
                            st.rerun() 
                        except Exception as e: st.error(f"🚨 La venta se guardó, pero hubo una desconexión menor con la base de datos. {e}")
                st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 🔄 MÓDULO 2: DEVOLUCIONES
# ==========================================
elif menu == "🔄 DEVOLUCIONES":
    st.markdown('<div class="main-header">Gestión de Devoluciones</div>', unsafe_allow_html=True)
    lista_vendedores = get_lista_usuarios()
    vendedor_opciones = {v['usuario']: v['id'] for v in lista_vendedores}
    
    tipo_b = st.radio("Método de búsqueda:", ["Por N° de Ticket", "Por Producto (Láser o Nombre)"], horizontal=True)

    if tipo_b == "Por N° de Ticket":
        search_dev = st.text_input("Ingresa N° de Ticket (Ej. AJ-123456)")
        if search_dev:
            try:
                v_cab = supabase.table("ventas_cabecera").select("*").eq("ticket_numero", search_dev.upper()).execute()
                if v_cab.data:
                    v_row = v_cab.data[0]
                    v_id_search = str(v_row.get('id', v_row.get('ticket_numero')))
                    st.success(f"✅ Ticket Encontrado. Pago: {v_row['metodo_pago']}")
                    v_det = supabase.table("ventas_detalle").select("*").eq("venta_id", v_id_search).execute()
                    
                    if v_det.data:
                        vendedor_sel = st.selectbox("👤 Vendedor que autoriza:", ["..."] + list(vendedor_opciones.keys()))
                        for d in v_det.data:
                            p_nom = "Producto Vendido"
                            try: 
                                p_res = supabase.table("productos").select("nombre").eq("codigo_barras", d['producto_id']).execute()
                                if p_res.data: p_nom = p_res.data[0]['nombre']
                            except: pass
                            
                            col_d1, col_d2 = st.columns([3, 1])
                            col_d1.write(f"**{p_nom}** - Compró: {d['cantidad']} ud.")
                            if col_d2.button("Devolver", key=f"dev_{d['id']}"):
                                if vendedor_sel != "...":
                                    usr_id = vendedor_opciones[vendedor_sel]
                                    p_s = supabase.table("productos").select("stock_actual").eq("codigo_barras", d['producto_id']).execute()
                                    supabase.table("productos").update({"stock_actual": p_s.data[0]['stock_actual'] + d['cantidad']}).eq("codigo_barras", d['producto_id']).execute()
                                    supabase.table("devoluciones").insert({"usuario_id": usr_id, "producto_id": d['producto_id'], "cantidad": d['cantidad'], "motivo": "Devolución Ticket", "dinero_devuelto": d['subtotal'], "estado_producto": "Vuelve a tienda"}).execute()
                                    registrar_kardex(d['producto_id'], usr_id, "INGRESO_DEVOLUCION", d['cantidad'], f"Ticket {search_dev.upper()}")
                                    st.session_state.iny_dev_cod = ""; st.success("✅ Devuelto."); time.sleep(1); st.rerun()
                                else: st.error("Selecciona tu usuario.")
                else: st.warning("Ticket no encontrado.")
            except: pass
            
    else: 
        col_d1, col_d2 = st.columns(2)
        d_cod = col_d1.text_input("Dispara Láser (Código)")
        prods_df = load_data_cached("productos")
        d_nom = col_d2.selectbox("O Buscar por Nombre (Autocompletado)", ["..."] + (prods_df['nombre'].tolist() if not prods_df.empty else []))
        
        cod_to_search = None
        if d_cod: cod_to_search = d_cod
        elif d_nom != "...": cod_to_search = prods_df[prods_df['nombre'] == d_nom]['codigo_barras'].iloc[0]

        if cod_to_search:
            try:
                p_db = supabase.table("productos").select("*").eq("codigo_barras", cod_to_search).execute()
                if p_db.data:
                    p = p_db.data[0]
                    st.write(f"**Producto:** {p['nombre']} | **Stock Actual:** {p['stock_actual']}")
                    with st.form("form_dev_libre"):
                        vendedor_sel = st.selectbox("👤 Vendedor que autoriza:", ["..."] + list(vendedor_opciones.keys()))
                        c1, c2 = st.columns(2)
                        d_cant = c1.number_input("Cantidad a devolver", min_value=1, step=1)
                        d_dinero = c2.number_input("Dinero Devuelto al Cliente (S/.)", value=float(p['precio_lista']))
                        m_dev = st.text_input("Motivo de la devolución")
                        if st.form_submit_button("🔁 DEVOLVER AL INVENTARIO"):
                            if m_dev and vendedor_sel != "...":
                                usr_id = vendedor_opciones[vendedor_sel]
                                supabase.table("productos").update({"stock_actual": p['stock_actual'] + d_cant}).eq("codigo_barras", p['codigo_barras']).execute()
                                supabase.table("devoluciones").insert({"usuario_id": usr_id, "producto_id": p['codigo_barras'], "cantidad": d_cant, "motivo": m_dev, "dinero_devuelto": d_cant * d_dinero, "estado_producto": "Vuelve a tienda"}).execute()
                                registrar_kardex(p['codigo_barras'], usr_id, "INGRESO_DEVOLUCION", d_cant, m_dev)
                                st.success("✅ Devuelto exitosamente."); time.sleep(1); st.rerun()
                            else: st.error("Falta motivo o usuario.")
            except: pass

# ==========================================
# 🤝 MÓDULO 3: CLIENTES (CRM)
# ==========================================
elif menu == "🤝 CLIENTES (CRM)":
    st.markdown('<div class="main-header">Base de Datos de Clientes</div>', unsafe_allow_html=True)
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
    st.markdown('<div class="main-header">Salidas de Caja Chica</div>', unsafe_allow_html=True)
    t1, t2 = st.tabs(["📝 Registrar Gasto", "📋 Historial Hoy"])
    with t1:
        with st.form("form_gasto"):
            tipo = st.selectbox("Categoría", ["Alimentación", "Pasajes/Movilidad", "Pago Servicios", "Compras Menores", "Otro"])
            desc = st.text_input("Descripción breve")
            monto = st.number_input("Monto retirado de caja (S/.)", min_value=0.1, step=1.0)
            if st.form_submit_button("Confirmar Salida", type="primary"):
                try:
                    supabase.table("gastos").insert({"usuario_id": st.session_state.user_id, "tipo_gasto": tipo, "descripcion": desc, "monto": monto}).execute()
                    st.success("✅ Gasto registrado."); time.sleep(1); st.rerun()
                except: st.error("Asegúrate de crear la tabla de gastos.")
    with t2:
        try:
            hoy_str = get_now().strftime('%Y-%m-%d')
            gst = supabase.table("gastos").select("*, usuarios(nombre_completo)").gte("fecha", hoy_str).execute()
            if gst.data:
                df_g = pd.DataFrame(gst.data)
                df_g['Usuario'] = df_g['usuarios'].apply(lambda x: x['nombre_completo'] if isinstance(x, dict) else '')
                st.dataframe(df_g[['tipo_gasto', 'descripcion', 'monto', 'Usuario']], use_container_width=True)
                st.warning(f"**Total Gastado Hoy: S/. {df_g['monto'].sum():.2f}**")
            else: st.info("No hay gastos hoy.")
        except: pass

# ==========================================
# 📦 MÓDULO 5: ALMACÉN Y COMPRAS
# ==========================================
elif menu == "📦 ALMACÉN Y COMPRAS" and "inventario_ver" in st.session_state.user_perms:
    st.markdown('<div class="main-header">Inventario Maestro y Compras</div>', unsafe_allow_html=True)
    t1, t2, t3, t4, t5 = st.tabs(["📋 Inventario General", "➕ Crear Producto", "⚙️ Catálogos", "📓 KARDEX", "📈 Productos Vendidos por Día"])
    
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
                        except: st.error("El código ya existe.")

    with t3:
        st.write("Catálogos de Clasificación")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            with st.form("fc"): v = st.text_input("Categoría"); st.form_submit_button("Guardar")
        with c2:
            with st.form("fm"): v = st.text_input("Marca"); st.form_submit_button("Guardar")
        with c3:
            with st.form("fcal"): v = st.text_input("Calidad"); st.form_submit_button("Guardar")
        with c4:
            with st.form("fcom"): v = st.text_input("Compatibilidad"); st.form_submit_button("Guardar")

    with t4:
        k_data = supabase.table("movimientos_inventario").select("*, usuarios(nombre_completo)").order("timestamp", desc=True).limit(100).execute()
        if k_data.data:
            df_k = pd.DataFrame(k_data.data)
            df_k['Usuario'] = df_k['usuarios'].apply(lambda x: x.get('nombre_completo', 'Sys'))
            df_k['Fecha'] = pd.to_datetime(df_k['timestamp']).dt.tz_convert('America/Lima').dt.strftime('%d/%m %H:%M')
            st.dataframe(df_k[['Fecha', 'producto_id', 'tipo_movimiento', 'cantidad', 'Usuario']], use_container_width=True)

    with t5:
        st.write("Consulta cuántas unidades de cada producto se vendieron en un día específico.")
        f_alm_dia = st.date_input("Selecciona la Fecha:", value=get_now().date(), key="f_alm_dia")
        try:
            cab_a = supabase.table("ventas_cabecera").select("*").execute()
            if cab_a.data:
                df_ca = pd.DataFrame(cab_a.data)
                df_ca['fecha'] = pd.to_datetime(df_ca['created_at']).dt.tz_convert('America/Lima').dt.date
                df_ca = df_ca[df_ca['fecha'] == f_alm_dia]
                
                if not df_ca.empty:
                    valid_ids = df_ca['id'].astype(str).tolist() if 'id' in df_ca.columns else df_ca['ticket_numero'].astype(str).tolist()
                    
                    det_res = supabase.table("ventas_detalle").select("*").order("id", desc=True).limit(3000).execute()
                    if det_res.data:
                        df_da = pd.DataFrame(det_res.data)
                        df_da['venta_id_str'] = df_da['venta_id'].astype(str)
                        df_da_filt = df_da[df_da['venta_id_str'].isin(valid_ids)]
                        
                        if not df_da_filt.empty:
                            p_ids = df_da_filt['producto_id'].unique().tolist()
                            p_info = supabase.table("productos").select("codigo_barras, nombre").in_("codigo_barras", p_ids).execute()
                            p_map = {str(x['codigo_barras']): x['nombre'] for x in p_info.data} if p_info.data else {}
                            
                            df_da_filt['Producto'] = df_da_filt['producto_id'].apply(lambda x: p_map.get(str(x), 'N/A'))
                            
                            res_alm = df_da_filt.groupby(['producto_id', 'Producto']).agg(Unidades_Vendidas=('cantidad', 'sum'), Dinero_Generado=('subtotal', 'sum')).reset_index().sort_values(by='Unidades_Vendidas', ascending=False)
                            st.dataframe(res_alm, use_container_width=True)
                        else: st.info("No hay detalles en esta fecha.")
                else: st.info("No hubo ventas en la fecha seleccionada.")
        except: st.error("Aún calculando inventario...")

# ==========================================
# ⚠️ MÓDULO 6: MERMAS 
# ==========================================
elif menu == "⚠️ MERMAS" and "mermas" in st.session_state.user_perms:
    st.markdown('<div class="main-header">Dar de Baja Productos Dañados</div>', unsafe_allow_html=True)
    col_m1, col_m2 = st.columns(2)
    m_cod_input = col_m1.text_input("Dispara Láser (Código)")
    prods_df = load_data_cached("productos")
    m_nom_input = col_m2.selectbox("O Buscar por Nombre (Autocompletado)", ["..."] + (prods_df['nombre'].tolist() if not prods_df.empty else []))
    
    m_cod = None
    if m_cod_input: m_cod = m_cod_input
    elif m_nom_input != "...": m_cod = prods_df[prods_df['nombre'] == m_nom_input]['codigo_barras'].iloc[0]

    if m_cod:
        try:
            p_inf = supabase.table("productos").select("*").eq("codigo_barras", m_cod).execute()
            if p_inf.data:
                p_merma = p_inf.data[0]
                st.write(f"**Producto:** {p_merma['nombre']} | **Stock Actual:** {p_merma['stock_actual']}")
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
# 👥 MÓDULO 7: GESTIÓN DE VENDEDORES (RRHH)
# ==========================================
elif menu == "👥 RRHH (Vendedores)" and "gestion_usuarios" in st.session_state.user_perms:
    st.markdown('<div class="main-header">Panel de Control Gerencial (RRHH)</div>', unsafe_allow_html=True)
    
    def format_permisos(lista):
        if not isinstance(lista, list) or len(lista) == 0: return "Ninguno"
        if len(lista) >= 6: return "🌟 Acceso Total (Full)"
        if len(lista) > 2: return f"Varios ({len(lista)})"
        return ", ".join(lista)
        
    t_u1, t_u2, t_u3, t_u4, t_u5, t_u6 = st.tabs(["📋 Activos", "➕ Crear Nuevo", "🔑 Password", "⚙️ Permisos", "🗑️ Baja / Alta", "📊 Rendimiento Diario"])
    
    usrs_db = supabase.table("usuarios").select("id, nombre_completo, usuario, clave, turno, permisos, estado").execute()
    df_u, df_activos, df_inactivos = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    if usrs_db.data:
        df_u = pd.DataFrame(usrs_db.data)
        df_u['permisos_visual'] = df_u['permisos'].apply(format_permisos)
        df_activos = df_u[df_u['estado'] == 'Activo']
        df_inactivos = df_u[df_u['estado'] == 'Inactivo']
    
    with t_u1:
        if not df_activos.empty: st.dataframe(df_activos[['nombre_completo', 'usuario', 'turno', 'permisos_visual']], use_container_width=True)
            
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
        st.write("#### 🛡️ Modificar Permisos de Acceso")
        if not df_activos.empty:
            user_to_edit = st.selectbox("Seleccionar vendedor a editar:", df_activos['usuario'].tolist(), key="sel_edit_perm")
            raw_perms = supabase.table("usuarios").select("permisos").eq("usuario", user_to_edit).execute().data[0]['permisos']
            curr_perms = raw_perms if isinstance(raw_perms, list) else []
            
            with st.form("form_edit_perms"):
                lista_permisos = ["mermas", "inventario_ver", "inventario_agregar", "inventario_modificar", "inventario_eliminar", "reportes", "cierre_caja", "gestion_usuarios"]
                valid_curr = [p for p in curr_perms if p in lista_permisos]
                new_perms = st.multiselect("Permisos Asignados:", lista_permisos, default=valid_curr)
                if st.form_submit_button("💾 Guardar Cambios", type="primary"):
                    if user_to_edit == "admin" and "gestion_usuarios" not in new_perms:
                        st.error("⚠️ No puedes quitarle el permiso de 'Gestión de Usuarios' al Administrador.")
                    else:
                        supabase.table("usuarios").update({"permisos": new_perms}).eq("usuario", user_to_edit).execute()
                        st.success(f"✅ Permisos actualizados."); time.sleep(1); st.rerun()

    with t_u5:
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

    with t_u6:
        if not df_activos.empty:
            st.write("#### 🎯 Informe Integral de Empleado (Asistencia + Ventas)")
            sel_u_nombre = st.selectbox("Selecciona un vendedor:", df_activos['nombre_completo'].tolist(), key="rrhh_vendedor")
            sel_u_id = df_activos[df_activos['nombre_completo'] == sel_u_nombre]['id'].iloc[0]
            f_rrhh_dia = st.date_input("📆 Fecha Específica a Consultar:", value=get_now().date(), key="f_rrhh_dia")
            
            try:
                # 1. Módulo Asistencia
                ast_db = supabase.table("asistencia").select("*").eq("usuario_id", sel_u_id).execute()
                df_a = pd.DataFrame(ast_db.data) if ast_db.data else pd.DataFrame()
                
                h_in, h_out, hrs_hoy, dias_faltados = "--:--", "--:--", 0.0, 0
                
                if not df_a.empty:
                    df_a['ts'] = pd.to_datetime(df_a['timestamp']).dt.tz_convert('America/Lima')
                    df_a['date'] = df_a['ts'].dt.date
                    df_hoy_a = df_a[df_a['date'] == f_rrhh_dia]
                    
                    if not df_hoy_a.empty:
                        i_ts = df_hoy_a[df_hoy_a['tipo_marcacion'] == 'Ingreso']['ts']
                        s_ts = df_hoy_a[df_hoy_a['tipo_marcacion'] == 'Salida']['ts']
                        if not i_ts.empty: h_in = i_ts.min().strftime('%I:%M %p')
                        if not s_ts.empty: h_out = s_ts.max().strftime('%I:%M %p')
                        if not i_ts.empty and not s_ts.empty: hrs_hoy = (s_ts.max() - i_ts.min()).total_seconds() / 3600
                
                # 2. Módulo Ventas del Empleado
                cab_v = supabase.table("ventas_cabecera").select("*").eq("usuario_id", sel_u_id).execute()
                v_hoy_ventas, v_hoy_costo, v_hoy_utilidad = 0.0, 0.0, 0.0
                
                if cab_v.data:
                    df_cv = pd.DataFrame(cab_v.data)
                    df_cv['fecha'] = pd.to_datetime(df_cv['created_at']).dt.tz_convert('America/Lima').dt.date
                    df_cv_dia = df_cv[df_cv['fecha'] == f_rrhh_dia]
                    
                    if not df_cv_dia.empty:
                        v_hoy_ventas = df_cv_dia['total_venta'].sum()
                        v_hoy_costo, _ = calcular_costo_y_cantidad_ventas(df_cv_dia.to_dict('records'))
                        v_hoy_utilidad = v_hoy_ventas - v_hoy_costo

                st.write("**Resumen de Turno**")
                c1, c2, c3 = st.columns(3)
                c1.markdown(f"<div class='metric-box'><div class='metric-title'>Hora de Ingreso</div><div class='metric-value-small'>{h_in}</div></div>", unsafe_allow_html=True)
                c2.markdown(f"<div class='metric-box'><div class='metric-title'>Hora de Salida</div><div class='metric-value-small'>{h_out}</div></div>", unsafe_allow_html=True)
                c3.markdown(f"<div class='metric-box'><div class='metric-title'>Total Horas</div><div class='metric-value-small metric-green'>{hrs_hoy:.1f} Hrs</div></div>", unsafe_allow_html=True)
                
                st.write("**Desempeño en Ventas**")
                c4, c5, c6 = st.columns(3)
                c4.markdown(f"<div class='metric-box'><div class='metric-title'>Ventas Realizadas</div><div class='metric-value-small metric-blue'>S/. {v_hoy_ventas:.2f}</div></div>", unsafe_allow_html=True)
                c5.markdown(f"<div class='metric-box'><div class='metric-title'>Costo de Mercadería</div><div class='metric-value-small metric-orange'>S/. {v_hoy_costo:.2f}</div></div>", unsafe_allow_html=True)
                c6.markdown(f"<div class='metric-box' style='border:2px solid #8b5cf6;'><div class='metric-title'>Utilidad Generada</div><div class='metric-value-small metric-purple'>S/. {v_hoy_utilidad:.2f}</div></div>", unsafe_allow_html=True)

            except: pass

# ==========================================
# 📊 MÓDULO 8: REPORTES Y CIERRE SÚPER BLINDADO
# ==========================================
elif menu == "📊 REPORTES Y CIERRE" and ("cierre_caja" in st.session_state.user_perms or "reportes" in st.session_state.user_perms):
    st.markdown('<div class="main-header">Auditoría Financiera Integral</div>', unsafe_allow_html=True)
    
    if st.session_state.ticket_cierre:
        tk = st.session_state.ticket_cierre
        st.success("✅ Caja cerrada con éxito.")
        st.markdown(f"""
        <div class="ticket-termico">
            <center><b>ACCESORIOS JORDAN</b><br><b>REPORTE Z (FIN TURNO)</b></center>
            --------------------------------<br>
            FECHA CIERRE: {tk['fecha']}<br>
            CAJERO: {st.session_state.user_name}<br>
            --------------------------------<br>
            <b>💰 VENTAS TOTALES: S/. {tk['tot_ventas']:.2f}</b><br>
            - Efectivo: S/. {tk['ventas_efectivo']:.2f}<br>
            - Digital: S/. {tk['ventas_digital']:.2f}<br>
            Cant. Vendida: {tk['cant_vendida']} ud.<br>
            --------------------------------<br>
            <b>📉 COSTOS Y SALIDAS:</b><br>
            Costo Mercadería: S/. {tk['capital_inv']:.2f}<br>
            Gastos en Efectivo: S/. {tk['tot_gastos']:.2f}<br>
            Mermas (Daños): S/. {tk['tot_merma']:.2f}<br>
            Devoluciones: S/. {tk['tot_dev']:.2f}<br>
            --------------------------------<br>
            <b>📊 RENDIMIENTO REAL:</b><br>
            Ganancia Bruta: S/. {tk['ganancia_bruta']:.2f}<br>
            <b>GANANCIA NETA: S/. {tk['utilidad']:.2f}</b><br>
            --------------------------------<br>
            <b>🏦 EFECTIVO FINAL A RENDIR: S/. {tk['caja_efectivo']:.2f}</b><br>
            --------------------------------<br>
            {tk['alertas_stock']}
        </div>
        """, unsafe_allow_html=True)
        if st.button("🧹 Iniciar Nuevo Turno", type="primary"):
            st.session_state.ticket_cierre = None
            st.rerun()
    else:
        t_rep1, t_rep2, t_rep3, t_rep4 = st.tabs(["📊 Turno Actual (Caja Viva)", "📆 Historial por Día", "🧾 Tickets", "👤 Ventas por Vendedor"])
        
        # --- PESTAÑA 1: TURNO ACTUAL (Costos 100% Reparados) ---
        with t_rep1:
            try:
                last_cierre = get_last_cierre_dt()
                st.caption(f"Contabilizando dinero desde: {last_cierre.strftime('%d/%m/%Y %H:%M')}")
                
                cab = supabase.table("ventas_cabecera").select("*").gte("created_at", last_cierre.isoformat()).execute()
                gst = supabase.table("gastos").select("monto").gte("fecha", last_cierre.isoformat()).execute()
                devs = supabase.table("devoluciones").select("dinero_devuelto").gte("created_at", last_cierre.isoformat()).execute()
                mermas = supabase.table("mermas").select("perdida_monetaria").gte("created_at", last_cierre.isoformat()).execute()
                
                tot_v, v_efe, v_dig, tot_costo, tot_gst, tot_dev, tot_merma = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
                c_ven = 0
                
                if cab.data:
                    df_c = pd.DataFrame(cab.data)
                    v_efe = df_c[df_c['metodo_pago'] == 'Efectivo']['total_venta'].sum()
                    v_dig = df_c[df_c['metodo_pago'] != 'Efectivo']['total_venta'].sum()
                    tot_v = v_efe + v_dig
                    
                    tot_costo, c_ven = calcular_costo_y_cantidad_ventas(cab.data)
                
                if gst.data: tot_gst = sum(g['monto'] for g in gst.data)
                if devs.data: tot_dev = sum(d['dinero_devuelto'] for d in devs.data)
                if mermas.data: tot_merma = sum(m['perdida_monetaria'] for m in mermas.data)
                
                ganancia_bruta = tot_v - tot_costo
                ganancia_neta = ganancia_bruta - tot_gst - tot_dev - tot_merma
                caja_efectivo = v_efe - tot_gst - tot_dev 
                
                c1, c2, c3 = st.columns(3)
                c1.markdown(f"<div class='metric-box'><div class='metric-title'>Ventas Totales Brutas</div><div class='metric-value metric-blue'>S/.{tot_v:.2f}</div></div>", unsafe_allow_html=True)
                c2.markdown(f"<div class='metric-box'><div class='metric-title'>Pagos Efectivo (Caja)</div><div class='metric-value'>S/.{v_efe:.2f}</div></div>", unsafe_allow_html=True)
                c3.markdown(f"<div class='metric-box'><div class='metric-title'>Pagos Digitales</div><div class='metric-value metric-purple'>S/.{v_dig:.2f}</div></div>", unsafe_allow_html=True)
                
                c4, c5, c6 = st.columns(3)
                c4.markdown(f"<div class='metric-box'><div class='metric-title'>Costo Mercadería (Inversión)</div><div class='metric-value metric-orange'>S/.{tot_costo:.2f}</div></div>", unsafe_allow_html=True)
                c5.markdown(f"<div class='metric-box'><div class='metric-title'>Gastos de Caja (-)</div><div class='metric-value metric-red'>S/.{tot_gst:.2f}</div></div>", unsafe_allow_html=True)
                c6.markdown(f"<div class='metric-box'><div class='metric-title'>Devoluciones/Mermas (-)</div><div class='metric-value metric-red'>S/.{tot_dev + tot_merma:.2f}</div></div>", unsafe_allow_html=True)
                
                c7, c8 = st.columns(2)
                c7.markdown(f"<div class='metric-box' style='border:2px solid #8b5cf6;'><div class='metric-title'>GANANCIA NETA (UTILIDAD PURA)</div><div class='metric-value metric-purple'>S/.{ganancia_neta:.2f}</div></div>", unsafe_allow_html=True)
                c8.markdown(f"<div class='metric-box' style='border:2px solid #10b981; background: #ecfdf5;'><div class='metric-title'>EFECTIVO FÍSICO A RENDIR EN CAJA</div><div class='metric-value metric-green'>S/.{caja_efectivo:.2f}</div></div>", unsafe_allow_html=True)
                
                st.divider()
                if "cierre_caja" in st.session_state.user_perms:
                    with st.form("f_cierre"):
                        st.write("🛑 ¿Terminó el turno? Genera el reporte final.")
                        if st.form_submit_button("🔒 APROBAR CIERRE DE CAJA E IMPRIMIR Z", type="primary"):
                            supabase.table("cierres_caja").insert({"total_ventas": tot_v, "utilidad": ganancia_neta}).execute()
                            
                            bajos = supabase.table("productos").select("nombre, stock_actual").lte("stock_actual", 20).execute()
                            alert_html = ""
                            if bajos.data:
                                alert_html = "<b>⚠️ ALERTAS DE STOCK (<=20):</b><br>"
                                for b in bajos.data: alert_html += f"- {b['nombre']}: {b['stock_actual']} ud<br>"
                                alert_html += "--------------------------------<br>"
                                
                            st.session_state.ticket_cierre = {
                                'fecha': get_now().strftime('%d/%m/%Y %H:%M'),
                                'cant_vendida': c_ven, 'tot_ventas': tot_v, 'ventas_efectivo': v_efe, 'ventas_digital': v_dig,
                                'capital_inv': tot_costo, 'tot_dev': tot_dev, 'tot_merma': tot_merma, 'tot_gastos': tot_gst,
                                'ganancia_bruta': ganancia_bruta, 'caja_efectivo': caja_efectivo, 'utilidad': ganancia_neta, 'alertas_stock': alert_html
                            }
                            st.rerun()
            except Exception as e: st.error(f"Esperando inicio de operaciones...")

        with t_rep2:
            st.write("Consulta la rentabilidad exacta de cualquier día del pasado.")
            f_dia = st.date_input("Selecciona la fecha a analizar:", value=get_now().date())
            
            try:
                cab_all = supabase.table("ventas_cabecera").select("*").execute()
                gst_all = supabase.table("gastos").select("*").execute()
                dev_all = supabase.table("devoluciones").select("*").execute()
                
                r_v_tot, r_v_efe, r_v_dig, r_costo, r_gst, r_dev = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
                
                if cab_all.data:
                    df_c_all = pd.DataFrame(cab_all.data)
                    df_c_all['fecha'] = pd.to_datetime(df_c_all['created_at']).dt.tz_convert('America/Lima').dt.date
                    df_c_dia = df_c_all[df_c_all['fecha'] == f_dia]
                    
                    if not df_c_dia.empty:
                        r_v_efe = df_c_dia[df_c_dia['metodo_pago'] == 'Efectivo']['total_venta'].sum()
                        r_v_dig = df_c_dia[df_c_dia['metodo_pago'] != 'Efectivo']['total_venta'].sum()
                        r_v_tot = r_v_efe + r_v_dig
                        
                        r_costo, _ = calcular_costo_y_cantidad_ventas(df_c_dia.to_dict('records'))

                if gst_all.data:
                    df_g_all = pd.DataFrame(gst_all.data)
                    df_g_all['fecha_local'] = pd.to_datetime(df_g_all['fecha']).dt.tz_convert('America/Lima').dt.date
                    r_gst = df_g_all[df_g_all['fecha_local'] == f_dia]['monto'].sum()
                
                if dev_all.data:
                    df_dev_all = pd.DataFrame(dev_all.data)
                    df_dev_all['fecha_local'] = pd.to_datetime(df_dev_all['created_at']).dt.tz_convert('America/Lima').dt.date
                    r_dev = df_dev_all[df_dev_all['fecha_local'] == f_dia]['dinero_devuelto'].sum()

                r_g_neta = r_v_tot - r_costo - r_gst - r_dev
                
                if r_v_tot > 0 or r_gst > 0:
                    c1, c2, c3, c4 = st.columns(4)
                    c1.markdown(f"<div class='metric-box'><div class='metric-title'>Ventas del Día</div><div class='metric-value-small metric-blue'>S/.{r_v_tot:.2f}</div></div>", unsafe_allow_html=True)
                    c2.markdown(f"<div class='metric-box'><div class='metric-title'>Costo (Compras)</div><div class='metric-value-small metric-orange'>S/.{r_costo:.2f}</div></div>", unsafe_allow_html=True)
                    c3.markdown(f"<div class='metric-box'><div class='metric-title'>Gastos y Devoluciones</div><div class='metric-value-small metric-red'>S/.{r_gst + r_dev:.2f}</div></div>", unsafe_allow_html=True)
                    c4.markdown(f"<div class='metric-box' style='border:2px solid #8b5cf6;'><div class='metric-title'>Ganancia Neta</div><div class='metric-value-small metric-purple'>S/.{r_g_neta:.2f}</div></div>", unsafe_allow_html=True)
                else:
                    st.info("No hubo movimientos financieros en la fecha seleccionada.")
            except: pass

        with t_rep3:
            st.write("Historial General de Tickets")
            try:
                tks = supabase.table("ticket_historial").select("ticket_numero, fecha, html_payload").order("fecha", desc=True).limit(50).execute()
                if tks.data:
                    df_tks = pd.DataFrame(tks.data)
                    df_tks['fecha_format'] = pd.to_datetime(df_tks['fecha']).dt.tz_convert('America/Lima').dt.strftime('%d/%m/%Y %H:%M')
                    opciones = [f"{row['ticket_numero']} - {row['fecha_format']}" for _, row in df_tks.iterrows()]
                    sel_tk = st.selectbox("Selecciona un ticket para previsualizarlo", opciones)
                    if sel_tk:
                        tk_num = sel_tk.split(" - ")[0]
                        html_raw = df_tks[df_tks['ticket_numero'] == tk_num]['html_payload'].iloc[0]
                        st.markdown(html_raw.replace("<script>window.onload=function(){window.print();}</script>", ""), unsafe_allow_html=True)
            except: pass

        with t_rep4:
            st.write("Consulta cuánto vendió cada empleado en un día específico.")
            f_ven_dia = st.date_input("📆 Selecciona el Día a Analizar:", value=get_now().date(), key="f_ven_dia2")
            
            try:
                cab_v = supabase.table("ventas_cabecera").select("*").execute()
                if cab_v.data:
                    cab_df = pd.DataFrame(cab_v.data)
                    cab_df['fecha'] = pd.to_datetime(cab_df['created_at']).dt.tz_convert('America/Lima').dt.date
                    cab_df = cab_df[cab_df['fecha'] == f_ven_dia]
                    
                    if not cab_df.empty:
                        usuarios_db = load_data_cached("usuarios")
                        user_dict = {u['id']: u['nombre_completo'] for _, u in usuarios_db.iterrows()} if not usuarios_db.empty else {}
                        
                        cab_df['Vendedor'] = cab_df['usuario_id'].apply(lambda x: user_dict.get(x, 'Desconocido'))
                        vendedores_activos = cab_df['Vendedor'].unique()
                        
                        sel_v = st.selectbox("Empleado:", vendedores_activos)
                        df_v_ventas = cab_df[cab_df['Vendedor'] == sel_v]
                        
                        v_ventas = df_v_ventas['total_venta'].sum()
                        v_costo, _ = calcular_costo_y_cantidad_ventas(df_v_ventas.to_dict('records'))
                        v_utilidad = v_ventas - v_costo
                        
                        c1, c2, c3 = st.columns(3)
                        c1.markdown(f"<div class='metric-box'><div class='metric-title'>Ventas de {sel_v}</div><div class='metric-value'>S/. {v_ventas:.2f}</div></div>", unsafe_allow_html=True)
                        c2.markdown(f"<div class='metric-box'><div class='metric-title'>Costo Mercadería</div><div class='metric-value metric-orange'>- S/. {v_costo:.2f}</div></div>", unsafe_allow_html=True)
                        c3.markdown(f"<div class='metric-box'><div class='metric-title'>Ganancia (Margen)</div><div class='metric-value metric-green'>S/. {v_utilidad:.2f}</div></div>", unsafe_allow_html=True)
                    else:
                        st.info("El vendedor seleccionado no registra ventas en esta fecha.")
            except: pass
