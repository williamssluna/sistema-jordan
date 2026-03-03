import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client
import pandas as pd
from datetime import datetime, timedelta
import time
import os
import bcrypt
import plotly.express as px
import plotly.graph_objects as go
import pytz
import uuid
import logging

# Configuración del logger para evitar fallos silenciosos
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ==========================================
# 1. GESTIÓN HORARIA NATIVA
# ==========================================
def get_now():
    return datetime.now(pytz.timezone('America/Lima'))

# ==========================================
# 1.5 CONEXIÓN SEGURA A LA BASE DE DATOS
# ==========================================
URL_SUPABASE = st.secrets["SUPABASE_URL"]
KEY_SUPABASE = st.secrets["SUPABASE_KEY"]
supabase = create_client(URL_SUPABASE, KEY_SUPABASE)

st.set_page_config(page_title="JORDAN POS ERP", layout="wide", page_icon="📱", initial_sidebar_state="expanded")

def get_qr_path(metodo):
    base = f"qr_{metodo.lower()}"
    try:
        for f in os.listdir('.'):
            if f.lower().startswith(base) and f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                return f
    except Exception as e: 
        logging.warning(f"Error al buscar QR local: {e}")
    return None

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
# 3. DISEÑO VISUAL UX/UI PREMIUM
# ==========================================
st.markdown("""
    <style>
    :root { --primary-color: #2563eb; --success-color: #10b981; --danger-color: #ef4444; --warning-color: #f59e0b; --bg-color: #f8fafc;}
    .stApp { background-color: var(--bg-color); }
    .main-header { font-size: 26px; font-weight: 800; color: #1e293b; padding: 10px 0px 20px 0px; border-bottom: 2px solid #e2e8f0; margin-bottom: 25px;}
    .css-card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; margin-bottom: 15px; }
    
    .metric-box { background: white; padding: 15px 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; transition: all 0.2s ease;}
    .metric-box:hover { box-shadow: 0 4px 6px rgba(0,0,0,0.1); transform: translateY(-2px); }
    .metric-title { font-size: 13px; color: #64748b; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;}
    .metric-value { font-size: 26px; font-weight: 800; color: #0f172a;}
    .metric-value-small { font-size: 20px; font-weight: 800; color: #0f172a;}
    
    .metric-green { color: #10b981; }
    .metric-red { color: #ef4444; }
    .metric-orange { color: #f59e0b; }
    .metric-blue { color: #2563eb; }
    .metric-purple { color: #8b5cf6; }
    
    button[data-baseweb="tab"] {
        background-color: #f1f5f9 !important; border-radius: 8px 8px 0px 0px !important;
        border: 1px solid #e2e8f0 !important; border-bottom: none !important;
        padding: 10px 20px !important; margin-right: 5px !important;
        font-weight: 700 !important; color: #475569 !important; transition: all 0.3s ease !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        background-color: #2563eb !important; color: white !important; border-color: #2563eb !important;
    }
    
    div[role="radiogroup"] > label { background-color: white; padding: 12px 15px; border-radius: 8px; margin-bottom: 10px; border: 1px solid #e2e8f0; transition: all 0.2s ease; cursor: pointer;}
    div[role="radiogroup"] > label[data-checked="true"] { background-color: #2563eb !important; border-color: #2563eb !important; }
    div[role="radiogroup"] > label[data-checked="true"] p { color: white !important; font-weight: 800 !important; }
    
    .ticket-termico { background: white; color: black; font-family: 'Courier New', monospace; padding: 15px; border: 1px dashed #cbd5e1; width: 100%; max-width: 320px; margin: 0 auto; line-height: 1.2; font-size: 13px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);}
    .linea-corte { text-align: center; margin: 25px 0; border-bottom: 2px dashed #94a3b8; color: #64748b; font-size: 12px; font-weight: bold;}
    .linea-corte span { background: var(--bg-color); padding: 0 10px; }
    .btn-checkout>button { background-color: #2563eb; color: white; height: 3.5em; font-size: 16px; border: none; border-radius: 8px;}
    .btn-checkout>button:hover { background-color: #1d4ed8; color: white;}
    </style>
    """, unsafe_allow_html=True)

components.html("""<script>const inputs = window.parent.document.querySelectorAll('input[type="text"]'); if(inputs.length > 0) { inputs[0].focus(); }</script>""", height=0)

# ==========================================
# 4. FUNCIONES MAESTRAS E INFRAESTRUCTURA
# ==========================================
keys_to_init = {
    'logged_in': False, 'user_id': None, 'user_name': "", 'user_perms': [], 'is_admin': False,
    'carrito': [], 'last_ticket_html': None, 'print_trigger': False, 'ticket_cierre': None
}
for key, value in keys_to_init.items():
    if key not in st.session_state: st.session_state[key] = value

@st.cache_data(ttl=300)
def load_data_cached(table):
    try: return pd.DataFrame(supabase.table(table).select("*").execute().data)
    except Exception as e: return pd.DataFrame()

def load_data(table):
    try: return pd.DataFrame(supabase.table(table).select("*").execute().data)
    except Exception as e: return pd.DataFrame()

def get_lista_usuarios():
    try: return supabase.table("usuarios").select("id, nombre_completo, usuario").eq("estado", "Activo").execute().data or []
    except Exception as e: return []

def registrar_kardex(producto_id, usuario_id, tipo_movimiento, cantidad, motivo):
    try: supabase.table("movimientos_inventario").insert({"producto_id": str(producto_id), "usuario_id": usuario_id, "tipo_movimiento": tipo_movimiento, "cantidad": cantidad, "motivo": motivo}).execute()
    except Exception as e: logging.error(f"Fallo en inserción Kardex: {e}")

def get_last_cierre_dt():
    try:
        c = supabase.table("cierres_caja").select("fecha_cierre").order("fecha_cierre", desc=True).limit(1).execute()
        if c.data and 'fecha_cierre' in c.data[0]:
            dt = pd.to_datetime(c.data[0]['fecha_cierre'], utc=True)
            return dt.tz_convert('America/Lima')
    except Exception as e: logging.error(f"Error leyendo último cierre: {e}")
    return pd.to_datetime("2000-01-01T00:00:00Z", utc=True).tz_convert('America/Lima')

def is_valid_uuid(val):
    try:
        uuid.UUID(str(val))
        return True
    except ValueError:
        return False

def clean_id(val):
    try:
        if pd.isna(val): return ""
        v_str = str(val).strip()
        if v_str.endswith(".0"): return v_str[:-2]
        return v_str
    except: return str(val).strip()

# 🔥 MOTOR DE COSTOS BASADO EN LÓGICA MERGE (AUDITADO V1.0)
def obtener_costo_y_detalles_optimizado(df_cab, supabase_client):
    if df_cab is None or df_cab.empty: 
        return pd.DataFrame(), 0.0, 0
    try:
        raw_ids = []
        if 'id' in df_cab.columns: raw_ids.extend(df_cab['id'].astype(str).str.strip().tolist())
        if 'ticket_numero' in df_cab.columns: raw_ids.extend(df_cab['ticket_numero'].astype(str).str.strip().tolist())
        raw_ids = list(set(raw_ids))
        
        uuid_list = [x for x in raw_ids if is_valid_uuid(x)]
        text_list = [x for x in raw_ids if not is_valid_uuid(x) and x]
        
        detalles_data = []
        
        if uuid_list:
            res_uuid = supabase_client.table("ventas_detalle").select("venta_id, producto_id, cantidad, subtotal").in_("venta_id", uuid_list).execute()
            if hasattr(res_uuid, 'data') and res_uuid.data:
                detalles_data.extend(res_uuid.data)
                
        if text_list:
            try:
                res_text = supabase_client.table("ventas_detalle").select("venta_id, producto_id, cantidad, subtotal").in_("venta_id", text_list).execute()
                if hasattr(res_text, 'data') and res_text.data:
                    detalles_data.extend(res_text.data)
            except Exception as db_err:
                logging.warning(f"Rechazo de BD por incompatibilidad de tipos en IDs de texto: {db_err}")
                
        if not detalles_data: 
            cant_total = int(pd.to_numeric(df_cab.get('cantidad', 0), errors='coerce').sum()) if 'cantidad' in df_cab.columns else 0
            return pd.DataFrame(), 0.0, cant_total

        df_filt = pd.DataFrame(detalles_data)
        
        df_filt['producto_id_clean'] = df_filt['producto_id'].astype(str).str.strip()
        df_filt['producto_id_clean'] = df_filt['producto_id_clean'].str.replace(r'\.0$', '', regex=True)
        
        productos_a_buscar = df_filt['producto_id_clean'].unique().tolist()

        if not productos_a_buscar:
            cant_total = int(pd.to_numeric(df_filt['cantidad'], errors='coerce').fillna(0).sum())
            return df_filt, 0.0, cant_total

        res_prod = supabase_client.table("productos").select("codigo_barras, nombre, costo_compra").in_("codigo_barras", productos_a_buscar).execute()
            
        if not res_prod.data: 
            cant_total = int(pd.to_numeric(df_filt['cantidad'], errors='coerce').fillna(0).sum())
            return df_filt, 0.0, cant_total

        df_prod = pd.DataFrame(res_prod.data)
        df_prod['codigo_barras_clean'] = df_prod['codigo_barras'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)

        df_merge = df_filt.merge(
            df_prod[['codigo_barras_clean', 'nombre', 'costo_compra']],
            left_on="producto_id_clean",
            right_on="codigo_barras_clean",
            how="left"
        )

        df_merge['cantidad'] = pd.to_numeric(df_merge['cantidad'], errors='coerce').fillna(0)
        df_merge['costo_compra'] = pd.to_numeric(df_merge['costo_compra'], errors='coerce').fillna(0)
        df_merge['subtotal'] = pd.to_numeric(df_merge['subtotal'], errors='coerce').fillna(0)

        df_merge['costo_total_linea'] = df_merge['cantidad'] * df_merge['costo_compra']
        df_merge['nombre_prod'] = df_merge['nombre'].fillna('Producto Desconocido')
        df_merge['costo_unit'] = df_merge['costo_compra']

        costo_total = float(df_merge['costo_total_linea'].sum())
        cant_total = int(df_merge['cantidad'].sum())

        return df_merge, costo_total, cant_total

    except Exception as e:
        logging.error(f"Fallo en motor de costeo. Traza: {str(e)}")
        return pd.DataFrame(), 0.0, 0

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
                        'cant': 1, 'costo': float(p['costo_compra']), 'p_min': float(p['precio_minimo']), 'stock_max': p['stock_actual']
                    })
                st.toast(f"✅ Añadido: {p['nombre']}", icon="🛒")
                return True
            else: st.error("❌ Sin stock disponible.")
        else: st.warning("⚠️ Producto no encontrado.")
    except Exception as e: st.error(f"Error de base de datos: {e}")
    return False

def execute_factory_reset():
    tables = [
        ("ventas_detalle", "id"), ("ticket_historial", "id"), ("movimientos_inventario", "id"),
        ("devoluciones", "id"), ("mermas", "id"), ("gastos", "id"), ("ventas_cabecera", "id"),
        ("cierres_caja", "id"), ("asistencia", "id"), ("productos", "codigo_barras"),
        ("clientes", "dni_ruc")
    ]
    for t, pk in tables:
        try: supabase.table(t).delete().not_is_null(pk).execute()
        except: pass
    try: supabase.table("usuarios").delete().neq("usuario", "admin").execute()
    except: pass

# ==========================================
# 5. SIDEBAR Y ACCESOS
# ==========================================
st.sidebar.markdown("### 🏢 Accesos del Sistema")

with st.sidebar.expander("⌚ Marcar Asistencia", expanded=True):
    with st.form("form_asistencia", clear_on_submit=True):
        usr_ast = st.text_input("Usuario Vendedor")
        pwd_ast = st.text_input("Clave", type="password")
        c_a1, c_a2 = st.columns(2)
        if c_a1.form_submit_button("🟢 Entrada") or c_a2.form_submit_button("🔴 Salida"):
            if usr_ast and pwd_ast:
                try:
                    u_d = supabase.table("usuarios").select("*").eq("usuario", usr_ast).eq("estado", "Activo").execute()
                    if u_d.data and verify_password(pwd_ast, u_d.data[0].get('clave')):
                        tipo = "Ingreso" if "Entrada" in str(st.session_state) else "Salida" 
                        supabase.table("asistencia").insert({"usuario_id": u_d.data[0]['id'], "tipo_marcacion": tipo}).execute()
                        st.success(f"✅ Asistencia registrada exitosamente.")
                    else: st.error("❌ Credenciales inválidas.")
                except Exception as e: st.error(f"Error al conectar: {e}")

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
                    st.session_state.is_admin = (l_usr == "admin")
                    st.rerun()
                else: st.error("❌ Acceso Denegado.")
            except Exception as e: st.error(f"Error de conexión: {e}")
else:
    st.sidebar.success(f"👤 {st.session_state.user_name}")
    if st.sidebar.button("🚪 Cerrar Sesión"):
        st.session_state.logged_in = False
        st.session_state.user_id = None
        st.session_state.user_perms = []
        st.session_state.is_admin = False
        st.rerun()

if st.session_state.logged_in and st.session_state.is_admin:
    st.sidebar.divider()
    with st.sidebar.expander("⚠️ ZONA DE PRUEBAS (RESET)", expanded=False):
        st.error("Esto borrará TODA la información operativa para iniciar en limpio.")
        confirm_text = st.text_input("Escribe 'RESETEAR' para confirmar:", key="input_reset_admin_v1")
        if st.button("🔥 FORMATEAR SISTEMA", type="primary", key="btn_reset_admin_v1"):
            if confirm_text == "RESETEAR":
                with st.spinner("Borrando base de datos con consultas Bulk..."):
                    execute_factory_reset()
                st.success("✅ Sistema reseteado a cero. Actualiza la página.")
                time.sleep(2)
                st.rerun()
            else:
                st.error("Palabra de seguridad incorrecta.")

menu_options = ["🛒 VENTAS (POS)", "🔄 DEVOLUCIONES"]
if st.session_state.logged_in:
    p = st.session_state.user_perms
    if "reportes" in p or "cierre_caja" in p or st.session_state.is_admin: menu_options.insert(0, "📈 DASHBOARD GENERAL")
    menu_options.append("🤝 CLIENTES (CRM)")
    if "inventario_ver" in p or st.session_state.is_admin: menu_options.append("📦 ALMACÉN Y COMPRAS")
    if "reportes" in p or "cierre_caja" in p or st.session_state.is_admin: menu_options.append("💵 GASTOS OPERATIVOS")
    if "mermas" in p or st.session_state.is_admin: menu_options.append("⚠️ MERMAS")
    if "reportes" in p or "cierre_caja" in p or st.session_state.is_admin: menu_options.append("📊 REPORTES Y CIERRE")
    if "gestion_usuarios" in p or st.session_state.is_admin: menu_options.append("👥 RRHH (Vendedores)")

menu = st.sidebar.radio("Navegación", menu_options)

# ==========================================
# 📈 MÓDULO 0: DASHBOARD GENERAL (RESTAURADO A V21.0)
# ==========================================
if menu == "📈 DASHBOARD GENERAL":
    st.markdown('<div class="main-header">Panel de Inteligencia Comercial</div>', unsafe_allow_html=True)
    try:
        v_db = supabase.table("ventas_cabecera").select("*").execute()
        ast_db = supabase.table("asistencia").select("*, usuarios(nombre_completo)").execute()
        
        if v_db.data:
            df_v = pd.DataFrame(v_db.data)
            df_v['created_at_dt'] = pd.to_datetime(df_v['created_at'], utc=True).dt.tz_convert('America/Lima')
            df_v['fecha'] = df_v['created_at_dt'].dt.date
            
            hoy = get_now().date()
            ayer = hoy - timedelta(days=1)
            mes = get_now().month
            semana_inicio = hoy - timedelta(days=hoy.weekday())
            
            df_hoy = df_v[df_v['fecha'] == hoy]
            df_ayer = df_v[df_v['fecha'] == ayer]
            
            v_hoy = df_hoy['total_venta'].sum()
            v_ayer = df_ayer['total_venta'].sum()
            
            personal_hoy = []
            if ast_db.data:
                df_a = pd.DataFrame(ast_db.data)
                df_a['ts'] = pd.to_datetime(df_a['timestamp'], utc=True).dt.tz_convert('America/Lima')
                df_a_hoy = df_a[df_a['ts'].dt.date == hoy].sort_values('ts')
                if not df_a_hoy.empty:
                    last_actions = df_a_hoy.groupby('usuario_id').last()
                    activos = last_actions[last_actions['tipo_marcacion'] == 'Ingreso']
                    for uid, row in activos.iterrows():
                        u_dict = row.get('usuarios', {})
                        nom = u_dict.get('nombre_completo', f'ID:{uid}') if isinstance(u_dict, dict) else f'ID:{uid}'
                        personal_hoy.append(nom)

            es_gerencia = st.session_state.is_admin or "reportes" in st.session_state.user_perms

            st.write("#### ⚡ Resumen Directivo")
            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(f"<div class='metric-box'><div class='metric-title'>Ventas de Hoy</div><div class='metric-value metric-green'>S/. {v_hoy:.2f}</div></div>", unsafe_allow_html=True)
            c2.markdown(f"<div class='metric-box'><div class='metric-title'>Ventas Ayer</div><div class='metric-value metric-blue'>S/. {v_ayer:.2f}</div></div>", unsafe_allow_html=True)
            
            if es_gerencia:
                _, util_hoy_costo, _ = obtener_costo_y_detalles_optimizado(df_hoy, supabase)
                c3.markdown(f"<div class='metric-box'><div class='metric-title'>Utilidad Neta Hoy</div><div class='metric-value metric-purple'>S/. {v_hoy - util_hoy_costo:.2f}</div></div>", unsafe_allow_html=True)
            else:
                c3.markdown(f"<div class='metric-box'><div class='metric-title'>Utilidad Neta Hoy</div><div class='metric-value metric-purple'>🔒 Oculto</div></div>", unsafe_allow_html=True)
                
            html_personal = "Nadie en turno" if not personal_hoy else "<br>".join([f"🟢 {n}" for n in personal_hoy])
            c4.markdown(f"<div class='metric-box' style='padding-bottom:10px;'><div class='metric-title'>Personal en Tienda</div><div style='font-size:14px; font-weight:bold; color:#334155;'>{html_personal}</div></div>", unsafe_allow_html=True)

            if es_gerencia:
                st.divider()
                st.write("#### 🚨 Alertas Operativas")
                p_db = supabase.table("productos").select("nombre, stock_actual, stock_minimo").execute()
                if p_db.data:
                    df_p = pd.DataFrame(p_db.data)
                    df_criticos = df_p[df_p['stock_actual'] <= 20].sort_values(by='stock_actual')
                    if not df_criticos.empty:
                        st.warning(f"⚠️ Atención: Tienes {len(df_criticos)} productos con 20 unidades o menos. Requieren reabastecimiento.")
                        with st.expander("Ver lista de productos a comprar"):
                            st.dataframe(df_criticos[['nombre', 'stock_actual']].rename(columns={'nombre':'Producto', 'stock_actual': 'Stock Restante'}), hide_index=True)
                    else: st.success("Todo el inventario supera las 20 unidades.")

                st.divider()
                st.write("#### 📈 Evolución Comercial (Últimos 7 Días)")
                fechas_7d = [hoy - timedelta(days=i) for i in range(6, -1, -1)]
                chart_data = []
                df_7d = df_v[df_v['fecha'] >= (hoy - timedelta(days=6))]
                
                for d in fechas_7d:
                    df_dia = df_7d[df_7d['fecha'] == d]
                    v_tot = df_dia['total_venta'].sum()
                    if not df_dia.empty:
                        _, costo_dia, _ = obtener_costo_y_detalles_optimizado(df_dia, supabase)
                    else:
                        costo_dia = 0.0
                    util_dia = v_tot - costo_dia
                    
                    chart_data.append({'Día': d.strftime('%d %b'), 'Ventas Brutas': v_tot, 'Utilidad Líquida': util_dia})
                    
                df_chart = pd.DataFrame(chart_data)
                fig_combo = go.Figure()
                fig_combo.add_trace(go.Bar(x=df_chart['Día'], y=df_chart['Ventas Brutas'], name='Ventas Brutas', marker_color='#2563eb', opacity=0.85))
                fig_combo.add_trace(go.Bar(x=df_chart['Día'], y=df_chart['Utilidad Líquida'], name='Utilidad Líquida', marker_color='#10b981', opacity=0.85))
                fig_combo.add_trace(go.Scatter(x=df_chart['Día'], y=df_chart['Ventas Brutas'], name='Tendencia', mode='lines+markers', line=dict(color='#f59e0b', width=3), marker=dict(size=8, color='#f59e0b')))
                
                fig_combo.update_layout(
                    barmode='group', xaxis_type='category', legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    margin=dict(l=0, r=0, t=30, b=0), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig_combo, use_container_width=True)

        else: st.info("No hay ventas registradas aún.")
    except Exception as e: st.error(f"Cargando módulos... {e}")

# ==========================================
# 🛒 MÓDULO 1: VENTAS (POS)
# ==========================================
elif menu == "🛒 VENTAS (POS)":
    
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

    col_v1, col_v2 = st.columns([1.3, 1.7])
    
    with col_v1:
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        st.write("#### 🔍 Búsqueda de Productos")
        with st.form("form_barcode", clear_on_submit=True):
            codigo = st.text_input("Dispara el Láser (Código Numérico):", key="pos_input")
            if st.form_submit_button("Añadir al Carrito", use_container_width=True):
                if codigo: procesar_codigo_venta(codigo); st.rerun()

        st.divider()
        st.write("**Búsqueda Manual (Autocompletado)**")
        prods_df = load_data_cached("productos")
        if not prods_df.empty:
            nombres_prods = prods_df['nombre'].tolist()
            search_nom = st.selectbox("Escribe el nombre (Ej. 'Cargador'):", ["..."] + nombres_prods)
            if search_nom != "...":
                p_sel = prods_df[prods_df['nombre'] == search_nom].iloc[0]
                c_p1, c_p2 = st.columns([3, 1])
                c_p1.write(f"**{p_sel['nombre']}** - S/.{p_sel['precio_lista']} (Stock: {p_sel['stock_actual']})")
                if c_p2.button("➕ Añadir", key="btn_add_nom"):
                    if procesar_codigo_venta(p_sel['codigo_barras']): st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with col_v2:
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        st.write("#### 🛍️ Carrito de Compras")
        if not st.session_state.carrito: 
            st.info("El carrito está vacío.")
        else:
            total_venta = 0.0
            costo_total = 0.0
            indices_basura = []
            
            st.markdown("<div style='font-size:12px; color:gray; font-weight:bold; display:flex; border-bottom:1px solid #e2e8f0; padding-bottom:5px;'><span style='width:45%;'>Producto</span><span style='width:25%;'>Precio (S/.)</span><span style='width:20%;'>Cant.</span><span style='width:10%;'></span></div>", unsafe_allow_html=True)
            
            for i, item in enumerate(st.session_state.carrito):
                c1, c2, c3, c4 = st.columns([4.5, 2.5, 2, 1])
                c1.markdown(f"<div style='padding-top:10px; font-size:14px;'><b>{item['nombre']}</b></div>", unsafe_allow_html=True)
                
                nuevo_p = c2.number_input("Precio", min_value=float(item['p_min']), value=float(item['precio']), step=1.0, key=f"p_{i}", label_visibility="collapsed")
                st.session_state.carrito[i]['precio'] = nuevo_p
                
                nueva_c = c3.number_input("Cant.", min_value=1, max_value=int(item['stock_max']), value=int(item['cant']), step=1, key=f"c_{i}", label_visibility="collapsed")
                st.session_state.carrito[i]['cant'] = nueva_c
                
                st.markdown("""<style>div.stButton > button:first-child {margin-top: 5px;}</style>""", unsafe_allow_html=True)
                if c4.button("🗑️", key=f"del_cart_{i}"):
                    indices_basura.append(i)
                    
                subtotal = nuevo_p * nueva_c
                total_venta += subtotal
                costo_total += (item['costo'] * nueva_c)

            if indices_basura:
                for idx_obsoleto in sorted(indices_basura, reverse=True):
                    st.session_state.carrito.pop(idx_obsoleto)
                st.rerun()

            st.markdown(f"<div style='text-align:right; margin-top:15px;'><h1 style='color:#2563eb; font-size:45px; margin-bottom:0;'>TOTAL: S/. {total_venta:.2f}</h1></div>", unsafe_allow_html=True)
            
            if st.session_state.logged_in and (st.session_state.is_admin or "reportes" in st.session_state.user_perms):
                st.caption(f"Ganancia Bruta estimada: S/. {total_venta - costo_total:.2f}")

            with st.expander("💸 PAGO Y FACTURACIÓN", expanded=True):
                lista_vendedores = get_lista_usuarios()
                vendedor_opciones = {v['usuario']: v['id'] for v in lista_vendedores}
                vendedor_seleccionado = st.selectbox("👤 Tu usuario (Vendedor):", ["Seleccionar..."] + list(vendedor_opciones.keys()))

                try:
                    clientes_db = supabase.table("clientes").select("*").execute()
                    opciones_clientes = ["Público General (Sin registrar)"]
                    cliente_dict = {}
                    if clientes_db.data:
                        for r in clientes_db.data:
                            label = f"{r.get('dni_ruc','')} - {r.get('nombre','')}"
                            opciones_clientes.append(label)
                            cliente_dict[label] = r.get('id')
                except Exception as e: 
                    opciones_clientes = ["Público General (Sin registrar)"]
                    cliente_dict = {}
                
                cliente_sel = st.selectbox("Cliente (Opcional):", opciones_clientes)
                
                crear_cli = st.checkbox("➕ Registrar Nuevo Cliente ahora")
                if crear_cli:
                    st.info("El cliente se guardará para futuras ventas.")
                    n_doc = st.text_input("DNI/RUC")
                    n_nom = st.text_input("Nombre Completo")
                    n_tel = st.text_input("Teléfono / WhatsApp")
                    n_mail = st.text_input("Correo Electrónico (Marketing)")
                    if st.button("Guardar y Seleccionar"):
                        try:
                            supabase.table("clientes").insert({"dni_ruc": n_doc, "nombre": n_nom, "telefono": n_tel, "correo": n_mail}).execute()
                            st.success("Cliente guardado."); time.sleep(2); st.rerun()
                        except Exception as e: st.error(f"Fallo al guardar cliente.")

                cp1, cp2 = st.columns(2)
                pago = cp1.selectbox("Método de Pago", ["Efectivo", "Yape", "Plin", "Tarjeta VISA/MC"])
                
                if pago in ["Yape", "Plin"]:
                    st.info(f"📲 Pide al cliente que escanee el código para pagar con {pago}:")
                    path_qr = get_qr_path(pago)
                    if path_qr: st.image(path_qr, width=220)
                    else: st.warning(f"⚠️ Sube el archivo 'qr_{pago.lower()}.png' a GitHub.")

                ref_pago = ""
                if pago != "Efectivo":
                    ref_pago = cp2.text_input("N° de Aprobación (Obligatorio)")

                st.markdown('<div class="btn-checkout">', unsafe_allow_html=True)
                
                if st.button("FINALIZAR VENTA E IMPRIMIR", use_container_width=True):
                    if vendedor_seleccionado == "Seleccionar...": st.error("🛑 Selecciona tu usuario.")
                    elif pago != "Efectivo" and not ref_pago: st.error("🛑 Ingresa la referencia del pago.")
                    else:
                        try:
                            vendedor_id = vendedor_opciones[vendedor_seleccionado]
                            t_num = f"AJ-{int(time.time())}"
                            
                            datos_insert = {"ticket_numero": t_num, "total_venta": total_venta, "metodo_pago": pago, "tipo_comprobante": "Ticket", "usuario_id": vendedor_id, "referencia_pago": ref_pago}
                            cli_id = cliente_dict.get(cliente_sel, None) if cliente_sel != "Público General (Sin registrar)" else None
                            if cli_id is not None: datos_insert["cliente_id"] = cli_id
                            
                            try: 
                                res_insert = supabase.table("ventas_cabecera").insert(datos_insert).execute()
                            except Exception as e_cab:
                                if "cliente_id" in datos_insert: del datos_insert["cliente_id"]
                                res_insert = supabase.table("ventas_cabecera").insert(datos_insert).execute()

                            v_id = t_num 
                            if hasattr(res_insert, 'data') and res_insert.data: 
                                row_v = res_insert.data[0]
                                v_id = str(row_v.get('id', t_num)).strip()
                            
                            items_html = ""
                            for it in st.session_state.carrito:
                                try: 
                                    supabase.table("ventas_detalle").insert({"venta_id": v_id, "producto_id": str(it['id']), "cantidad": it['cant'], "precio_unitario": it['precio'], "subtotal": it['precio'] * it['cant']}).execute()
                                except Exception as e_det: pass
                                
                                try:
                                    supabase.rpc("reducir_stock", {"p_codigo": str(it['id']), "p_cant": int(it['cant'])}).execute()
                                except Exception as e_rpc:
                                    try:
                                        stk = supabase.table("productos").select("stock_actual").eq("codigo_barras", it['id']).execute()
                                        if stk.data: supabase.table("productos").update({"stock_actual": stk.data[0]['stock_actual'] - it['cant']}).eq("codigo_barras", it['id']).execute()
                                    except: pass
                                
                                registrar_kardex(it['id'], vendedor_id, "SALIDA_VENTA", it['cant'], f"Ticket {t_num}")
                                items_html += f"{it['nombre'][:20]} <br> {it['cant']} x S/. {it['precio']:.2f} = S/. {it['precio']*it['cant']:.2f}<br>"
                            
                            fecha_tk = get_now().strftime('%d/%m/%Y %I:%M %p')
                            nom_cliente = cliente_sel.split(' - ')[1] if (cli_id and ' - ' in cliente_sel) else 'General'
                            
                            c_base = f"--------------------------------<br>TICKET: {t_num}<br>FECHA: {fecha_tk}<br>CAJERO: {vendedor_seleccionado}<br>CLIENTE: {nom_cliente}<br>--------------------------------<br>{items_html}--------------------------------<br><b>TOTAL PAGADO: S/. {total_venta:.2f}</b><br>MÉTODO: {pago}<br>"
                            tk_html = f"<div class='ticket-termico' style='text-align:left;'><center><b>ACCESORIOS JORDAN</b><br>COPIA CLIENTE</center><br>{c_base}<center>¡Gracias por su compra!</center></div><div class='linea-corte'><span>✂️</span></div><div class='ticket-termico' style='text-align:left;'><center><b>ACCESORIOS JORDAN</b><br>CONTROL INTERNO</center><br>{c_base}</div><script>window.onload=function(){{window.print();}}</script>"
                            
                            try: supabase.table("ticket_historial").insert({"ticket_numero": t_num, "usuario_id": vendedor_id, "html_payload": tk_html}).execute()
                            except: pass
                            
                            st.session_state.last_ticket_html = tk_html
                            st.session_state.print_trigger = True
                            st.session_state.carrito = []
                            st.rerun() 
                        except Exception as e: st.error(f"🚨 Error en facturación: {e}")
                st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 🔄 MÓDULO 2: DEVOLUCIONES
# ==========================================
elif menu == "🔄 DEVOLUCIONES":
    st.markdown('<div class="main-header">Gestión de Devoluciones</div>', unsafe_allow_html=True)
    st.markdown('<div class="css-card">', unsafe_allow_html=True)
    
    lista_vendedores = get_lista_usuarios()
    vendedor_opciones = {v['usuario']: v['id'] for v in lista_vendedores}
    tipo_b = st.radio("Método de búsqueda:", ["Por N° de Ticket", "Por Producto Libre (Láser o Nombre)"], horizontal=True)

    if tipo_b == "Por N° de Ticket":
        search_dev = st.text_input("Ingresa N° de Ticket (Ej. AJ-123456)")
        if search_dev:
            try:
                v_cab = supabase.table("ventas_cabecera").select("*").eq("ticket_numero", search_dev.upper()).execute()
                if v_cab.data:
                    v_row = v_cab.data[0]
                    v_id_search = str(v_row.get('id', v_row.get('ticket_numero'))).strip()
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
                                    try: 
                                        supabase.rpc("aumentar_stock", {"p_codigo": d['producto_id'], "p_cant": int(d['cantidad'])}).execute()
                                    except:
                                        p_s = supabase.table("productos").select("stock_actual").eq("codigo_barras", d['producto_id']).execute()
                                        supabase.table("productos").update({"stock_actual": p_s.data[0]['stock_actual'] + d['cantidad']}).eq("codigo_barras", d['producto_id']).execute()
                                        
                                    supabase.table("devoluciones").insert({"usuario_id": usr_id, "producto_id": d['producto_id'], "cantidad": d['cantidad'], "motivo": "Devolución Ticket", "dinero_devuelto": d['subtotal'], "estado_producto": "Vuelve a tienda"}).execute()
                                    registrar_kardex(d['producto_id'], usr_id, "INGRESO_DEVOLUCION", d['cantidad'], f"Ticket {search_dev.upper()}")
                                    st.session_state.iny_dev_cod = ""; st.success("✅ Devuelto."); time.sleep(1); st.rerun()
                                else: st.error("Selecciona tu usuario.")
                else: st.warning("Ticket no encontrado.")
            except Exception as e: st.error(f"Error procesando búsqueda.")
            
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
                                try: 
                                    supabase.rpc("aumentar_stock", {"p_codigo": p['codigo_barras'], "p_cant": int(d_cant)}).execute()
                                except: supabase.table("productos").update({"stock_actual": p['stock_actual'] + d_cant}).eq("codigo_barras", p['codigo_barras']).execute()
                                
                                supabase.table("devoluciones").insert({"usuario_id": usr_id, "producto_id": p['codigo_barras'], "cantidad": d_cant, "motivo": m_dev, "dinero_devuelto": d_cant * d_dinero, "estado_producto": "Vuelve a tienda"}).execute()
                                registrar_kardex(p['codigo_barras'], usr_id, "INGRESO_DEVOLUCION", d_cant, m_dev)
                                st.success("✅ Devuelto exitosamente."); time.sleep(1); st.rerun()
                            else: st.error("Falta motivo o usuario autorizador.")
            except Exception as e: st.error(f"Fallo de conexión.")
    st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 🤝 MÓDULO 3: CLIENTES (CRM)
# ==========================================
elif menu == "🤝 CLIENTES (CRM)":
    st.markdown('<div class="main-header">Base de Datos de Clientes y CRM</div>', unsafe_allow_html=True)
    t1, t2 = st.tabs(["📋 Lista de Clientes", "➕ Nuevo Cliente / Edición"])
    
    with t1:
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        try:
            cls_df = load_data("clientes")
            if not cls_df.empty: 
                cols_disponibles = cls_df.columns.tolist()
                cols_a_mostrar = ['dni_ruc', 'nombre']
                if 'telefono' in cols_disponibles: cols_a_mostrar.append('telefono')
                if 'correo' in cols_disponibles: cols_a_mostrar.append('correo')
                if 'created_at' in cols_disponibles: cols_a_mostrar.append('created_at')

                csv = cls_df.to_csv(index=False).encode('utf-8')
                st.download_button(label="📥 Descargar Base de Datos para Marketing (CSV)", data=csv, file_name='clientes_jordan.csv', mime='text/csv')
                
                st.dataframe(cls_df[cols_a_mostrar], use_container_width=True)
                
                st.divider()
                st.write("#### 🗑️ Eliminar Cliente")
                if 'nombre' in cls_df.columns and 'dni_ruc' in cls_df.columns:
                    cli_a_borrar = st.selectbox("Selecciona cliente a eliminar:", ["..."] + cls_df['nombre'].astype(str).tolist())
                    if st.button("🗑️ Confirmar Eliminación Permanente", type="primary"):
                        if cli_a_borrar != "...":
                            dni_to_del = cls_df[cls_df['nombre'] == cli_a_borrar]['dni_ruc'].iloc[0]
                            try:
                                supabase.table("clientes").delete().eq("dni_ruc", dni_to_del).execute()
                                st.success("Cliente eliminado exitosamente."); time.sleep(1); st.rerun()
                            except Exception as e: st.error(f"Error al borrar cliente.")
            else: st.info("No hay clientes registrados en la Base de Datos.")
        except Exception as e: st.error(f"Error procesando clientes.")
        st.markdown('</div>', unsafe_allow_html=True)
        
    with t2:
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        with st.form("form_cli"):
            doc = st.text_input("DNI o RUC (Único)")
            nom = st.text_input("Nombre / Razón Social")
            tel = st.text_input("Celular (Para envío de ofertas por WhatsApp)")
            mail = st.text_input("Correo Electrónico (Opcional)")
            if st.form_submit_button("Guardar en Base de Datos", type="primary"):
                if doc and nom:
                    try:
                        supabase.table("clientes").insert({"dni_ruc": doc, "nombre": nom, "telefono": tel, "correo": mail}).execute()
                        st.success("✅ Cliente guardado."); time.sleep(1); st.rerun()
                    except Exception as e:
                        if "correo" in str(e):
                            try:
                                supabase.table("clientes").insert({"dni_ruc": doc, "nombre": nom, "telefono": tel}).execute()
                                st.success("✅ Cliente guardado (Sin correo)."); time.sleep(1); st.rerun()
                            except Exception as ex: st.error(f"Error: DNI ya existe.")
                        else: st.error(f"Error guardando: DNI ya existe.")
        st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 💵 MÓDULO 4: GASTOS OPERATIVOS
# ==========================================
elif menu == "💵 GASTOS OPERATIVOS" and ("reportes" in st.session_state.user_perms or "cierre_caja" in st.session_state.user_perms or st.session_state.is_admin):
    st.markdown('<div class="main-header">Control de Gastos (Caja Chica)</div>', unsafe_allow_html=True)
    t1, t2 = st.tabs(["📝 Registrar Gasto", "📋 Historial Diario"])
    with t1:
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        with st.form("form_gasto"):
            tipo = st.selectbox("Categoría", ["Alimentación", "Pasajes/Movilidad", "Pago Servicios", "Compras Menores", "Otro"])
            desc = st.text_input("Descripción breve")
            monto = st.number_input("Monto retirado de caja (S/.)", min_value=0.1, step=1.0)
            if st.form_submit_button("Confirmar Salida de Dinero", type="primary"):
                try:
                    supabase.table("gastos").insert({"usuario_id": st.session_state.user_id, "tipo_gasto": tipo, "descripcion": desc, "monto": monto}).execute()
                    st.success("✅ Gasto registrado."); time.sleep(1); st.rerun()
                except Exception as e: st.error(f"Error registrando gasto.")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with t2:
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        f_gasto_dia = st.date_input("📆 Selecciona el día para revisar los gastos:", value=get_now().date())
        try:
            start_dt = datetime.combine(f_gasto_dia, datetime.min.time()).replace(tzinfo=pytz.timezone('America/Lima'))
            end_dt = start_dt + timedelta(days=1)
            
            # FILTRO SEGURO PARA TABLA GASTOS (Verificando si es created_at o fecha)
            try:
                gst = supabase.table("gastos").select("*, usuarios(nombre_completo)").gte("created_at", start_dt.isoformat()).lt("created_at", end_dt.isoformat()).order("id", desc=True).execute()
            except Exception:
                gst = supabase.table("gastos").select("*, usuarios(nombre_completo)").gte("fecha", start_dt.isoformat()).lt("fecha", end_dt.isoformat()).order("id", desc=True).execute()
                
            if gst.data:
                df_g = pd.DataFrame(gst.data)
                df_g['Usuario'] = df_g['usuarios'].apply(lambda x: x.get('nombre_completo', '') if isinstance(x, dict) else '')
                cols_to_show = ['tipo_gasto', 'descripcion', 'monto', 'Usuario']
                cols = [c for c in cols_to_show if c in df_g.columns]
                st.dataframe(df_g[cols], use_container_width=True)
                st.markdown(f"<div style='text-align:right;'><h3 style='color:#ef4444;'>Total Egresos: S/. {df_g['monto'].sum():.2f}</h3></div>", unsafe_allow_html=True)
            else: st.info("No hay gastos registrados en la fecha seleccionada.")
        except Exception as e: st.error(f"Error procesando gastos.")
        st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 📦 MÓDULO 5: ALMACÉN Y COMPRAS
# ==========================================
elif menu == "📦 ALMACÉN Y COMPRAS" and ("inventario_ver" in st.session_state.user_perms or st.session_state.is_admin):
    st.markdown('<div class="main-header">Inventario y Catálogo</div>', unsafe_allow_html=True)
    t1, t2, t3, t4, t5 = st.tabs(["📋 Inventario General", "➕ Alta de Producto", "⚙️ Clasificación", "📓 KARDEX", "📈 Rotación de Productos"])
    
    with t1:
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        try:
            prods = supabase.table("productos").select("*, categorias(nombre), marcas(nombre)").execute()
            if prods.data: 
                df = pd.DataFrame(prods.data)
                df['Categoría'] = df['categorias'].apply(lambda x: x['nombre'] if isinstance(x, dict) else 'N/A')
                df['Marca'] = df['marcas'].apply(lambda x: x['nombre'] if isinstance(x, dict) else 'N/A')
                
                df['precio_lista'] = pd.to_numeric(df['precio_lista'], errors='coerce').fillna(0)
                df['costo_compra'] = pd.to_numeric(df['costo_compra'], errors='coerce').fillna(0)

                columnas_mostrar = ['codigo_barras', 'nombre', 'Categoría', 'Marca', 'precio_lista', 'stock_actual', 'stock_minimo']
                
                if st.session_state.is_admin:
                    df['Margen %'] = ((df['precio_lista'] - df['costo_compra']) / df['costo_compra'] * 100).fillna(0).round(1).astype(str) + "%"
                    columnas_mostrar.insert(4, 'costo_compra')
                    columnas_mostrar.insert(6, 'Margen %')
                
                df['precio_lista'] = df['precio_lista'].apply(lambda x: f"{float(x):.2f}")
                if 'costo_compra' in df.columns:
                    df['costo_compra'] = df['costo_compra'].apply(lambda x: f"{float(x):.2f}")

                if 'stock_minimo' not in df.columns: df['stock_minimo'] = 5
                
                def highlight_stock(row):
                    if row['stock_actual'] <= row['stock_minimo']: return ['background-color: #fef2f2; color: #dc2626'] * len(row)
                    return [''] * len(row)
                
                df_show = df[columnas_mostrar]
                st.dataframe(df_show.style.apply(highlight_stock, axis=1), use_container_width=True)
                
                if "inventario_modificar" in st.session_state.user_perms or st.session_state.is_admin:
                    st.divider()
                    st.write("#### ⚡ Reabastecimiento / Ajuste de Stock")
                    with st.form("form_add_stock"):
                        col_r1, col_r2 = st.columns([3, 1])
                        sel_p = col_r1.selectbox("Producto a modificar:", ["..."] + [f"{r['codigo_barras']} - {r['nombre']}" for _, r in df.iterrows()])
                        add_qty = col_r2.number_input("Cantidad entrante/saliente (Usa - para restar)", step=1, value=0)
                        motivo_auditoria = st.text_input("Motivo del Ajuste (Ej. 'Factura 001' o 'Conteo Físico') - OBLIGATORIO")
                        
                        if st.form_submit_button("💾 Ejecutar Ajuste Físico", type="primary"):
                            if sel_p != "..." and add_qty != 0:
                                if not motivo_auditoria.strip():
                                    st.error("🛑 AUDITORÍA: Debes ingresar el motivo para alterar el stock manualmente.")
                                else:
                                    c_up = sel_p.split(" - ")[0]
                                    try:
                                        if add_qty > 0: supabase.rpc("aumentar_stock", {"p_codigo": c_up, "p_cant": add_qty}).execute()
                                        else: supabase.rpc("reducir_stock", {"p_codigo": c_up, "p_cant": abs(add_qty)}).execute()
                                        
                                        tipo_mov = "INGRESO_MANUAL" if add_qty > 0 else "SALIDA_MANUAL"
                                        registrar_kardex(c_up, st.session_state.user_id, tipo_mov, abs(add_qty), f"Ajuste: {motivo_auditoria}")
                                        st.success(f"✅ Stock actualizado."); time.sleep(1.5); st.rerun()
                                    except Exception as db_err:
                                        st.error(f"Falla crítica: RPC no configurado en BD.")
        except Exception as e: st.error(f"Error cargando inventario.")
        st.markdown('</div>', unsafe_allow_html=True)

    with t2:
        if "inventario_agregar" in st.session_state.user_perms or st.session_state.is_admin:
            st.markdown('<div class="css-card">', unsafe_allow_html=True)
            cats, mars = load_data_cached("categorias"), load_data_cached("marcas")
            cals, comps = load_data_cached("calidades"), load_data_cached("compatibilidades")
            with st.form("form_nuevo", clear_on_submit=True):
                st.write("**Datos Principales**")
                c1, c2 = st.columns([1, 2])
                c_cod = c1.text_input("Código de Barras (Obligatorio)")
                c_nom = c2.text_input("Nombre / Descripción del Producto")
                
                st.write("**Clasificación**")
                f1, f2, f3, f8 = st.columns(4)
                f_cat = f1.selectbox("Categoría", cats['nombre'].tolist() if not cats.empty else [])
                f_mar = f2.selectbox("Marca", mars['nombre'].tolist() if not mars.empty else [])
                f_cal = f3.selectbox("Calidad", cals['nombre'].tolist() if not cals.empty else [])
                f_comp = f8.selectbox("Compatibilidad", comps['nombre'].tolist() if not comps.empty else [])
                
                st.write("**Costos y Almacén**")
                f4, f5, f6, f7 = st.columns(4)
                f_costo = f4.number_input("Costo Compra (S/.)", min_value=0.0)
                f_venta = f5.number_input("Precio Sugerido (S/.)", min_value=0.0)
                f_stock = f6.number_input("Stock Físico Inicial", min_value=0)
                f_smin = f7.number_input("Alerta de Stock Mínimo", value=5)
                
                if st.form_submit_button("🚀 GUARDAR EN BASE DE DATOS", type="primary"):
                    if c_cod and c_nom:
                        cid = int(cats[cats['nombre'] == f_cat]['id'].iloc[0])
                        mid = int(mars[mars['nombre'] == f_mar]['id'].iloc[0])
                        try:
                            supabase.table("productos").insert({"codigo_barras": c_cod, "nombre": c_nom, "categoria_id": cid, "marca_id": mid, "calidad": f_cal, "compatibilidad": f_comp, "costo_compra": f_costo, "precio_lista": f_venta, "precio_minimo": f_venta, "stock_actual": f_stock, "stock_inicial": f_stock, "stock_minimo": f_smin}).execute()
                            if f_stock > 0: registrar_kardex(c_cod, st.session_state.user_id, "INGRESO_COMPRA", f_stock, "Registro Inicial")
                            st.success("✅ Producto Registrado Exitosamente."); time.sleep(1); st.rerun()
                        except: st.error("❌ El código de barras ya existe.")
            st.markdown('</div>', unsafe_allow_html=True)

    with t3:
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        st.write("Añade nuevas opciones para los menús desplegables.")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            with st.form("fc"): v = st.text_input("Nueva Categoría"); st.form_submit_button("Añadir")
        with c2:
            with st.form("fm"): v = st.text_input("Nueva Marca"); st.form_submit_button("Añadir")
        with c3:
            with st.form("fcal"): v = st.text_input("Nueva Calidad"); st.form_submit_button("Añadir")
        with c4:
            with st.form("fcom"): v = st.text_input("Nueva Compatibilidad"); st.form_submit_button("Añadir")
        st.markdown('</div>', unsafe_allow_html=True)

    with t4:
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        st.write("Registro inmutable de movimientos de mercadería")
        try:
            k_data = supabase.table("movimientos_inventario").select("*, usuarios(nombre_completo)").order("timestamp", desc=True).limit(100).execute()
            if k_data.data:
                df_k = pd.DataFrame(k_data.data)
                df_k['Usuario'] = df_k['usuarios'].apply(lambda x: x.get('nombre_completo', 'Sys'))
                df_k['Fecha'] = pd.to_datetime(df_k['timestamp'], utc=True).dt.tz_convert('America/Lima').dt.strftime('%d/%m %H:%M')
                st.dataframe(df_k[['Fecha', 'producto_id', 'tipo_movimiento', 'cantidad', 'Usuario']], use_container_width=True)
        except: pass
        st.markdown('</div>', unsafe_allow_html=True)

    with t5:
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        st.write("Consulta la rotación exacta de artículos en una fecha pasada.")
        f_alm_dia = st.date_input("Selecciona la Fecha:", value=get_now().date(), key="f_alm_dia")
        try:
            start_dt = datetime.combine(f_alm_dia, datetime.min.time()).replace(tzinfo=pytz.timezone('America/Lima'))
            end_dt = start_dt + timedelta(days=1)
            cab_a = supabase.table("ventas_cabecera").select("*").gte("created_at", start_dt.isoformat()).lt("created_at", end_dt.isoformat()).execute()
            if cab_a.data:
                df_ca_dia = pd.DataFrame(cab_a.data)
                if not df_ca_dia.empty:
                    df_det, _, _ = obtener_costo_y_detalles_optimizado(df_ca_dia, supabase)
                    if not df_det.empty:
                        res_alm = df_det.groupby(['producto_id', 'nombre_prod']).agg(
                            Unidades_Vendidas=('cantidad', 'sum'), Dinero_Generado=('subtotal', 'sum')
                        ).reset_index().sort_values(by='Unidades_Vendidas', ascending=False)
                        st.dataframe(res_alm, use_container_width=True)
                    else: st.info("No hay detalles de venta registrados para esta fecha.")
                else: st.info("No hubo ventas en la fecha seleccionada.")
        except Exception as e: st.error(f"Calculando rotación...")
        st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# ⚠️ MÓDULO 6: MERMAS 
# ==========================================
elif menu == "⚠️ MERMAS" and ("mermas" in st.session_state.user_perms or st.session_state.is_admin):
    st.markdown('<div class="main-header">Registro de Mermas (Bajas)</div>', unsafe_allow_html=True)
    st.markdown('<div class="css-card">', unsafe_allow_html=True)
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
                st.write(f"**Producto a dar de baja:** {p_merma['nombre']} | **Stock Actual:** {p_merma['stock_actual']}")
                with st.form("form_merma"):
                    m_cant = st.number_input("Cantidad física a desechar", min_value=1, max_value=int(p_merma['stock_actual']) if p_merma['stock_actual']>0 else 1)
                    m_mot = st.selectbox("Motivo Operativo", ["Roto al instalar", "Falla de Fábrica", "Robo/Extravío"])
                    if st.form_submit_button("⚠️ CONFIRMAR PÉRDIDA FINANCIERA"):
                        if p_merma['stock_actual'] >= m_cant:
                            try: 
                                supabase.rpc("reducir_stock", {"p_codigo": m_cod, "p_cant": m_cant}).execute()
                                supabase.table("mermas").insert({"usuario_id": st.session_state.user_id, "producto_id": m_cod, "cantidad": m_cant, "motivo": m_mot, "perdida_monetaria": p_merma['costo_compra'] * m_cant}).execute()
                                registrar_kardex(m_cod, st.session_state.user_id, "SALIDA_MERMA", m_cant, m_mot)
                                st.success("✅ Baja documentada exitosamente."); time.sleep(1); st.rerun()
                            except Exception as e_rpc:
                                st.error(f"Falla de base de datos registrando merma.")
        except Exception as e: st.error(f"Falla cargando datos.")
    st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 👥 MÓDULO 7: GESTIÓN DE VENDEDORES (RRHH)
# ==========================================
elif menu == "👥 RRHH (Vendedores)" and ("gestion_usuarios" in st.session_state.user_perms or st.session_state.is_admin):
    st.markdown('<div class="main-header">Centro de Recursos Humanos</div>', unsafe_allow_html=True)
    
    def format_permisos(lista):
        if not isinstance(lista, list) or len(lista) == 0: return "Ninguno"
        if len(lista) >= 6: return "🌟 Acceso Total"
        if len(lista) > 2: return f"Varios ({len(lista)})"
        return ", ".join(lista)
        
    t_u1, t_u2, t_edit, t_u3, t_u4, t_u5, t_u6 = st.tabs(["📋 Plantilla", "➕ Nuevo", "✏️ Editar Perfil", "🔑 Clave", "⚙️ Permisos", "🗑️ Baja", "📊 Auditoría"])
    
    usrs_db = supabase.table("usuarios").select("*").execute()
    df_u, df_activos, df_inactivos = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    if usrs_db.data:
        df_u = pd.DataFrame(usrs_db.data)
        df_u['Permisos Asignados'] = df_u['permisos'].apply(format_permisos)
        df_activos = df_u[df_u['estado'] == 'Activo']
        df_inactivos = df_u[df_u['estado'] == 'Inactivo']
    
    with t_u1:
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        if not df_activos.empty: st.dataframe(df_activos[['nombre_completo', 'usuario', 'turno', 'Permisos Asignados']], use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
            
    with t_u2:
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        with st.form("form_new_user", clear_on_submit=True):
            n_nombre = st.text_input("Nombre Completo")
            n_user = st.text_input("Usuario (Login para el sistema)")
            n_pass = st.text_input("Contraseña Temporal")
            n_turno = st.selectbox("Turno", ["Mañana", "Tarde", "Completo", "Rotativo"])
            n_perms = st.multiselect("Permisos Especiales:", ["mermas", "inventario_ver", "inventario_agregar", "inventario_modificar", "inventario_eliminar", "reportes", "cierre_caja", "gestion_usuarios"])
            if st.form_submit_button("Registrar Empleado", type="primary"):
                if n_nombre and n_user and n_pass:
                    try:
                        hashed_pw = hash_password(n_pass)
                        supabase.table("usuarios").insert({"nombre_completo": n_nombre, "usuario": n_user, "clave": hashed_pw, "turno": n_turno, "permisos": n_perms, "estado": "Activo"}).execute()
                        st.success("✅ Cuenta Creada."); time.sleep(1.5); st.rerun()
                    except: st.error("❌ El Nombre de Usuario (Login) ya existe en el sistema. Elija otro.")
        st.markdown('</div>', unsafe_allow_html=True)

    with t_edit:
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        st.write("#### ✏️ Modificar Datos del Vendedor")
        if not df_activos.empty:
            usr_to_edit_prof = st.selectbox("Seleccionar empleado:", df_activos['usuario'].tolist(), key="sel_edit_prof")
            data_user = df_activos[df_activos['usuario'] == usr_to_edit_prof].iloc[0]
            with st.form("form_edit_profile"):
                new_nom = st.text_input("Nombre Completo", value=data_user['nombre_completo'])
                new_turn = st.selectbox("Turno", ["Mañana", "Tarde", "Completo", "Rotativo"], index=["Mañana", "Tarde", "Completo", "Rotativo"].index(data_user['turno']) if data_user['turno'] in ["Mañana", "Tarde", "Completo", "Rotativo"] else 0)
                if st.form_submit_button("💾 Guardar Cambios de Perfil", type="primary"):
                    try:
                        supabase.table("usuarios").update({"nombre_completo": new_nom, "turno": new_turn}).eq("usuario", usr_to_edit_prof).execute()
                        st.success("Perfil actualizado correctamente."); time.sleep(1); st.rerun()
                    except Exception as e: st.error(f"Falla actualizando perfil.")
        st.markdown('</div>', unsafe_allow_html=True)

    with t_u3:
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        if not df_activos.empty:
            with st.form("reset_pwd"):
                c_u = st.selectbox("Usuario a modificar:", df_activos['usuario'].tolist())
                n_pwd = st.text_input("Nueva Contraseña Obligatoria")
                if st.form_submit_button("Actualizar Seguridad", type="primary"):
                    if n_pwd:
                        try:
                            hashed_pw = hash_password(n_pwd)
                            supabase.table("usuarios").update({"clave": hashed_pw}).eq("usuario", c_u).execute()
                            st.success("✅ Contraseña Modificada."); time.sleep(1); st.rerun()
                        except Exception as e: st.error(f"Error actualizando clave.")
        st.markdown('</div>', unsafe_allow_html=True)

    with t_u4:
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        if not df_activos.empty:
            user_to_edit = st.selectbox("Seleccionar vendedor a editar:", df_activos['usuario'].tolist(), key="sel_edit_perm")
            raw_perms = supabase.table("usuarios").select("permisos").eq("usuario", user_to_edit).execute().data[0]['permisos']
            curr_perms = raw_perms if isinstance(raw_perms, list) else []
            
            with st.form("form_edit_perms"):
                lista_permisos = ["mermas", "inventario_ver", "inventario_agregar", "inventario_modificar", "inventario_eliminar", "reportes", "cierre_caja", "gestion_usuarios"]
                valid_curr = [p for p in curr_perms if p in lista_permisos]
                new_perms = st.multiselect("Permisos Activos (Agrega o quita con la 'X'):", lista_permisos, default=valid_curr)
                if st.form_submit_button("💾 Actualizar Accesos", type="primary"):
                    if user_to_edit == "admin" and "gestion_usuarios" not in new_perms:
                        st.error("⚠️ Operación Bloqueada: No puedes despojar al 'admin' de su acceso a RRHH.")
                    else:
                        try:
                            supabase.table("usuarios").update({"permisos": new_perms}).eq("usuario", user_to_edit).execute()
                            st.success(f"✅ Niveles de acceso actualizados."); time.sleep(1); st.rerun()
                        except Exception as e: st.error(f"Fallo en permisos.")
        st.markdown('</div>', unsafe_allow_html=True)

    with t_u5:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown('<div class="css-card">', unsafe_allow_html=True)
            if not df_activos.empty:
                v_b = df_activos[df_activos['usuario'] != 'admin']['usuario'].tolist()
                if v_b:
                    u_del = st.selectbox("Suspender Acceso (Despido/Falta):", v_b)
                    if st.button("🗑️ INHABILITAR USUARIO"):
                        try:
                            supabase.table("usuarios").update({"estado": "Inactivo"}).eq("usuario", u_del).execute(); st.rerun()
                        except Exception as e: st.error(f"Falla inhabilitando.")
                    st.divider()
                    if st.button("❌ ELIMINAR DEFINITIVAMENTE"):
                        try:
                            supabase.table("usuarios").delete().eq("usuario", u_del).execute()
                            st.success("✅ Usuario eliminado de la base de datos.")
                            time.sleep(1); st.rerun()
                        except Exception as e:
                            st.error("⚠️ No se puede eliminar. Este usuario ya tiene ventas o asistencias en su historial. Por favor, inhabilítalo.")
            st.markdown('</div>', unsafe_allow_html=True)
        with c2:
            st.markdown('<div class="css-card">', unsafe_allow_html=True)
            if not df_inactivos.empty:
                u_react = st.selectbox("Reactivar Acceso (Retorno):", df_inactivos['usuario'].tolist())
                if st.button("✅ RESTAURAR USUARIO", type="primary"):
                    try:
                        supabase.table("usuarios").update({"estado": "Activo"}).eq("usuario", u_react).execute(); st.rerun()
                    except Exception as e: st.error(f"Falla restaurando.")
            st.markdown('</div>', unsafe_allow_html=True)

    with t_u6:
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        if not df_activos.empty:
            st.write("#### 🎯 Informe Integral de Empleado")
            sel_u_nombre = st.selectbox("Selecciona un empleado para auditoría completa:", df_activos['nombre_completo'].tolist(), key="rrhh_vendedor")
            sel_u_id = df_activos[df_activos['nombre_completo'] == sel_u_nombre]['id'].iloc[0]
            f_rrhh_dia = st.date_input("📆 Día a auditar:", value=get_now().date(), key="f_rrhh_dia")
            
            try:
                start_dt = datetime.combine(f_rrhh_dia, datetime.min.time()).replace(tzinfo=pytz.timezone('America/Lima'))
                end_dt = start_dt + timedelta(days=1)
                
                ast_db = supabase.table("asistencia").select("*").eq("usuario_id", sel_u_id).gte("timestamp", start_dt.isoformat()).lt("timestamp", end_dt.isoformat()).execute()
                df_a = pd.DataFrame(ast_db.data) if ast_db.data else pd.DataFrame()
                
                h_in, h_out, hrs_hoy, dias_faltados, dias_asistidos = "--:--", "--:--", 0.0, 0, 0
                df_tabla_asistencia = pd.DataFrame()

                start_month = start_dt.replace(day=1)
                end_month = (start_month + timedelta(days=32)).replace(day=1)
                ast_month = supabase.table("asistencia").select("timestamp").eq("usuario_id", sel_u_id).gte("timestamp", start_month.isoformat()).lt("timestamp", end_month.isoformat()).execute()
                if ast_month.data:
                    df_a_month = pd.DataFrame(ast_month.data)
                    df_a_month['ts'] = pd.to_datetime(df_a_month['timestamp'], utc=True).dt.tz_convert('America/Lima')
                    dias_asistidos = df_a_month['ts'].dt.date.nunique()

                if not df_a.empty:
                    df_a['ts'] = pd.to_datetime(df_a['timestamp'], utc=True).dt.tz_convert('America/Lima')
                    df_hoy_a = df_a.sort_values('ts')
                    
                    if not df_hoy_a.empty:
                        df_tabla_asistencia = df_hoy_a[['tipo_marcacion', 'ts']].copy()
                        df_tabla_asistencia['Hora Local'] = df_tabla_asistencia['ts'].dt.strftime('%I:%M %p')
                        
                        h_in = df_hoy_a.iloc[0]['ts'].strftime('%I:%M %p')
                        if df_hoy_a.iloc[-1]['tipo_marcacion'] == 'Salida':
                            h_out = df_hoy_a.iloc[-1]['ts'].strftime('%I:%M %p')
                        
                        total_secs = 0
                        last_in = None
                        for _, row in df_hoy_a.iterrows():
                            if row['tipo_marcacion'] == 'Ingreso': last_in = row['ts']
                            elif row['tipo_marcacion'] == 'Salida' and last_in is not None:
                                total_secs += (row['ts'] - last_in).total_seconds()
                                last_in = None
                        if last_in is not None and f_rrhh_dia == get_now().date():
                            total_secs += (get_now() - last_in).total_seconds()
                        
                        hrs_hoy = total_secs / 3600.0
                
                dias_totales_mes = get_now().date().day if f_rrhh_dia.month == get_now().month else 30
                dias_faltados = dias_totales_mes - dias_asistidos if dias_totales_mes > dias_asistidos else 0

                cab_v = supabase.table("ventas_cabecera").select("*").eq("usuario_id", sel_u_id).gte("created_at", start_dt.isoformat()).lt("created_at", end_dt.isoformat()).execute()
                v_hoy_ventas, v_hoy_costo, v_hoy_utilidad = 0.0, 0.0, 0.0
                
                if cab_v.data:
                    df_cv_dia = pd.DataFrame(cab_v.data)
                    
                    if not df_cv_dia.empty:
                        v_hoy_ventas = df_cv_dia['total_venta'].sum()
                        _df_rrhh_det, v_hoy_costo, _ = obtener_costo_y_detalles_optimizado(df_cv_dia, supabase)
                        v_hoy_utilidad = v_hoy_ventas - v_hoy_costo

                st.write("**Desempeño Financiero (Productividad)**")
                c4, c5, c6 = st.columns(3)
                c4.markdown(f"<div class='metric-box'><div class='metric-title'>Dinero a Caja</div><div class='metric-value-small metric-blue'>S/. {v_hoy_ventas:.2f}</div></div>", unsafe_allow_html=True)
                c5.markdown(f"<div class='metric-box'><div class='metric-title'>Costo Mercadería</div><div class='metric-value-small metric-orange'>- S/. {v_hoy_costo:.2f}</div></div>", unsafe_allow_html=True)
                c6.markdown(f"<div class='metric-box' style='border:2px solid #8b5cf6;'><div class='metric-title'>UTILIDAD GENERADA</div><div class='metric-value-small metric-purple'>S/. {v_hoy_utilidad:.2f}</div></div>", unsafe_allow_html=True)

                st.write("**Control de Asistencia y Turnos**")
                c1, c2, c3, c4_ast = st.columns(4)
                c1.markdown(f"<div class='metric-box'><div class='metric-title'>1er Ingreso</div><div class='metric-value-small'>{h_in}</div></div>", unsafe_allow_html=True)
                c2.markdown(f"<div class='metric-box'><div class='metric-title'>Última Salida</div><div class='metric-value-small'>{h_out}</div></div>", unsafe_allow_html=True)
                c3.markdown(f"<div class='metric-box'><div class='metric-title'>Hrs Trabajadas Hoy</div><div class='metric-value-small metric-green'>{hrs_hoy:.1f} Hrs</div></div>", unsafe_allow_html=True)
                c4_ast.markdown(f"<div class='metric-box'><div class='metric-title'>Días Trabajados (Mes)</div><div class='metric-value-small metric-blue'>{dias_asistidos} Días</div></div>", unsafe_allow_html=True)
                
                if not df_tabla_asistencia.empty:
                    with st.expander("Ver bitácora de marcaciones del día (Entradas/Salidas)", expanded=False):
                        st.dataframe(df_tabla_asistencia[['tipo_marcacion', 'Hora Local']], use_container_width=True)

            except Exception as e: st.info("Evaluando datos en segundo plano...")
        st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 📊 MÓDULO 8: REPORTES Y CIERRE SÚPER BLINDADO
# ==========================================
elif menu == "📊 REPORTES Y CIERRE" and ("cierre_caja" in st.session_state.user_perms or "reportes" in st.session_state.user_perms or st.session_state.is_admin):
    st.markdown('<div class="main-header">Auditoría Financiera y Tesorería</div>', unsafe_allow_html=True)
    
    es_gerencia = st.session_state.is_admin or "reportes" in st.session_state.user_perms
    
    if st.session_state.ticket_cierre:
        tk = st.session_state.ticket_cierre
        st.success("✅ Reporte Z Generado Correctamente.")
        
        ticket_cajero_html = f"""
        <div class="ticket-termico">
            <center><b>ACCESORIOS JORDAN</b><br><b>REPORTE Z (CIERRE TURNO)</b></center>
            --------------------------------<br>
            FECHA CIERRE: {tk['fecha']}<br>
            CAJERO RESP: {st.session_state.user_name}<br>
            --------------------------------<br>
            <b>💰 INGRESOS BRUTOS: S/. {tk['tot_ventas']:.2f}</b><br>
            - En Efectivo: S/. {tk['ventas_efectivo']:.2f}<br>
            - En Digital: S/. {tk['ventas_digital']:.2f}<br>
            Volumen Venta: {tk['cant_vendida']} items.<br>
            --------------------------------<br>
            <b>📉 SALIDAS DE CAJA:</b><br>
            Gastos Operativos: S/. {tk['tot_gastos']:.2f}<br>
            Devoluciones: S/. {tk['tot_dev']:.2f}<br>
            --------------------------------<br>
            <b>🏦 EFECTIVO A ENTREGAR AL DUEÑO: S/. {tk['caja_efectivo']:.2f}</b><br>
            --------------------------------<br>
            {tk['alertas_stock']}
        </div>
        """
        st.markdown(ticket_cajero_html, unsafe_allow_html=True)
        if st.button("🧹 Iniciar Nuevo Turno Operativo", type="primary"):
            st.session_state.ticket_cierre = None
            st.rerun()
    else:
        tabs_disponibles = ["📊 Balance de Turno (Caja)"]
        if es_gerencia:
            tabs_disponibles.extend(["📆 Historial Diario", "🧾 Historial de Tickets", "🖨️ Reimprimir Cierres Z"])
            tabs = st.tabs(tabs_disponibles)
            t_rep1, t_rep2, t_rep3, t_rep4 = tabs[0], tabs[1], tabs[2], tabs[3]
        else:
            tabs = st.tabs(tabs_disponibles)
            t_rep1 = tabs[0]
            t_rep2, t_rep3, t_rep4 = None, None, None
        
        with t_rep1:
            st.markdown('<div class="css-card">', unsafe_allow_html=True)
            try:
                lc = get_last_cierre_dt()
                lc_iso = lc.isoformat()
                st.caption(f"Contabilizando movimientos en tiempo real desde el último cierre: {lc.strftime('%d/%m/%Y %I:%M %p')}")
                
                cab_all = supabase.table("ventas_cabecera").select("*").gte("created_at", lc_iso).execute()
                
                # 🛡️ FILTRO DUAL INTELIGENTE PARA TABLAS CON COLUMNAS MIXTAS
                try: gst_all = supabase.table("gastos").select("*").gte("created_at", lc_iso).execute()
                except: gst_all = supabase.table("gastos").select("*").gte("fecha", lc_iso).execute()
                
                try: dev_all = supabase.table("devoluciones").select("*").gte("created_at", lc_iso).execute()
                except: dev_all = supabase.table("devoluciones").select("*").gte("fecha", lc_iso).execute()
                
                try: mer_all = supabase.table("mermas").select("*").gte("created_at", lc_iso).execute()
                except: mer_all = supabase.table("mermas").select("*").gte("fecha", lc_iso).execute()
                
                tot_v, v_efe, v_dig, tot_costo, tot_gst, tot_dev, tot_merma = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
                c_ven = 0
                
                if cab_all.data:
                    df_c = pd.DataFrame(cab_all.data)
                    if not df_c.empty:
                        v_efe = df_c[df_c['metodo_pago'] == 'Efectivo']['total_venta'].sum()
                        v_dig = df_c[df_c['metodo_pago'] != 'Efectivo']['total_venta'].sum()
                        tot_v = v_efe + v_dig
                        _df_costo_det, tot_costo, c_ven = obtener_costo_y_detalles_optimizado(df_c, supabase)
                
                if gst_all.data: tot_gst = pd.DataFrame(gst_all.data)['monto'].sum()
                if dev_all.data: tot_dev = pd.DataFrame(dev_all.data)['dinero_devuelto'].sum()
                if mer_all.data: tot_merma = pd.DataFrame(mer_all.data)['perdida_monetaria'].sum()
                
                ganancia_bruta = tot_v - tot_costo
                ganancia_neta = ganancia_bruta - tot_gst - tot_dev - tot_merma
                caja_efectivo = v_efe - tot_gst - tot_dev 
                
                st.write("**1. Ingresos y Dinero Físico**")
                c1, c2, c3 = st.columns(3)
                c1.markdown(f"<div class='metric-box'><div class='metric-title'>Ventas Totales Brutas</div><div class='metric-value metric-blue'>S/.{tot_v:.2f}</div></div>", unsafe_allow_html=True)
                c2.markdown(f"<div class='metric-box'><div class='metric-title'>Pagos Efectivo (Caja)</div><div class='metric-value'>S/.{v_efe:.2f}</div></div>", unsafe_allow_html=True)
                c3.markdown(f"<div class='metric-box'><div class='metric-title'>Pagos Digitales</div><div class='metric-value metric-purple'>S/.{v_dig:.2f}</div></div>", unsafe_allow_html=True)
                
                if es_gerencia:
                    st.write("**2. Descuentos, Inversión y Fugas**")
                    c4, c5, c6 = st.columns(3)
                    c4.markdown(f"<div class='metric-box'><div class='metric-title'>Costo Mercadería (Inversión)</div><div class='metric-value-small metric-orange'>- S/.{tot_costo:.2f}</div></div>", unsafe_allow_html=True)
                    c5.markdown(f"<div class='metric-box'><div class='metric-title'>Gastos Operativos Caja</div><div class='metric-value-small metric-red'>- S/.{tot_gst:.2f}</div></div>", unsafe_allow_html=True)
                    c6.markdown(f"<div class='metric-box'><div class='metric-title'>Devoluciones/Mermas</div><div class='metric-value-small metric-red'>- S/.{tot_dev + tot_merma:.2f}</div></div>", unsafe_allow_html=True)
                    
                    st.write("**3. Resultados del Negocio**")
                    c7, c8 = st.columns(2)
                    c7.markdown(f"<div class='metric-box' style='border-left: 5px solid #8b5cf6;'><div class='metric-title'>GANANCIA NETA (UTILIDAD PURA)</div><div class='metric-value metric-purple'>S/.{ganancia_neta:.2f}</div></div>", unsafe_allow_html=True)
                    c8.markdown(f"<div class='metric-box' style='background: #ecfdf5; border-left: 5px solid #10b981;'><div class='metric-title'>EFECTIVO FÍSICO A RENDIR EN CAJA</div><div class='metric-value metric-green'>S/.{caja_efectivo:.2f}</div></div>", unsafe_allow_html=True)
                else:
                    st.write("**2. Resumen Operativo y Gastos**")
                    cx1, cx2, cx3 = st.columns(3)
                    cx1.markdown(f"<div class='metric-box'><div class='metric-title'>Gastos Autorizados</div><div class='metric-value-small metric-red'>- S/.{tot_gst:.2f}</div></div>", unsafe_allow_html=True)
                    cx2.markdown(f"<div class='metric-box'><div class='metric-title'>Devoluciones Clientes</div><div class='metric-value-small metric-red'>- S/.{tot_dev:.2f}</div></div>", unsafe_allow_html=True)
                    cx3.markdown(f"<div class='metric-box' style='background: #ecfdf5; border-left: 5px solid #10b981;'><div class='metric-title'>EFECTIVO A RENDIR</div><div class='metric-value metric-green'>S/.{caja_efectivo:.2f}</div></div>", unsafe_allow_html=True)

                st.divider()
                if "cierre_caja" in st.session_state.user_perms or st.session_state.is_admin:
                    with st.form("f_cierre"):
                        st.write("🛑 **¿Terminó el turno? Extrae y asegura el balance.**")
                        if st.form_submit_button("🔒 APROBAR CIERRE DE CAJA E IMPRIMIR Z", type="primary"):
                            try:
                                supabase.table("cierres_caja").insert({"total_ventas": tot_v, "utilidad": ganancia_neta}).execute()
                                
                                bajos = supabase.table("productos").select("nombre, stock_actual").lte("stock_actual", 20).execute()
                                alert_html = ""
                                if bajos.data:
                                    alert_html = "<b>⚠️ COMPRAS SUGERIDAS (STOCK BAJO):</b><br>"
                                    for b in bajos.data: alert_html += f"- {b['nombre']}: {b['stock_actual']} ud<br>"
                                    alert_html += "--------------------------------<br>"
                                    
                                st.session_state.ticket_cierre = {
                                    'fecha': get_now().strftime('%d/%m/%Y %I:%M %p'),
                                    'cant_vendida': c_ven, 'tot_ventas': tot_v, 'ventas_efectivo': v_efe, 'ventas_digital': v_dig,
                                    'capital_inv': tot_costo, 'tot_dev': tot_dev, 'tot_merma': tot_merma, 'tot_gastos': tot_gst,
                                    'ganancia_bruta': ganancia_bruta, 'caja_efectivo': caja_efectivo, 'utilidad': ganancia_neta, 'alertas_stock': alert_html
                                }
                                
                                tk_z_num = f"Z-{int(time.time())}"
                                tk_admin_html = f"""
                                <div class="ticket-termico">
                                    <center><b>ACCESORIOS JORDAN</b><br><b>REPORTE Z (CONFIDENCIAL ADMIN)</b></center>
                                    --------------------------------<br>
                                    FECHA CIERRE: {st.session_state.ticket_cierre['fecha']}<br>
                                    CAJERO: {st.session_state.user_name}<br>
                                    --------------------------------<br>
                                    <b>💰 INGRESOS BRUTOS: S/. {tot_v:.2f}</b><br>
                                    - Efectivo: S/. {v_efe:.2f}<br>
                                    - Digital: S/. {v_dig:.2f}<br>
                                    Volumen: {c_ven} items.<br>
                                    --------------------------------<br>
                                    <b>📉 COSTOS Y SALIDAS CAJA:</b><br>
                                    Capital Inv: S/. {tot_costo:.2f}<br>
                                    Gastos Caja: S/. {tot_gst:.2f}<br>
                                    Mermas: S/. {tot_merma:.2f}<br>
                                    Devoluciones: S/. {tot_dev:.2f}<br>
                                    --------------------------------<br>
                                    <b>📊 RENDIMIENTO NETO:</b><br>
                                    Ganancia Bruta: S/. {ganancia_bruta:.2f}<br>
                                    <b>UTILIDAD PURA: S/. {ganancia_neta:.2f}</b><br>
                                    --------------------------------<br>
                                    <b>🏦 EFECTIVO RENDIR: S/. {caja_efectivo:.2f}</b><br>
                                    --------------------------------<br>
                                </div>
                                """
                                try: supabase.table("ticket_historial").insert({"ticket_numero": tk_z_num, "usuario_id": st.session_state.user_id, "html_payload": tk_admin_html}).execute()
                                except Exception as log_err: logging.error(f"Falla insertando historial Z.")
                                
                                st.rerun()
                            except Exception as cierre_err:
                                st.error(f"Falla catastrófica ejecutando Cierre de Caja.")
            except Exception as e: st.error(f"Sistema a la espera de transacciones...")
            st.markdown('</div>', unsafe_allow_html=True)

        if t_rep2:
            with t_rep2:
                st.markdown('<div class="css-card">', unsafe_allow_html=True)
                st.write("Auditoría histórica: Revisa ingresos, costos y ganancias de días cerrados.")
                f_dia = st.date_input("📆 Selecciona el día de operación:", value=get_now().date())
                
                try:
                    start_dt = datetime.combine(f_dia, datetime.min.time()).replace(tzinfo=pytz.timezone('America/Lima'))
                    end_dt = start_dt + timedelta(days=1)
                    start_iso = start_dt.isoformat()
                    end_iso = end_dt.isoformat()
                    
                    cab_all = supabase.table("ventas_cabecera").select("*").gte("created_at", start_iso).lt("created_at", end_iso).execute()
                    
                    # 🛡️ FILTRO DUAL HISTÓRICO
                    try: gst_all = supabase.table("gastos").select("*").gte("created_at", start_iso).lt("created_at", end_iso).execute()
                    except: gst_all = supabase.table("gastos").select("*").gte("fecha", start_iso).lt("fecha", end_iso).execute()
                    
                    try: dev_all = supabase.table("devoluciones").select("*").gte("created_at", start_iso).lt("created_at", end_iso).execute()
                    except: dev_all = supabase.table("devoluciones").select("*").gte("fecha", start_iso).lt("fecha", end_iso).execute()
                    
                    try: mermas_all = supabase.table("mermas").select("*").gte("created_at", start_iso).lt("created_at", end_iso).execute()
                    except: mermas_all = supabase.table("mermas").select("*").gte("fecha", start_iso).lt("fecha", end_iso).execute()
                    
                    r_v_tot, r_v_efe, r_v_dig, r_costo, r_gst, r_dev, r_merma = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
                    
                    if cab_all.data:
                        df_c_dia = pd.DataFrame(cab_all.data)
                        if not df_c_dia.empty:
                            r_v_efe = df_c_dia[df_c_dia['metodo_pago'] == 'Efectivo']['total_venta'].sum()
                            r_v_dig = df_c_dia[df_c_dia['metodo_pago'] != 'Efectivo']['total_venta'].sum()
                            r_v_tot = r_v_efe + r_v_dig
                            _df_hist_det, r_costo, _ = obtener_costo_y_detalles_optimizado(df_c_dia, supabase)

                    if gst_all.data: r_gst = pd.DataFrame(gst_all.data)['monto'].sum()
                    if dev_all.data: r_dev = pd.DataFrame(dev_all.data)['dinero_devuelto'].sum()
                    if mermas_all.data: r_merma = pd.DataFrame(mermas_all.data)['perdida_monetaria'].sum()

                    r_g_neta = r_v_tot - r_costo - r_gst - r_dev - r_merma
                    
                    if r_v_tot > 0 or r_gst > 0:
                        st.write("**Resumen de Flujo de Caja**")
                        c1, c2, c3, c4 = st.columns(4)
                        c1.markdown(f"<div class='metric-box'><div class='metric-title'>Ingresos Brutos</div><div class='metric-value-small metric-blue'>S/.{r_v_tot:.2f}</div></div>", unsafe_allow_html=True)
                        c2.markdown(f"<div class='metric-box'><div class='metric-title'>Costo Inventario</div><div class='metric-value-small metric-orange'>- S/.{r_costo:.2f}</div></div>", unsafe_allow_html=True)
                        c3.markdown(f"<div class='metric-box'><div class='metric-title'>Egresos (Gast/Dev)</div><div class='metric-value-small metric-red'>- S/.{r_gst + r_dev + r_merma:.2f}</div></div>", unsafe_allow_html=True)
                        c4.markdown(f"<div class='metric-box' style='border-left:4px solid #8b5cf6;'><div class='metric-title'>Utilidad Neta Pura</div><div class='metric-value-small metric-purple'>S/.{r_g_neta:.2f}</div></div>", unsafe_allow_html=True)
                    else:
                        st.info("Sin registros contables en este día específico.")
                except Exception as e: st.error("Procesando datos históricos...")
                st.markdown('</div>', unsafe_allow_html=True)

        if t_rep3:
            with t_rep3:
                st.markdown('<div class="css-card">', unsafe_allow_html=True)
                st.write("Directorio de facturas normales emitidas a clientes.")
                try:
                    tks = supabase.table("ticket_historial").select("ticket_numero, fecha, html_payload").ilike("ticket_numero", "AJ-%").order("fecha", desc=True).limit(50).execute()
                    if tks.data:
                        df_tks = pd.DataFrame(tks.data)
                        df_tks['fecha_format'] = pd.to_datetime(df_tks['fecha'], utc=True).dt.tz_convert('America/Lima').dt.strftime('%d/%m/%Y %I:%M %p')
                        opciones = [f"{row['ticket_numero']} - {row['fecha_format']}" for _, row in df_tks.iterrows()]
                        sel_tk = st.selectbox("Selecciona un ticket para visualizar", opciones)
                        if sel_tk:
                            tk_num = sel_tk.split(" - ")[0]
                            html_raw = df_tks[df_tks['ticket_numero'] == tk_num]['html_payload'].iloc[0]
                            st.markdown(html_raw.replace("<script>window.onload=function(){window.print();}</script>", ""), unsafe_allow_html=True)
                except: pass
                st.markdown('</div>', unsafe_allow_html=True)
                
        if t_rep4:
            with t_rep4:
                st.markdown('<div class="css-card">', unsafe_allow_html=True)
                st.write("Directorio de Reportes Z Generados (Reimpresión con detalle financiero)")
                try:
                    tks_z = supabase.table("ticket_historial").select("ticket_numero, fecha, html_payload").ilike("ticket_numero", "Z-%").order("fecha", desc=True).limit(20).execute()
                    if tks_z.data:
                        df_tks_z = pd.DataFrame(tks_z.data)
                        df_tks_z['fecha_format'] = pd.to_datetime(df_tks_z['fecha'], utc=True).dt.tz_convert('America/Lima').dt.strftime('%d/%m/%Y %I:%M %p')
                        opciones_z = [f"{row['ticket_numero']} - {row['fecha_format']}" for _, row in df_tks_z.iterrows()]
                        sel_tk_z = st.selectbox("Selecciona un Cierre Z pasado", opciones_z)
                        if sel_tk_z:
                            tk_num_z = sel_tk_z.split(" - ")[0]
                            html_raw_z = df_tks_z[df_tks_z['ticket_numero'] == tk_num_z]['html_payload'].iloc[0]
                            st.markdown(html_raw_z, unsafe_allow_html=True)
                    else:
                        st.info("Aún no se ha guardado ningún Cierre Z en el historial.")
                except: pass
                st.markdown('</div>', unsafe_allow_html=True)
