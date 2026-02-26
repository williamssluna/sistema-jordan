import streamlit as st
from supabase import create_client
import pandas as pd
import zxingcpp
import cv2
import numpy as np
from datetime import datetime
import time
import plotly.express as px

# --- 1. CONEXIÓN AL CEREBRO (SUPABASE) ---
URL_SUPABASE = "https://degzltrjrzqbahdonmmb.supabase.co"
KEY_SUPABASE = "sb_publishable_td5_vXX42LYc8PlTAbBgVg_-xCp-94r"
supabase = create_client(URL_SUPABASE, KEY_SUPABASE)

st.set_page_config(page_title="JORDAN POS SMART", layout="wide", page_icon="📱")

# --- 2. ESTILO VISUAL PROFESIONAL ---
st.markdown("""
    <style>
    .stApp { background-color: #f1f5f9; }
    .main-header { font-size: 28px; font-weight: 800; color: #1e3a8a; text-align: center; padding: 15px; border-bottom: 4px solid #1e3a8a; margin-bottom: 20px; }
    .css-card { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-left: 6px solid #2563eb; margin-bottom: 15px; }
    .ticket-termico { 
        background: white; color: black; font-family: 'Courier New', monospace; 
        padding: 15px; border: 1px dashed #333; width: 280px; margin: 0 auto; line-height: 1.1; font-size: 13px;
    }
    .stButton>button { border-radius: 8px; font-weight: 700; height: 3.5em; width: 100%; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. MEMORIA DEL SISTEMA (STATE) ---
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'last_ticket' not in st.session_state: st.session_state.last_ticket = None
if 'admin_auth' not in st.session_state: st.session_state.admin_auth = False
if 'scan_agregar' not in st.session_state: st.session_state.scan_agregar = ""

# --- 4. FUNCIONES DE APOYO ---
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
    except:
        return pd.DataFrame()

# --- CABECERA ---
st.markdown('<div class="main-header">📱 ACCESORIOS JORDAN | SMART POS v4.1</div>', unsafe_allow_html=True)

menu = st.sidebar.radio("SISTEMA DE GESTIÓN", ["🛒 VENTAS (POS)", "📦 ALMACÉN PRO", "🔄 DEVOLUCIONES", "⚠️ MERMAS/DAÑOS", "📊 REPORTES"])

# ==========================================
# 🛒 MÓDULO 1: VENTAS (CARRITO + TICKET)
# ==========================================
if menu == "🛒 VENTAS (POS)":
    col_v1, col_v2 = st.columns([1.8, 1.2])
    with col_v1:
        st.subheader("🔍 Buscador de Productos")
        with st.expander("📷 SCANNER (Lector de Barras)", expanded=True):
            img = st.camera_input("Lector", key="scanner_venta")
            if img:
                code = scan_pos(img)
                if code:
                    prod_db = supabase.table("productos").select("*").eq("codigo_barras", code).execute()
                    if prod_db.data:
                        p = prod_db.data[0]
                        exist = False
                        for item in st.session_state.carrito:
                            if item['id'] == code:
                                item['cant'] += 1
                                exist = True
                        if not exist:
                            st.session_state.carrito.append({'id': code, 'nombre': p['nombre'], 'precio': float(p['precio_lista']), 'cant': 1})
                        st.success(f"Añadido: {p['nombre']}")
                        time.sleep(0.5); st.rerun()

        search = st.text_input("Escribe nombre, marca o modelo...")
        if search:
            res_s = supabase.table("productos").select("*, marcas(nombre)").ilike("nombre", f"%{search}%").execute()
            if res_s.data:
                for p in res_s.data:
                    c_p1, c_p2, c_p3 = st.columns([3, 1, 1])
                    c_p1.write(f"**{p['nombre']}** ({p['marcas']['nombre']})")
                    c_p2.write(f"S/. {p['precio_lista']}")
                    if c_p3.button("➕", key=f"add_{p['codigo_barras']}"):
                        st.session_state.carrito.append({'id': p['codigo_barras'], 'nombre': p['nombre'], 'precio': float(p['precio_lista']), 'cant': 1})
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
                    st.session_state.carrito.pop(i); st.rerun()
                total += item['precio'] * item['cant']
            
            st.divider()
            st.markdown(f"## TOTAL: S/. {total:.2f}")
            pago = st.selectbox("Medio de Pago", ["Efectivo", "Yape", "Plin", "Tarjeta"])
            doc = st.selectbox("Comprobante", ["Ticket Interno", "Boleta Electrónica"])
            
            if st.button("🏁 CONFIRMAR VENTA", type="primary"):
                t_num = f"AJ-{int(time.time())}"
                res_cab = supabase.table("ventas_cabecera").insert({
                    "ticket_numero": t_num, "total_venta": total, "metodo_pago": pago, "tipo_comprobante": doc
                }).execute()
                v_id = res_cab.data[0]['id']
                for item in st.session_state.carrito:
                    supabase.table("ventas_detalle").insert({"venta_id": v_id, "producto_id": item['id'], "cantidad": item['cant'], "precio_unitario": item['precio'], "subtotal": item['precio'] * item['cant']}).execute()
                    stk = supabase.table("productos").select("stock_actual").eq("codigo_barras", item['id']).execute()
                    supabase.table("productos").update({"stock_actual": stk.data[0]['stock_actual'] - item['cant']}).eq("codigo_barras", item['id']).execute()
                st.session_state.last_ticket = {'num': t_num, 'items': st.session_state.carrito.copy(), 'total': total, 'pago': pago}
                st.session_state.carrito = []
                st.balloons(); st.rerun()

        if st.session_state.last_ticket:
            with st.expander("🖨️ TICKET TÉRMICO", expanded=True):
                tk = st.session_state.last_ticket
                st.markdown(f"""<div class="ticket-termico"><b>ACCESORIOS JORDAN</b><br>----------------------------<br>TICKET: {tk['num']}<br>PRODUCTOS:<br>""", unsafe_allow_html=True)
                for it in tk['items']: st.write(f"{it['nombre'][:18]:<18} {it['cant']:>2} {it['precio']*it['cant']:>7.2f}")
                st.markdown(f"----------------------------<br><b>TOTAL: S/. {tk['total']:.2f}</b><br>----------------------------</div>", unsafe_allow_html=True)

# ==========================================
# 📦 MÓDULO 2: ALMACÉN PRO (CORREGIDO)
# ==========================================
elif menu == "📦 ALMACÉN PRO":
    st.subheader("Gestión Central de Inventario")
    t1, t2, t3 = st.tabs(["📋 Catálogo Completo", "➕ Nuevo Ingreso", "⚙️ Categorías y Marcas"])
    
    with t1:
        prods = load_data("productos")
        if not prods.empty: st.dataframe(prods, use_container_width=True)
            
    with t2:
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        # --- CÁMARA PARA AGREGAR PRODUCTO (CORRECCIÓN) ---
        with st.expander("📷 ACTIVAR CÁMARA PARA ESCANEAR CÓDIGO", expanded=True):
            img_a = st.camera_input("Scanner Almacén", key="scanner_almacen")
            if img_a:
                code_a = scan_pos(img_a)
                if code_a:
                    st.session_state.scan_agregar = code_a
                    st.success(f"¡Código capturado: {code_a}!")
        
        cats = load_data("categorias")
        mars = load_data("marcas")
        
        with st.form("form_nuevo"):
            c_cod = st.text_input("Código de Barras", value=st.session_state.scan_agregar)
            c_nom = st.text_input("Nombre / Modelo del Accesorio")
            f1, f2, f3 = st.columns(3)
            f_cat = f1.selectbox("Categoría", cats['nombre'].tolist()) if not cats.empty else ""
            f_mar = f2.selectbox("Marca", mars['nombre'].tolist()) if not mars.empty else ""
            f_cal = f3.selectbox("Calidad", ["Genérico", "Original", "AAA", "Premium"])
            
            f4, f5, f6 = st.columns(3)
            f_costo = f4.number_input("Costo Compra (S/.)", min_value=0.0)
            f_venta = f5.number_input("Precio Venta (S/.)", min_value=0.0)
            f_stock = f6.number_input("Stock Inicial", min_value=0)
            
            if st.form_submit_button("🚀 REGISTRAR PRODUCTO"):
                if c_cod and c_nom:
                    cid = int(cats[cats['nombre'] == f_cat]['id'].values[0])
                    mid = int(mars[mars['nombre'] == f_mar]['id'].values[0])
                    supabase.table("productos").insert({"codigo_barras": c_cod, "nombre": c_nom, "categoria_id": cid, "marca_id": mid, "calidad": f_cal, "costo_compra": f_costo, "precio_lista": f_venta, "precio_minimo": f_costo, "stock_actual": f_stock}).execute()
                    st.session_state.scan_agregar = ""
                    st.success("Registrado correctamente."); time.sleep(1); st.rerun()
                else: st.error("Faltan datos obligatorios.")
        st.markdown('</div>', unsafe_allow_html=True)

    with t3:
        st.subheader("Gestionar Listas Desplegables")
        col_cat, col_mar = st.columns(2)
        with col_cat:
            st.write("### Categorías")
            new_cat = st.text_input("Nueva Categoría (Ej: Micas de Gel)")
            if st.button("Añadir Categoría"):
                if new_cat:
                    supabase.table("categorias").insert({"nombre": new_cat}).execute()
                    st.success(f"Categoría '{new_cat}' añadida."); time.sleep(1); st.rerun()
        with col_mar:
            st.write("### Marcas")
            new_mar = st.text_input("Nueva Marca (Ej: Baseus)")
            if st.button("Añadir Marca"):
                if new_mar:
                    supabase.table("marcas").insert({"nombre": new_mar}).execute()
                    st.success(f"Marca '{new_mar}' añadida."); time.sleep(1); st.rerun()

# ==========================================
# 🔄 MÓDULO 3: DEVOLUCIONES
# ==========================================
elif menu == "🔄 DEVOLUCIONES":
    st.subheader("Registro de Devoluciones")
    tick = st.text_input("Número de Ticket (Ej. AJ-17000000)")
    if tick:
        v_cab = supabase.table("ventas_cabecera").select("*").eq("ticket_numero", tick).execute()
        if v_cab.data:
            v_id = v_cab.data[0]['id']
            v_det = supabase.table("ventas_detalle").select("*, productos(nombre)").eq("venta_id", v_id).execute()
            for d in v_det.data:
                col_d1, col_d2 = st.columns([3, 1])
                col_d1.write(f"Item: {d['productos']['nombre']} (Cant: {d['cantidad']})")
                if col_d2.button("Procesar Devolución", key=f"dev_{d['id']}"):
                    p_s = supabase.table("productos").select("stock_actual").eq("codigo_barras", d['producto_id']).execute()
                    supabase.table("productos").update({"stock_actual": p_s.data[0]['stock_actual'] + d['cantidad']}).eq("codigo_barras", d['producto_id']).execute()
                    supabase.table("devoluciones").insert({"producto_id": d['producto_id'], "cantidad": d['cantidad'], "motivo": "Devolución Cliente", "dinero_devuelto": d['subtotal'], "estado_producto": "Vuelve a tienda"}).execute()
                    st.success("Inventario restaurado."); time.sleep(1); st.rerun()

# ==========================================
# ⚠️ MÓDULO 4: MERMAS
# ==========================================
elif menu == "⚠️ MERMAS/DAÑOS":
    st.subheader("Baja de Productos (Dañados)")
    with st.form("form_merma"):
        m_cod = st.text_input("Código de Barras")
        m_cant = st.number_input("Cantidad dañada", min_value=1)
        m_mot = st.selectbox("Motivo", ["Roto en Tienda", "Falla de Fábrica", "Extravío"])
        if st.form_submit_button("⚠️ REGISTRAR BAJA"):
            p_inf = supabase.table("productos").select("stock_actual, costo_compra").eq("codigo_barras", m_cod).execute()
            if p_inf.data:
                supabase.table("productos").update({"stock_actual": p_inf.data[0]['stock_actual'] - m_cant}).eq("codigo_barras", m_cod).execute()
                supabase.table("mermas").insert({"producto_id": m_cod, "cantidad": m_cant, "motivo": m_mot, "perdida_monetaria": p_inf.data[0]['costo_compra'] * m_cant}).execute()
                st.error("Descontado por daño."); time.sleep(1); st.rerun()

# ==========================================
# 📊 MÓDULO 5: REPORTES
# ==========================================
elif menu == "📊 REPORTES":
    st.subheader("Análisis de Negocio")
    v_full = load_data("ventas_cabecera")
    if not v_full.empty:
        m1, m2 = st.columns(2)
        m1.metric("Ventas Totales (Bruto)", f"S/. {v_full['total_venta'].sum():.2f}")
        m2.metric("N° Operaciones", len(v_full))
        # Corrección de fecha para el reporte
        if 'created_at' in v_full.columns:
            v_full['fecha'] = pd.to_datetime(v_full['created_at']).dt.date
            fig = px.line(v_full.groupby('fecha')['total_venta'].sum().reset_index(), x="fecha", y="total_venta", title="Ventas por Fecha")
            st.plotly_chart(fig, use_container_width=True)
