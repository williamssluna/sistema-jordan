import streamlit as st
from supabase import create_client
import pandas as pd
import zxingcpp
import cv2
import numpy as np
from datetime import datetime
import time
import plotly.express as px

# --- 1. CONEXIÓN BLINDADA ---
URL_SUPABASE = "https://degzltrjrzqbahdonmmb.supabase.co"
KEY_SUPABASE = "sb_publishable_td5_vXX42LYc8PlTAbBgVg_-xCp-94r"
supabase = create_client(URL_SUPABASE, KEY_SUPABASE)

st.set_page_config(page_title="JORDAN POS SMART", layout="wide", page_icon="📱")

# --- 2. ESTILO VISUAL "SMART BLUE" ---
st.markdown("""
    <style>
    .stApp { background-color: #f1f5f9; }
    .main-header { font-size: 30px; font-weight: 800; color: #1e3a8a; text-align: center; padding: 15px; border-bottom: 4px solid #1e3a8a; margin-bottom: 20px; }
    .css-card { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); border-left: 6px solid #2563eb; }
    .ticket-termico { 
        background: white; color: black; font-family: 'Courier New', monospace; 
        padding: 15px; border: 1px dashed #333; width: 280px; margin: 0 auto; line-height: 1.1; font-size: 13px;
    }
    .stButton>button { border-radius: 8px; font-weight: 700; height: 3.5em; transition: 0.3s; }
    .stButton>button:hover { background-color: #1e3a8a !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. GESTIÓN DE MEMORIA (STATE) ---
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'last_ticket' not in st.session_state: st.session_state.last_ticket = None
if 'admin_auth' not in st.session_state: st.session_state.admin_auth = False

# --- 4. FUNCIONES DE EXPERTO ---
def scan_pos(image):
    if not image: return None
    file_bytes = np.asarray(bytearray(image.read()), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, 1)
    res = zxingcpp.read_barcodes(img)
    return res[0].text if res else None

def load_data(table):
    try:
        res = supabase.table(table).select("*").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except: return pd.DataFrame()

def login():
    if not st.session_state.admin_auth:
        with st.sidebar:
            st.markdown("### 🔐 Acceso Admin")
            u = st.text_input("Usuario")
            p = st.text_input("Clave", type="password")
            if st.button("Ingresar"):
                if u == "admin" and p == "12345":
                    st.session_state.admin_auth = True
                    st.rerun()
                else: st.error("Error")
        return False
    return True

# --- CABECERA ---
st.markdown('<div class="main-header">📱 ACCESORIOS JORDAN | SMART POS v4.0</div>', unsafe_allow_html=True)

menu = st.sidebar.radio("SISTEMA", ["🛒 VENTAS (POS)", "📦 ALMACÉN PRO", "🔄 DEVOLUCIONES", "⚠️ MERMAS/DAÑOS", "📊 REPORTES"])

# ==========================================
# 🛒 MÓDULO 1: VENTAS (CARRITO + TICKET)
# ==========================================
if menu == "🛒 VENTAS (POS)":
    col_v1, col_v2 = st.columns([1.8, 1.2])

    with col_v1:
        st.subheader("🔍 Buscador de Accesorios")
        with st.expander("📷 SCANNER (Lector de Barras)", expanded=True):
            img = st.camera_input("Lector", key="scanner_venta", label_visibility="hidden")
            if img:
                code = scan_pos(img)
                if code:
                    prod_db = supabase.table("productos").select("*").eq("codigo_barras", code).execute()
                    if prod_db.data:
                        p = prod_db.data[0]
                        # Agregar al carrito o sumar cantidad
                        exist = False
                        for item in st.session_state.carrito:
                            if item['id'] == code:
                                item['cant'] += 1
                                exist = True
                        if not exist:
                            st.session_state.carrito.append({'id': code, 'nombre': p['nombre'], 'precio': float(p['precio_lista']), 'cant': 1, 'costo': float(p['costo_compra'])})
                        st.success(f"Añadido: {p['nombre']}")
                        time.sleep(0.6)
                        st.rerun()

        search = st.text_input("Escribe nombre, marca o modelo...")
        if search:
            res_s = supabase.table("productos").select("*, marcas(nombre)").ilike("nombre", f"%{search}%").execute()
            if res_s.data:
                for p in res_s.data:
                    c_p1, c_p2, c_p3 = st.columns([3, 1, 1])
                    c_p1.write(f"**{p['nombre']}** ({p['marcas']['nombre']})")
                    c_p2.write(f"S/. {p['precio_lista']}")
                    if c_p3.button("➕", key=f"add_{p['codigo_barras']}"):
                        st.session_state.carrito.append({'id': p['codigo_barras'], 'nombre': p['nombre'], 'precio': float(p['precio_lista']), 'cant': 1, 'costo': float(p['costo_compra'])})
                        st.rerun()

    with col_v2:
        st.subheader("🛍️ Carrito")
        if not st.session_state.carrito:
            st.info("Escanea productos para empezar.")
        else:
            total = 0
            for i, item in enumerate(st.session_state.carrito):
                c_c1, c_c2, c_c3 = st.columns([3, 1, 0.5])
                c_c1.write(f"**{item['cant']}x** {item['nombre']}")
                c_c2.write(f"S/. {item['precio']*item['cant']:.2f}")
                if c_c3.button("❌", key=f"del_{i}"):
                    st.session_state.carrito.pop(i)
                    st.rerun()
                total += item['precio'] * item['cant']
            
            st.divider()
            st.markdown(f"## TOTAL: S/. {total:.2f}")
            
            pago = st.selectbox("Medio de Pago", ["Efectivo", "Yape", "Plin", "Tarjeta"])
            doc = st.selectbox("Comprobante", ["Ticket Interno", "Boleta Electrónica"])
            
            if st.button("🏁 CONFIRMAR VENTA", type="primary", use_container_width=True):
                t_num = f"AJ-{int(time.time())}"
                # 1. Cabecera
                res_cab = supabase.table("ventas_cabecera").insert({
                    "ticket_numero": t_num, "total_venta": total, "metodo_pago": pago, "tipo_comprobante": doc
                }).execute()
                
                v_id = res_cab.data[0]['id']
                # 2. Detalle y Stock
                for item in st.session_state.carrito:
                    supabase.table("ventas_detalle").insert({
                        "venta_id": v_id, "producto_id": item['id'], "cantidad": item['cant'],
                        "precio_unitario": item['precio'], "subtotal": item['precio'] * item['cant']
                    }).execute()
                    
                    stk = supabase.table("productos").select("stock_actual").eq("codigo_barras", item['id']).execute()
                    supabase.table("productos").update({"stock_actual": stk.data[0]['stock_actual'] - item['cant']}).eq("codigo_barras", item['id']).execute()
                
                st.session_state.last_ticket = {'num': t_num, 'items': st.session_state.carrito.copy(), 'total': total, 'pago': pago}
                st.session_state.carrito = []
                st.balloons()
                st.rerun()

        if st.session_state.last_ticket:
            st.divider()
            with st.expander("🖨️ TICKET PARA IMPRESORA POS", expanded=True):
                tk = st.session_state.last_ticket
                st.markdown(f"""
                <div class="ticket-termico">
                    <b>ACCESORIOS JORDAN</b><br>
                    Cusco - Perú<br>
                    ----------------------------<br>
                    TICKET: {tk['num']}<br>
                    FECHA: {datetime.now().strftime('%d/%m/%Y %H:%M')}<br>
                    ----------------------------<br>
                """, unsafe_allow_html=True)
                for it in tk['items']:
                    st.write(f"{it['nombre'][:18]:<18} {it['cant']:>2} {it['precio']*it['cant']:>7.2f}")
                st.markdown(f"""
                    ----------------------------<br>
                    <b>TOTAL: S/. {tk['total']:.2f}</b><br>
                    PAGO: {tk['pago']}<br>
                    ----------------------------<br>
                    ¡Gracias por su compra!
                </div>
                """, unsafe_allow_html=True)

# ==========================================
# 📦 MÓDULO 2: ALMACÉN (CATEGORÍAS Y MARCAS)
# ==========================================
elif menu == "📦 ALMACÉN PRO":
    if login():
        st.subheader("Gestión Central de Inventario")
        t1, t2 = st.tabs(["📋 Catálogo Completo", "➕ Nuevo Ingreso"])
        
        with t1:
            prods = load_data("productos")
            if not prods.empty: st.dataframe(prods, use_container_width=True)
            
        with t2:
            cats = load_data("categorias")
            mars = load_data("marcas")
            
            with st.form("form_nuevo"):
                st.write("### Datos de Mercadería")
                c_cod = st.text_input("Escanea Código de Barras")
                c_nom = st.text_input("Nombre / Modelo del Accesorio")
                
                f1, f2, f3 = st.columns(3)
                f_cat = f1.selectbox("Categoría", cats['nombre'].tolist())
                f_mar = f2.selectbox("Marca", mars['nombre'].tolist())
                f_cal = f3.selectbox("Calidad", ["Genérico", "Original", "AAA", "Premium"])
                
                f4, f5, f6 = st.columns(3)
                f_costo = f4.number_input("Costo Compra (S/.)", min_value=0.0)
                f_venta = f5.number_input("Precio Venta (S/.)", min_value=0.0)
                f_stock = f6.number_input("Stock Inicial", min_value=0)
                
                if st.form_submit_button("🚀 REGISTRAR EN SISTEMA"):
                    cid = int(cats[cats['nombre'] == f_cat]['id'].values[0])
                    mid = int(mars[mars['nombre'] == f_mar]['id'].values[0])
                    supabase.table("productos").insert({
                        "codigo_barras": c_cod, "nombre": c_nom, "categoria_id": cid, "marca_id": mid,
                        "calidad": f_cal, "costo_compra": f_costo, "precio_lista": f_venta,
                        "precio_minimo": f_costo, "stock_actual": f_stock
                    }).execute()
                    st.success("Ingreso exitoso.")

# ==========================================
# 🔄 MÓDULO 3: DEVOLUCIONES
# ==========================================
elif menu == "🔄 DEVOLUCIONES":
    st.subheader("Registro de Devoluciones de Clientes")
    tick = st.text_input("Número de Ticket (Ej. AJ-17000000)")
    if tick:
        v_cab = supabase.table("ventas_cabecera").select("*").eq("ticket_numero", tick).execute()
        if v_cab.data:
            v_id = v_cab.data[0]['id']
            v_det = supabase.table("ventas_detalle").select("*, productos(nombre)").eq("venta_id", v_id).execute()
            for d in v_det.data:
                col_d1, col_d2 = st.columns([3, 1])
                col_d1.write(f"Item: {d['productos']['nombre']} (Cant: {d['cantidad']})")
                if col_d2.button("Devolver", key=f"dev_{d['id']}"):
                    # 1. Recuperar Stock
                    p_s = supabase.table("productos").select("stock_actual").eq("codigo_barras", d['producto_id']).execute()
                    supabase.table("productos").update({"stock_actual": p_s.data[0]['stock_actual'] + d['cantidad']}).eq("codigo_barras", d['producto_id']).execute()
                    # 2. Registrar Devolución
                    supabase.table("devoluciones").insert({
                        "producto_id": d['producto_id'], "cantidad": d['cantidad'], "motivo": "Devolución Cliente",
                        "dinero_devuelto": d['subtotal'], "estado_producto": "Vuelve a tienda"
                    }).execute()
                    st.success("Stock recuperado y dinero registrado como egreso.")
                    time.sleep(1); st.rerun()

# ==========================================
# ⚠️ MÓDULO 4: MERMAS (PRODUCTO DAÑADO)
# ==========================================
elif menu == "⚠️ MERMAS/DAÑOS":
    st.subheader("Baja de Productos (Dañados / Fallados)")
    with st.form("form_merma"):
        m_cod = st.text_input("Código de Barras")
        m_cant = st.number_input("Cantidad dañada", min_value=1)
        m_mot = st.selectbox("Motivo", ["Roto en Tienda", "Falla de Fábrica", "Mica Quebrada", "Extravío"])
        if st.form_submit_button("⚠️ REGISTRAR BAJA"):
            p_inf = supabase.table("productos").select("stock_actual, costo_compra").eq("codigo_barras", m_cod).execute()
            if p_inf.data:
                supabase.table("productos").update({"stock_actual": p_inf.data[0]['stock_actual'] - m_cant}).eq("codigo_barras", m_cod).execute()
                supabase.table("mermas").insert({
                    "producto_id": m_cod, "cantidad": m_cant, "motivo": m_mot,
                    "perdida_monetaria": p_inf.data[0]['costo_compra'] * m_cant
                }).execute()
                st.error("Producto descontado del inventario por merma.")
            else: st.warning("No encontrado")

# ==========================================
# 📊 MÓDULO 5: REPORTES GERENCIALES
# ==========================================
elif menu == "📊 REPORTES":
    if login():
        st.subheader("Dashboards de Rendimiento")
        v_full = load_data("ventas_cabecera")
        if not v_full.empty:
            m1, m2 = st.columns(2)
            m1.metric("Ingresos Brutos", f"S/. {v_full['total_venta'].sum():.2f}")
            m2.metric("N° Operaciones", len(v_full))
            
            fig = px.line(v_full, x="created_at", y="total_venta", title="Ventas en el Tiempo")
            st.plotly_chart(fig, use_container_width=True)
