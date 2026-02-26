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

# --- 2. MENSAJE OFICIAL DE SOPORTE ---
ERROR_ADMIN = "🚨 Ocurrió un error inesperado. Por favor, contactar con el administrador: **Williams Luna - Celular: 95555555**"

# --- 3. ESTILO VISUAL PROFESIONAL ---
st.markdown("""
    <style>
    .stApp { background-color: #f1f5f9; }
    .main-header { font-size: 26px; font-weight: 800; color: #1e3a8a; text-align: center; padding: 15px; border-bottom: 4px solid #1e3a8a; margin-bottom: 20px; }
    .css-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 5px solid #2563eb; margin-bottom: 15px; }
    .ticket-termico { 
        background: white; color: black; font-family: 'Courier New', monospace; 
        padding: 15px; border: 1px dashed #333; width: 100%; max-width: 300px; margin: 0 auto; line-height: 1.2; font-size: 14px;
    }
    .stButton>button { border-radius: 6px; font-weight: bold; height: 3.5em; width: 100%; }
    </style>
    """, unsafe_allow_html=True)

# --- 4. MEMORIA DEL SISTEMA (STATE) ---
# Inicializamos las llaves para inyección directa de texto
keys_to_init = ['carrito', 'last_ticket', 'alm_cod', 'alm_nom', 'cat_nom', 'mar_nom', 'dev_cod', 'merma_cod']
for k in keys_to_init:
    if k not in st.session_state:
        st.session_state[k] = [] if k == 'carrito' else "" if 'cod' in k or 'nom' in k else None

# --- 5. FUNCIONES DE APOYO ---
def scan_pos(image):
    if not image: return None
    try:
        file_bytes = np.asarray(bytearray(image.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, 1)
        res = zxingcpp.read_barcodes(img)
        return res[0].text if res else None
    except:
        return None

def load_data(table):
    try:
        res = supabase.table(table).select("*").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except:
        return pd.DataFrame() 

# --- CABECERA ---
st.markdown('<div class="main-header">📱 ACCESORIOS JORDAN | SMART POS v4.7</div>', unsafe_allow_html=True)

menu = st.sidebar.radio("SISTEMA DE GESTIÓN", ["🛒 VENTAS (POS)", "📦 ALMACÉN PRO", "🔄 DEVOLUCIONES", "⚠️ MERMAS/DAÑOS", "📊 REPORTES"])

# ==========================================
# 🛒 MÓDULO 1: VENTAS (POS)
# ==========================================
if menu == "🛒 VENTAS (POS)":
    col_v1, col_v2 = st.columns([1.5, 1.2])
    with col_v1:
        st.subheader("🔍 Escáner de Productos")
        with st.expander("📷 ABRIR ESCÁNER", expanded=True):
            img = st.camera_input("Lector", key="scanner_venta", label_visibility="hidden")
            if img:
                code = scan_pos(img)
                if code:
                    try:
                        prod_db = supabase.table("productos").select("*").eq("codigo_barras", code).execute()
                        if prod_db.data:
                            p = prod_db.data[0]
                            if p['stock_actual'] > 0:
                                exist = False
                                for item in st.session_state.carrito:
                                    if item['id'] == code: item['cant'] += 1; exist = True
                                if not exist:
                                    st.session_state.carrito.append({'id': code, 'nombre': p['nombre'], 'precio': float(p['precio_lista']), 'cant': 1})
                                st.success(f"Añadido: {p['nombre']}")
                                time.sleep(0.5); st.rerun()
                            else: st.error("❌ Sin stock disponible.")
                        else: st.warning("⚠️ Producto no encontrado en el sistema.")
                    except: st.error(ERROR_ADMIN)

        search = st.text_input("Búsqueda Manual (Ej. Mica S23)")
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
                                st.session_state.carrito.append({'id': p['codigo_barras'], 'nombre': p['nombre'], 'precio': float(p['precio_lista']), 'cant': 1})
                                st.rerun()
                            else: st.error("Sin stock")
                else: st.info("No se encontraron productos con ese nombre.")
            except: st.error(ERROR_ADMIN)

    with col_v2:
        st.subheader("🛍️ Carrito Actual")
        if not st.session_state.carrito: 
            st.info("🛒 Aún no se han agregado productos al carrito.")
        else:
            total = 0
            for i, item in enumerate(st.session_state.carrito):
                c_c1, c_c2, c_c3 = st.columns([3, 1, 0.7])
                c_c1.write(f"**{item['cant']}x** {item['nombre']}")
                c_c2.write(f"S/. {item['precio']*item['cant']:.2f}")
                if c_c3.button("❌", key=f"del_{i}"): st.session_state.carrito.pop(i); st.rerun()
                total += item['precio'] * item['cant']
            
            st.divider()
            st.markdown(f"<h2 style='color:#16a34a; text-align:center;'>TOTAL: S/. {total:.2f}</h2>", unsafe_allow_html=True)
            pago = st.selectbox("Medio de Pago", ["Efectivo", "Yape", "Plin", "Tarjeta VISA/MC"])
            doc = st.selectbox("Comprobante", ["Ticket Interno", "Boleta Electrónica"])
            
            if st.button("🏁 PROCESAR PAGO", type="primary"):
                try:
                    t_num = f"AJ-{int(time.time())}"
                    res_cab = supabase.table("ventas_cabecera").insert({"ticket_numero": t_num, "total_venta": total, "metodo_pago": pago, "tipo_comprobante": doc}).execute()
                    v_id = res_cab.data[0]['id']
                    
                    for item in st.session_state.carrito:
                        supabase.table("ventas_detalle").insert({"venta_id": v_id, "producto_id": item['id'], "cantidad": item['cant'], "precio_unitario": item['precio'], "subtotal": item['precio'] * item['cant']}).execute()
                        stk = supabase.table("productos").select("stock_actual").eq("codigo_barras", item['id']).execute()
                        supabase.table("productos").update({"stock_actual": stk.data[0]['stock_actual'] - item['cant']}).eq("codigo_barras", item['id']).execute()
                    
                    st.session_state.last_ticket = {'num': t_num, 'items': st.session_state.carrito.copy(), 'total': total, 'pago': pago, 'doc': doc}
                    st.session_state.carrito = []
                    st.rerun()
                except: st.error(ERROR_ADMIN)
        
        if st.session_state.last_ticket:
            with st.container():
                tk = st.session_state.last_ticket
                st.success("✅ Venta procesada correctamente.")
                st.markdown(f"""
                <div class="ticket-termico">
                    <center><b>ACCESORIOS JORDAN</b></center>
                    <center>{tk['doc']}</center>
                    --------------------------------<br>
                    TICKET: {tk['num']}<br>
                    FECHA: {datetime.now().strftime('%d/%m/%Y %H:%M')}<br>
                    --------------------------------<br>
                """, unsafe_allow_html=True)
                for it in tk['items']:
                    st.write(f"{it['nombre'][:20]:<20} <br> {it['cant']:>2} x {it['precio']:.2f} = {it['precio']*it['cant']:>6.2f}", unsafe_allow_html=True)
                st.markdown(f"""
                    --------------------------------<br>
                    <b>TOTAL PAGADO: S/. {tk['total']:.2f}</b><br>
                    MÉTODO: {tk['pago']}<br>
                    --------------------------------<br>
                    <center>¡Gracias por su compra!</center>
                </div>
                """, unsafe_allow_html=True)

# ==========================================
# 📦 MÓDULO 2: ALMACÉN PRO
# ==========================================
elif menu == "📦 ALMACÉN PRO":
    st.subheader("Gestión de Inventario")
    t1, t2, t3 = st.tabs(["➕ Ingresar Mercadería", "⚙️ Configurar Listas", "📋 Inventario Actual"])
    
    with t1:
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        # --- CÁMARA INYECTA DIRECTO A LA LLAVE 'alm_cod' ---
        with st.expander("📷 ABRIR ESCÁNER", expanded=True):
            img_a = st.camera_input("Scanner Almacén", key="scanner_almacen")
            if img_a:
                code_a = scan_pos(img_a)
                if code_a: 
                    st.session_state.alm_cod = code_a 
                    st.success(f"¡Código capturado: {code_a}!")
                    time.sleep(0.5); st.rerun()
        
        cats = load_data("categorias")
        mars = load_data("marcas")
        
        # ELIMINAMOS EL st.form AQUÍ PARA EVITAR EL BLOQUEO
        c_cod = st.text_input("Código de Barras", key="alm_cod")
        c_nom = st.text_input("Nombre / Descripción del Accesorio", key="alm_nom")
        
        f1, f2, f3 = st.columns(3)
        cat_list = cats['nombre'].tolist() if not cats.empty else ["Aún no hay categorías"]
        mar_list = mars['nombre'].tolist() if not mars.empty else ["Aún no
