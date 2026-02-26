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

# --- 2. ESTILO VISUAL PROFESIONAL (Optimizado para POS) ---
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
    .stButton>button:active { transform: scale(0.98); }
    </style>
    """, unsafe_allow_html=True)

# --- 3. MEMORIA DEL SISTEMA (STATE) ---
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'last_ticket' not in st.session_state: st.session_state.last_ticket = None
if 'scan_agregar' not in st.session_state: st.session_state.scan_agregar = ""
if 'scan_merma' not in st.session_state: st.session_state.scan_merma = ""
if 'scan_dev' not in st.session_state: st.session_state.scan_dev = ""

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
    except: return pd.DataFrame()

# --- CABECERA ---
st.markdown('<div class="main-header">📱 ACCESORIOS JORDAN | SMART POS v4.4</div>', unsafe_allow_html=True)

menu = st.sidebar.radio("SISTEMA DE GESTIÓN", ["🛒 VENTAS (POS)", "📦 ALMACÉN PRO", "🔄 DEVOLUCIONES", "⚠️ MERMAS/DAÑOS", "📊 REPORTES"])

# ==========================================
# 🛒 MÓDULO 1: VENTAS (CARRITO Y TICKET)
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
                        else: st.error("Sin stock disponible.")

        search = st.text_input("Búsqueda Manual (Ej. Mica S23)")
        if search:
            res_s = supabase.table("productos").select("*, marcas(nombre)").ilike("nombre", f"%{search}%").execute()
            if res_s.data:
                for p in res_s.data:
                    c_p1, c_p2, c_p3 = st.columns([3, 1, 1])
                    c_p1.write(f"**{p['nombre']}** ({p['marcas']['nombre'] if p['marcas'] else 'Genérico'})")
                    c_p2.write(f"S/. {p['precio_lista']}")
                    if c_p3.button("➕", key=f"add_{p['codigo_barras']}"):
                        if p['stock_actual'] > 0:
                            st.session_state.carrito.append({'id': p['codigo_barras'], 'nombre': p['nombre'], 'precio': float(p['precio_lista']), 'cant': 1})
                            st.rerun()
                        else: st.error("Sin stock")

    with col_v2:
        st.subheader("🛍️ Carrito Actual")
        if not st.session_state.carrito: st.info("El carrito está vacío.")
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
                t_num = f"AJ-{int(time.time())}"
                res_cab = supabase.table("ventas_cabecera").insert({"ticket_numero": t_num, "total_venta": total, "metodo_pago": pago, "tipo_comprobante": doc}).execute()
                v_id = res_cab.data[0]['id']
                for item in st.session_state.carrito:
                    supabase.table("ventas_detalle").insert({"venta_id": v_id, "producto_id": item['id'], "cantidad": item['cant'], "precio_unitario": item['precio'], "subtotal": item['precio'] * item['cant']}).execute()
                    stk = supabase.table("productos").select("stock_actual").eq("codigo_barras", item['id']).execute()
                    supabase.table("productos").update({"stock_actual": stk.data[0]['stock_actual'] - item['cant']}).eq("codigo_barras", item['id']).execute()
                
                st.session_state.last_ticket = {'num': t_num, 'items': st.session_state.carrito.copy(), 'total': total, 'pago': pago, 'doc': doc}
                st.session_state.carrito = []
                st.rerun() # Eliminados los globos para mayor velocidad
        
        # REPORTE DE VENTA DIRECTO Y LIMPIO
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
        with st.expander("📷 ABRIR ESCÁNER", expanded=True):
            img_a = st.camera_input("Scanner Almacén", key="scanner_almacen")
            if img_a:
                code_a = scan_pos(img_a)
                if code_a: st.session_state.scan_agregar = code_a; st.success(f"¡Código capturado: {code_a}!"); time.sleep(0.5); st.rerun()
        
        cats = load_data("categorias")
        mars = load_data("marcas")
        
        with st.form("form_nuevo"):
            c_cod = st.text_input("Código de Barras", value=st.session_state.scan_agregar)
            c_nom = st.text_input("Nombre / Descripción del Accesorio")
            
            f1, f2, f3 = st.columns(3)
            cat_list = cats['nombre'].tolist() if not cats.empty else ["Ve a Configurar Listas primero"]
            mar_list = mars['nombre'].tolist() if not mars.empty else ["Ve a Configurar Listas primero"]
            
            f_cat = f1.selectbox("Categoría", cat_list)
            f_mar = f2.selectbox("Marca", mar_list)
            f_cal = f3.selectbox("Calidad", ["Genérico", "Original", "AAA", "Alta Gama"])
            
            f4, f5, f6 = st.columns(3)
            f_costo = f4.number_input("Costo de Compra (S/.)", min_value=0.0, step=0.5)
            f_venta = f5.number_input("Precio Venta Público (S/.)", min_value=0.0, step=0.5)
            f_stock = f6.number_input("Stock Inicial", min_value=1)
            
            if st.form_submit_button("🚀 GUARDAR EN INVENTARIO"):
                if c_cod and c_nom and not cats.empty and not mars.empty:
                    cid = int(cats[cats['nombre'] == f_cat]['id'].values[0])
                    mid = int(mars[mars['nombre'] == f_mar]['id'].values[0])
                    supabase.table("productos").insert({"codigo_barras": c_cod, "nombre": c_nom, "categoria_id": cid, "marca_id": mid, "calidad": f_cal, "costo_compra": f_costo, "precio_lista": f_venta, "precio_minimo": f_costo, "stock_actual": f_stock}).execute()
                    st.session_state.scan_agregar = ""; st.success("Producto registrado exitosamente."); time.sleep(1); st.rerun()
                else: st.error("Asegúrate de haber creado al menos una Categoría y una Marca.")
        st.markdown('</div>', unsafe_allow_html=True)

    with t2:
        st.write("### Personaliza tu Sistema")
        c_left, c_right = st.columns(2)
        with c_left:
            st.markdown('<div class="css-card">', unsafe_allow_html=True)
            st.write("#### 📂 Categorías")
            new_c = st.text_input("Crear Categoría (Ej: Micas, Cases)")
            if st.button("➕ Guardar Categoría", type="primary"):
                if new_c: supabase.table("categorias").insert({"nombre": new_c}).execute(); st.rerun()
            cats_df = load_data("categorias")
            if not cats_df.empty:
                del_c = st.selectbox("Eliminar Categoría", ["..."] + cats_df['nombre'].tolist())
                if st.button("🗑️ Borrar Categoría"):
                    if del_c != "...": supabase.table("categorias").delete().eq("nombre", del_c).execute(); st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
            
        with c_right:
            st.markdown('<div class="css-card">', unsafe_allow_html=True)
            st.write("#### ®️ Marcas")
            new_m = st.text_input("Crear Marca (Ej: Genérico, Samsung)")
            if st.button("➕ Guardar Marca", type="primary"):
                if new_m: supabase.table("marcas").insert({"nombre": new_m}).execute(); st.rerun()
            mars_df = load_data("marcas")
            if not mars_df.empty:
                del_m = st.selectbox("Eliminar Marca", ["..."] + mars_df['nombre'].tolist())
                if st.button("🗑️ Borrar Marca"):
                    if del_m != "...": supabase.table("marcas").delete().eq("nombre", del_m).execute(); st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    with t3:
        prods = load_data("productos")
        if not prods.empty: st.dataframe(prods, use_container_width=True)

# ==========================================
# 🔄 MÓDULO 3: DEVOLUCIONES (AHORA CON ESCÁNER)
# ==========================================
elif menu == "🔄 DEVOLUCIONES":
    st.subheader("Gestión de Devoluciones de Clientes")
    st.info("Escanea el código de barras del ticket o escríbelo manualmente.")
    
    with st.expander("📷 ESCANEAR TICKET O PRODUCTO", expanded=False):
        img_dev = st.camera_input("Scanner Devolución", key="scanner_dev")
        if img_dev:
            code_dev = scan_pos(img_dev)
            if code_dev:
                st.session_state.scan_dev = code_dev
                st.success(f"Capturado: {code_dev}"); time.sleep(0.5); st.rerun()

    tick = st.text_input("Ingresa el Número de Ticket (Ej. AJ-17000000)", value=st.session_state.scan_dev)
    if tick:
        v_cab = supabase.table("ventas_cabecera").select("*").eq("ticket_numero", tick).execute()
        if v_cab.data:
            st.success(f"Ticket encontrado. Método original: {v_cab.data[0]['metodo_pago']}")
            v_det = supabase.table("ventas_detalle").select("*, productos(nombre)").eq("venta_id", v_cab.data[0]['id']).execute()
            for d in v_det.data:
                col_d1, col_d2 = st.columns([3, 1])
                col_d1.write(f"**{d['productos']['nombre']}** - Compró: {d['cantidad']} ud.")
                if col_d2.button("Ejecutar Devolución", key=f"dev_{d['id']}"):
                    p_s = supabase.table("productos").select("stock_actual").eq("codigo_barras", d['producto_id']).execute()
                    supabase.table("productos").update({"stock_actual": p_s.data[0]['stock_actual'] + d['cantidad']}).eq("codigo_barras", d['producto_id']).execute()
                    supabase.table("devoluciones").insert({"producto_id": d['producto_id'], "cantidad": d['cantidad'], "motivo": "Devolución", "dinero_devuelto": d['subtotal'], "estado_producto": "Vuelve a tienda"}).execute()
                    st.session_state.scan_dev = ""
                    st.success("Dinero descontado contablemente y producto vuelto a vitrina."); time.sleep(1.5); st.rerun()
        else:
            st.warning("Ticket o producto no encontrado en el sistema de ventas.")

# ==========================================
# ⚠️ MÓDULO 4: MERMAS Y DAÑOS (AHORA CON ESCÁNER)
# ==========================================
elif menu == "⚠️ MERMAS/DAÑOS":
    st.subheader("Dar de Baja Productos Dañados")
    st.info("Escanea el accesorio que se dañó para descontarlo de tu inventario real.")
    
    with st.expander("📷 ABRIR ESCÁNER", expanded=True):
        img_m = st.camera_input("Scanner Merma", key="scanner_merma")
        if img_m:
            code
