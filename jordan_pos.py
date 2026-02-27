import streamlit as st
from supabase import create_client
import pandas as pd
import zxingcpp
import cv2
import numpy as np
from datetime import datetime
import time

# ==========================================
# 1. CONEXIÓN AL CEREBRO DE BASE DE DATOS (SUPABASE)
# ==========================================
URL_SUPABASE = "https://degzltrjrzqbahdonmmb.supabase.co"
KEY_SUPABASE = "sb_publishable_td5_vXX42LYc8PlTAbBgVg_-xCp-94r"
supabase = create_client(URL_SUPABASE, KEY_SUPABASE)

st.set_page_config(page_title="JORDAN POS SMART", layout="wide", page_icon="📱")

# Mensaje oficial en caso de caídas de internet o fallos de base de datos
ERROR_ADMIN = "🚨 Ocurrió un error inesperado. Contactar al administrador: **Williams Luna - Celular: 95555555**"

# ==========================================
# 2. DISEÑO VISUAL Y ESTILOS (CSS PROFESIONAL)
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
# 3. MEMORIA DEL SISTEMA Y ESTADO (SESSION STATE)
# ==========================================
keys_to_init = {
    'carrito': [], 
    'last_ticket': None, 
    'ticket_cierre': None,
    'iny_alm_cod': "", 
    'iny_dev_cod': "", 
    'iny_merma_cod': "",
    'cam_v_key': 0, 
    'cam_a_key': 0, 
    'cam_d_key': 0, 
    'cam_m_key': 0,
    'admin_auth': True # <--- FORZADO A TRUE PARA MODO PRUEBAS
}
for key, value in keys_to_init.items():
    if key not in st.session_state: 
        st.session_state[key] = value

# ==========================================
# 4. FUNCIONES DE APOYO Y MOTOR PRINCIPAL
# ==========================================

def get_last_cierre_dt():
    try:
        cierres_db = supabase.table("cierres_caja").select("fecha_cierre").order("fecha_cierre", desc=True).limit(1).execute()
        if cierres_db.data:
            return pd.to_datetime(cierres_db.data[0]['fecha_cierre'], utc=True)
    except Exception: 
        pass
    return pd.to_datetime("2000-01-01T00:00:00Z", utc=True)

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
    except Exception: 
        return None

def load_data(table):
    try:
        res = supabase.table(table).select("*").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except Exception: return pd.DataFrame()

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
                        item['cant'] += 1
                        exist = True
                if not exist:
                    st.session_state.carrito.append({
                        'id': code, 'nombre': p['nombre'], 'precio': float(p['precio_lista']), 
                        'cant': 1, 'costo': float(p['costo_compra']), 'p_min': float(p['precio_minimo'])
                    })
                st.success(f"✅ Añadido: {p['nombre']}")
                exito = True
            else: st.error("❌ Sin stock disponible en tienda.")
        else: st.warning("⚠️ Producto no encontrado.")
    except Exception as e: st.error(ERROR_ADMIN)
    return exito

# ==========================================
# 5. ESTRUCTURA DE LA PÁGINA Y MENÚ (LIBERADO)
# ==========================================
st.markdown('<div class="main-header">📱 ACCESORIOS JORDAN | SMART POS v6.8 (Pruebas)</div>', unsafe_allow_html=True)

st.sidebar.markdown("### 🏢 Panel de Control")

# Menú liberado, muestra todas las opciones
menu_options = ["🛒 VENTAS (POS)", "📦 ALMACÉN PRO", "🔄 DEVOLUCIONES", "⚠️ MERMAS/DAÑOS", "📊 REPORTES (CAJA)"]
menu = st.sidebar.radio("SISTEMA DE GESTIÓN", menu_options)

st.sidebar.divider()
st.sidebar.info("🔓 **MODO DE PRUEBAS ACTIVADO:** Todas las contraseñas y candados han sido retirados temporalmente.")

# ==========================================
# 🛒 MÓDULO 1: VENTAS Y REGATEO
# ==========================================
if menu == "🛒 VENTAS (POS)":
    col_v1, col_v2 = st.columns([1.5, 1.4])
    
    with col_v1:
        st.subheader("🔍 Ingreso de Productos")
        with st.form("form_manual_barcode", clear_on_submit=True):
            col_mb1, col_mb2 = st.columns([3, 1])
            manual_code = col_mb1.text_input("Tipear Código Numérico")
            add_manual = col_mb2.form_submit_button("➕ Agregar")
            if add_manual and manual_code:
                if procesar_codigo_venta(manual_code):
                    time.sleep(0.5); st.rerun()

        with st.expander("📷 ABRIR ESCÁNER TÁCTIL", expanded=False):
            img = st.camera_input("Lector", key=f"scanner_venta_{st.session_state.cam_v_key}", label_visibility="hidden")
            if img:
                code = scan_pos(img)
                if code:
                    if procesar_codigo_venta(code):
                        st.session_state.cam_v_key += 1 
                        time.sleep(0.5); st.rerun()
                else: st.error("⚠️ Foto muy borrosa. Intenta darle más luz.")

        st.divider()
        search = st.text_input("Búsqueda por Nombre (Ej. Mica S23)")
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
                                st.session_state.carrito.append({
                                    'id': p['codigo_barras'], 'nombre': p['nombre'], 
                                    'precio': float(p['precio_lista']), 'cant': 1,
                                    'costo': float(p['costo_compra']), 'p_min': float(p['precio_minimo'])
                                })
                                st.rerun()
                            else: st.error("Sin stock")
                else: st.info("No se encontraron productos.")
            except Exception as e: st.error(ERROR_ADMIN)

    with col_v2:
        st.subheader("🛍️ Carrito de Compras")
        if not st.session_state.carrito: 
            st.info("🛒 Aún no se han agregado productos.")
        else:
            total_venta = 0
            for i, item in enumerate(st.session_state.carrito):
                st.write(f"**{item['cant']}x** {item['nombre']} (Mín: S/. {item['p_min']:.2f})")
                c_c1, c_c2, c_c3 = st.columns([2, 1.5, 0.7])
                nuevo_precio = c_c1.number_input("Precio final (S/.)", min_value=float(item['p_min']), value=float(item['precio']), step=1.0, key=f"precio_{i}")
                st.session_state.carrito[i]['precio'] = nuevo_precio
                subtotal = nuevo_precio * item['cant']
                c_c2.markdown(f"<div style='padding-top:30px;'><b>Sub: S/. {subtotal:.2f}</b></div>", unsafe_allow_html=True)
                if c_c3.button("❌", key=f"del_{i}"): 
                    st.session_state.carrito.pop(i)
                    st.rerun()
                total_venta += subtotal
            
            st.divider()
            st.markdown(f"<h2 style='color:#16a34a; text-align:center;'>TOTAL: S/. {total_venta:.2f}</h2>", unsafe_allow_html=True)
            pago = st.selectbox("Medio de Pago", ["Efectivo", "Yape", "Plin", "Tarjeta VISA/MC"])
            doc = st.selectbox("Comprobante a emitir", ["Ticket de Venta", "Boleta Electrónica", "Ticket Interno"])
            
            if st.button("🏁 PROCESAR PAGO", type="primary"):
                exito_pago = False
                try:
                    t_num = f"AJ-{int(time.time())}"
                    res_cab = supabase.table("ventas_cabecera").insert({"ticket_numero": t_num, "total_venta": total_venta, "metodo_pago": pago, "tipo_comprobante": doc}).execute()
                    v_id = res_cab.data[0]['id']
                    
                    for item in st.session_state.carrito:
                        supabase.table("ventas_detalle").insert({
                            "venta_id": v_id, "producto_id": item['id'], "cantidad": item['cant'], 
                            "precio_unitario": item['precio'], "subtotal": item['precio'] * item['cant']
                        }).execute()
                        stk = supabase.table("productos").select("stock_actual").eq("codigo_barras", item['id']).execute()
                        supabase.table("productos").update({"stock_actual": stk.data[0]['stock_actual'] - item['cant']}).eq("codigo_barras", item['id']).execute()
                    
                    st.session_state.last_ticket = {'num': t_num, 'items': st.session_state.carrito.copy(), 'total': total_venta, 'pago': pago, 'doc': doc}
                    st.session_state.carrito = []
                    exito_pago = True
                except Exception as e: st.error(ERROR_ADMIN)
                if exito_pago: st.rerun() 
        
        if st.session_state.last_ticket:
            with st.container():
                tk = st.session_state.last_ticket
                st.success("✅ Venta procesada correctamente.")
                ticket_html = f"""<div class="ticket-termico"><center><b>ACCESORIOS JORDAN</b></center><center>{tk['doc']}</center>--------------------------------<br>TICKET: {tk['num']}<br>FECHA: {datetime.now().strftime('%d/%m/%Y %H:%M')}<br>--------------------------------<br>"""
                
                if tk['doc'] == "Ticket Interno":
                    ticket_html += "<b>RESUMEN DE UTILIDADES:</b><br><br>"
                    total_costo = 0
                    for it in tk['items']:
                        costo_sub = it['costo'] * it['cant']
                        venta_sub = it['precio'] * it['cant']
                        total_costo += costo_sub
                        ticket_html += f"<b>{it['nombre'][:20]}</b> (x{it['cant']})<br> Costo: S/. {costo_sub:.2f} | Venta: S/. {venta_sub:.2f} <br> <span style='color:green'>Ganancia: S/. {venta_sub - costo_sub:.2f}</span><br><br>"
                    ticket_html += f"--------------------------------<br><b>VENTA TOTAL: S/. {tk['total']:.2f}</b><br>COSTO INVERSIÓN: S/. {total_costo:.2f}<br><b>UTILIDAD NETA: S/. {tk['total'] - total_costo:.2f}</b><br>MÉTODO: {tk['pago']}<br>--------------------------------<br></div>"
                else:
                    for it in tk['items']: ticket_html += f"{it['nombre'][:20]:<20} <br> {it['cant']:>2} x S/. {it['precio']:.2f} = S/. {it['precio']*it['cant']:.2f}<br><br>"
                    ticket_html += f"--------------------------------<br><b>TOTAL PAGADO: S/. {tk['total']:.2f}</b><br>MÉTODO: {tk['pago']}<br>--------------------------------<br><center>¡Gracias por su compra!</center></div>"
                st.markdown(ticket_html, unsafe_allow_html=True)

# ==========================================
# 📦 MÓDULO 2: ALMACÉN PRO
# ==========================================
elif menu == "📦 ALMACÉN PRO":
    st.subheader("Gestión de Inventario Maestro")
    t1, t2, t3, t4 = st.tabs(["➕ Ingreso Mercadería", "⚙️ Configuración", "📋 Inventario General", "📉 Mermas Históricas"])
    
    with t1:
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        with st.expander("📷 ABRIR ESCÁNER ALMACÉN", expanded=True):
            img_a = st.camera_input("Scanner Almacén", key=f"cam_almacen_{st.session_state.cam_a_key}")
            if img_a:
                code_a = scan_pos(img_a)
                if code_a: 
                    try:
                        check = supabase.table("productos").select("*, categorias(nombre), marcas(nombre)").eq("codigo_barras", code_a).execute()
                        if check.data:
                            p_ex = check.data[0]
                            c_nom = p_ex['categorias']['nombre'] if p_ex['categorias'] else 'N/A'
                            m_nom = p_ex['marcas']['nombre'] if p_ex['marcas'] else 'N/A'
                            st.markdown(f"""
                            <div class="resumen-duplicado">
                                <b>⚠️ ESTE PRODUCTO YA EXISTE EN EL SISTEMA</b><br>
                                <b>Nombre:</b> {p_ex['nombre']} | <b>Marca:</b> {m_nom} | <b>Categoría:</b> {c_nom}<br>
                                <b>Stock Actual:</b> {p_ex['stock_actual']} ud. | <b>Precio:</b> S/. {p_ex['precio_lista']}<br>
                                <i>👉 Ve a la pestaña 'Inventario General' para sumarle más cantidad.</i>
                            </div>
                            """, unsafe_allow_html=True)
                            st.session_state.cam_a_key += 1 
                        else:
                            st.session_state.iny_alm_cod = code_a 
                            st.session_state.cam_a_key += 1 
                            st.success(f"¡Código nuevo capturado con éxito: {code_a}!")
                            time.sleep(1); st.rerun() 
                    except Exception as e: st.error(ERROR_ADMIN)
                else: st.error("⚠️ La foto está muy borrosa. Intenta darle más luz.")
        
        cats = load_data("categorias")
        mars = load_data("marcas")
        
        with st.form("form_nuevo", clear_on_submit=True):
            c_cod = st.text_input("Código de Barras", value=st.session_state.iny_alm_cod)
            c_nom = st.text_input("Nombre / Descripción del Accesorio")
            f1, f2, f3 = st.columns(3)
            f_cat = f1.selectbox("Categoría", cats['nombre'].tolist() if not cats.empty else ["Vacío"])
            f_mar = f2.selectbox("Marca", mars['nombre'].tolist() if not mars.empty else ["Vacío"])
            f_cal = f3.selectbox("Calidad", ["Genérico", "Original", "AAA", "Alta Gama"])
            f4, f5, f6, f7 = st.columns(4)
            f_costo = f4.number_input("Costo Compra Unidad (S/.)", min_value=0.0, step=0.5)
            f_pmin = f6.number_input("Precio Mínimo Permitido (S/.)", min_value=0.0, step=0.5)
            f_venta = f5.number_input("Precio Venta Sugerido (S/.)", min_value=0.0, step=0.5)
            f_stock = f7.number_input("Stock Inicial Ingresado", min_value=1, step=1)
            
            if st.form_submit_button("🚀 GUARDAR EN INVENTARIO", type="primary"):
                exito_guardar = False
                if c_cod and c_nom and not cats.empty and not mars.empty:
                    try:
                        check_exist = supabase.table("productos").select("codigo_barras").eq("codigo_barras", c_cod).execute()
                        if check_exist.data:
                            st.error("❌ Este código ya existe en la base de datos.")
                        else:
                            cid, mid = int(cats[cats['nombre'] == f_cat]['id'].iloc[0]), int(mars[mars['nombre'] == f_mar]['id'].iloc[0])
                            supabase.table("productos").insert({
                                "codigo_barras": c_cod, "nombre": c_nom, "categoria_id": cid, "marca_id": mid, "calidad": f_cal, 
                                "costo_compra": f_costo, "precio_lista": f_venta, "precio_minimo": f_pmin, 
                                "stock_actual": f_stock, "stock_inicial": f_stock
                            }).execute()
                            st.session_state.iny_alm_cod = "" 
                            exito_guardar = True
                    except Exception as e: st.error("Error al guardar. Asegúrate de rellenar todo correctamente.")
                else: st.warning("⚠️ Debes rellenar código, nombre y tener creadas Categorías y Marcas.")
                if exito_guardar: st.success("✅ Producto registrado exitosamente."); time.sleep(1.5); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    with t2:
        st.write("### Creación de Categorías y Marcas")
        c_left, c_right = st.columns(2)
        with c_left:
            st.markdown('<div class="css-card">', unsafe_allow_html=True)
            st.write("#### 📂 Categorías")
            with st.form("f_cat", clear_on_submit=True):
                new_c = st.text_input("Crear Categoría")
                if st.form_submit_button("➕ Guardar Categoría", type="primary"):
                    if new_c: 
                        try: supabase.table("categorias").insert({"nombre": new_c}).execute(); st.success("Guardada."); time.sleep(1); st.rerun()
                        except: st.error(ERROR_ADMIN)
            cats_df = load_data("categorias")
            if not cats_df.empty:
                del_c = st.selectbox("Eliminar Categoría", ["..."] + cats_df['nombre'].tolist())
                if st.button("🗑️ Borrar Categoría", key="btn_del_cat"):
                    if del_c != "...": 
                        try: supabase.table("categorias").delete().eq("nombre", del_c).execute(); st.rerun()
                        except: st.error(ERROR_ADMIN)
            else: st.info("📭 Sin categorías.")
            st.markdown('</div>', unsafe_allow_html=True)
            
        with c_right:
            st.markdown('<div class="css-card">', unsafe_allow_html=True)
            st.write("#### ®️ Marcas")
            with st.form("f_mar", clear_on_submit=True):
                new_m = st.text_input("Crear Marca")
                if st.form_submit_button("➕ Guardar Marca", type="primary"):
                    if new_m: 
                        try: supabase.table("marcas").insert({"nombre": new_m}).execute(); st.success("Guardada."); time.sleep(1); st.rerun()
                        except: st.error(ERROR_ADMIN)
            mars_df = load_data("marcas")
            if not mars_df.empty:
                del_m = st.selectbox("Eliminar Marca", ["..."] + mars_df['nombre'].tolist())
                if st.button("🗑️ Borrar Marca", key="btn_del_mar"):
                    if del_m != "...": 
                        try: supabase.table("marcas").delete().eq("nombre", del_m).execute(); st.rerun()
                        except: st.error(ERROR_ADMIN)
            else: st.info("📭 Sin marcas.")
            st.markdown('</div>', unsafe_allow_html=True)

    with t3:
        st.write("### 📋 Inventario General")
        try:
            prods = supabase.table("productos").select("*, categorias(nombre), marcas(nombre)").execute()
            if prods.data: 
                df = pd.DataFrame(prods.data)
                df['Categoría'] = df['categorias'].apply(lambda x: x['nombre'] if isinstance(x, dict) else 'N/A')
                df['Marca'] = df['marcas'].apply(lambda x: x['nombre'] if isinstance(x, dict) else 'N/A')
                df['stock_inicial'] = df.apply(lambda row: row.get('stock_inicial') if pd.notnull(row.get('stock_inicial')) else row['stock_actual'], axis=1)
                
                df_show = df[['codigo_barras', 'nombre', 'Categoría', 'Marca', 'stock_inicial', 'stock_actual', 'costo_compra', 'precio_minimo', 'precio_lista']]
                df_show.columns = ['Código', 'Nombre', 'Categoría', 'Marca', 'Stock Inic.', 'Stock Act.', 'Costo (S/.)', 'P. Mín (S/.)', 'P. Venta (S/.)']
                st.dataframe(df_show, use_container_width=True)
                
                st.divider()
                st.write("### ⚡ Reabastecimiento Rápido (Suma de Stock)")
                col_r1, col_r2 = st.columns([3, 1])
                prod_options = [f"{row['codigo_barras']} - {row['nombre']} (Stock Act: {row['stock_actual']})" for idx, row in df.iterrows()]
                selected_prod = col_r1.selectbox("Selecciona el producto que acaba de llegar:", ["Seleccionar..."] + prod_options)
                add_stock = col_r2.number_input("Cantidad a sumar a vitrina", min_value=1, step=1)
                
                if st.button("➕ Sumar al Stock Físico", type="primary"):
                    exito_re = False
                    if selected_prod != "Seleccionar...":
                        cod_up = selected_prod.split(" - ")[0]
                        c_stk = int(df[df['codigo_barras'] == cod_up]['stock_actual'].iloc[0])
                        c_ini = int(df[df['codigo_barras'] == cod_up]['stock_inicial'].iloc[0])
                        try:
                            supabase.table("productos").update({"stock_actual": c_stk + add_stock, "stock_inicial": c_ini + add_stock}).eq("codigo_barras", cod_up).execute()
                            exito_re = True
                        except: st.error(ERROR_ADMIN)
                        if exito_re: st.success(f"✅ Stock actualizado. Nuevo stock total: {c_stk + add_stock}"); time.sleep(1.5); st.rerun() 
            else: st.info("📭 Aún no se han registrado productos en el inventario.")
        except: pass
        
    with t4:
        st.write("### 📉 Historial de Mermas del Turno Actual")
        st.info("Recuento de inventario dañado desde el último corte de caja y su impacto en capital.")
        try:
            lc_dt = get_last_cierre_dt()
            mermas_db = supabase.table("mermas").select("*, productos(nombre)").execute()
            if mermas_db.data:
                df_m = pd.DataFrame(mermas_db.data)
                df_m['created_dt'] = pd.to_datetime(df_m['created_at'], utc=True)
                df_m_filt = df_m[df_m['created_dt'] > lc_dt] 
                
                if not df_m_filt.empty:
                    df_m_filt['Producto'] = df_m_filt['productos'].apply(lambda x: x['nombre'] if isinstance(x, dict) else 'N/A')
                    df_m_filt['Fecha'] = df_m_filt['created_dt'].dt.strftime('%d/%m/%Y %H:%M')
                    df_show_m = df_m_filt[['Fecha', 'Producto', 'cantidad', 'motivo', 'perdida_monetaria']]
                    df_show_m.columns = ['Fecha', 'Producto', 'Cantidad Pérdida', 'Motivo del Daño', 'Impacto Monetario (S/.)']
                    
                    st.dataframe(df_show_m, use_container_width=True)
                    st.markdown(f"<h3 style='color:#dc2626;'>Impacto Total al Capital hoy: S/. {df_m_filt['perdida_monetaria'].sum():.2f}</h3>", unsafe_allow_html=True)
                else: st.success("✅ Historial visual limpio. No hay mermas registradas en este turno.")
            else: st.success("✅ Historial completamente limpio en la base de datos.")
        except: pass

# ==========================================
# 🔄 MÓDULO 3: DEVOLUCIONES
# ==========================================
elif menu == "🔄 DEVOLUCIONES":
    st.subheader("Gestión de Devoluciones y Reembolsos")
    
    with st.expander("📷 ESCANEAR PRODUCTO A DEVOLVER", expanded=False):
        img_dev = st.camera_input("Scanner Devolución", key=f"cam_dev_{st.session_state.cam_d_key}")
        if img_dev:
            code_dev = scan_pos(img_dev)
            if code_dev:
                st.session_state.iny_dev_cod = code_dev 
                st.session_state.cam_d_key += 1 
                st.rerun()
            else: st.warning("⚠️ No se detectó código. Intenta enfocar mejor.")

    search_dev = st.text_input("Ingresa el Número de Ticket (AJ-...) o el Código de Barras del producto", value=st.session_state.iny_dev_cod)
    
    if search_dev:
        if "AJ-" in search_dev.upper():
            try:
                v_cab = supabase.table("ventas_cabecera").select("*").eq("ticket_numero", search_dev.upper()).execute()
                if v_cab.data:
                    st.success(f"✅ Ticket encontrado. Método original de pago: {v_cab.data[0]['metodo_pago']}")
                    v_det = supabase.table("ventas_detalle").select("*, productos(nombre)").eq("venta_id", v_cab.data[0]['id']).execute()
                    
                    for d in v_det.data:
                        col_d1, col_d2 = st.columns([3, 1])
                        col_d1.write(f"**{d['productos']['nombre']}** - Compró: {d['cantidad']} ud.")
                        
                        if col_d2.button("Ejecutar Devolución", key=f"dev_{d['id']}"):
                            exito_dev = False
                            try:
                                p_s = supabase.table("productos").select("stock_actual").eq("codigo_barras", d['producto_id']).execute()
                                supabase.table("productos").update({"stock_actual": p_s.data[0]['stock_actual'] + d['cantidad']}).eq("codigo_barras", d['producto_id']).execute()
                                supabase.table("devoluciones").insert({"producto_id": d['producto_id'], "cantidad": d['cantidad'], "motivo": "Devolución por Ticket", "dinero_devuelto": d['subtotal'], "estado_producto": "Vuelve a tienda"}).execute()
                                st.session_state.iny_dev_cod = "" 
                                exito_dev = True
                            except: st.error(ERROR_ADMIN)
                            if exito_dev: st.success("✅ Dinero descontado de caja y producto vuelto a vitrina."); time.sleep(1.5); st.rerun()
                else: st.warning("⚠️ Ticket no encontrado en el sistema histórico.")
            except: st.error(ERROR_ADMIN)
            
        else:
            try:
                p_db = supabase.table("productos").select("*").eq("codigo_barras", search_dev).execute()
                if p_db.data:
                    p = p_db.data[0]
                    st.markdown(f"<div class='info-caja'>📦 Producto detectado: <b>{p['nombre']}</b><br>Precio lista general: S/. {p['precio_lista']}</div>", unsafe_allow_html=True)
                    
                    with st.form("form_dev_libre", clear_on_submit=True):
                        col_f1, col_f2 = st.columns(2)
                        dev_cant = col_f1.number_input("Cantidad a regresar a vitrina", min_value=1, step=1)
                        dinero_reembolsado = col_f2.number_input("Dinero devuelto al cliente por UND. (S/.)", value=float(p['precio_lista']), min_value=0.0, step=0.5)
                        motivo_dev = st.text_input("Motivo de la devolución del cliente (Obligatorio)")
                        
                        if st.form_submit_button("🔁 EJECUTAR DEVOLUCIÓN (DESCONTAR DE CAJA)", type="primary"):
                            exito_dl = False
                            if motivo_dev:
                                try:
                                    new_stock = p['stock_actual'] + dev_cant
                                    supabase.table("productos").update({"stock_actual": new_stock}).eq("codigo_barras", p['codigo_barras']).execute()
                                    total_reembolso = dev_cant * dinero_reembolsado
                                    supabase.table("devoluciones").insert({"producto_id": p['codigo_barras'], "cantidad": dev_cant, "motivo": motivo_dev, "dinero_devuelto": total_reembolso, "estado_producto": "Vuelve a tienda"}).execute()
                                    st.session_state.iny_dev_cod = ""
                                    exito_dl = True
                                except: st.error(ERROR_ADMIN)
                            else: st.warning("⚠️ Debes escribir el motivo por el cual el cliente devolvió el producto.")
                            if exito_dl: st.success(f"✅ Se retornaron {dev_cant} unidades a vitrina y se descontó S/. {total_reembolso} de la caja del día."); time.sleep(2); st.rerun()
                else: st.warning("⚠️ El código ingresado no corresponde a ningún producto registrado.")
            except: st.error(ERROR_ADMIN)

    st.divider()
    st.write("### 📉 Historial de Devoluciones del Turno")
    try:
        lc_dt = get_last_cierre_dt()
        devs_db = supabase.table("devoluciones").select("*, productos(nombre)").execute()
        if devs_db.data:
            df_dev = pd.DataFrame(devs_db.data)
            df_dev['created_dt'] = pd.to_datetime(df_dev['created_at'], utc=True)
            df_dev_filt = df_dev[df_dev['created_dt'] > lc_dt]
            if not df_dev_filt.empty:
                df_dev_filt['Producto'] = df_dev_filt['productos'].apply(lambda x: x['nombre'] if isinstance(x, dict) else 'N/A')
                df_dev_filt['Fecha'] = df_dev_filt['created_dt'].dt.strftime('%d/%m/%Y %H:%M')
                df_show_dev = df_dev_filt[['Fecha', 'Producto', 'cantidad', 'motivo', 'dinero_devuelto']]
                df_show_dev.columns = ['Fecha', 'Producto', 'Cant. Regresada', 'Motivo', 'Reembolso (S/.)']
                st.dataframe(df_show_dev, use_container_width=True)
            else: st.info("✅ No hay devoluciones en este turno.")
        else: st.info("✅ No hay devoluciones en este turno.")
    except: pass

# ==========================================
# ⚠️ MÓDULO 4: MERMAS Y DAÑOS
# ==========================================
elif menu == "⚠️ MERMAS/DAÑOS":
    st.subheader("Dar de Baja Productos Dañados")
    
    with st.expander("📷 ABRIR ESCÁNER", expanded=True):
        img_m = st.camera_input("Scanner Merma", key=f"cam_merma_{st.session_state.cam_m_key}")
        if img_m:
            code_m = scan_pos(img_m)
            if code_m:
                st.session_state.iny_merma_cod = code_m 
                st.session_state.cam_m_key += 1 
                st.rerun()
            else: st.warning("⚠️ No se detectó código. Intenta enfocar mejor.")

    m_cod = st.text_input("Código de Barras del Producto Dañado", value=st.session_state.iny_merma_cod)
    
    if m_cod:
        try:
            p_inf = supabase.table("productos").select("stock_actual, costo_compra, nombre").eq("codigo_barras", m_cod).execute()
            if p_inf.data:
                p_merma = p_inf.data[0]
                st.markdown(f"<div class='info-caja'>🛑 <b>A PUNTO DE DAR DE BAJA:</b> {p_merma['nombre']}<br>Stock actual: <b>{p_merma['stock_actual']}</b> ud.<br>Pérdida por unidad: <b>S/. {p_merma['costo_compra']}</b></div>", unsafe_allow_html=True)
                with st.form("form_merma", clear_on_submit=True):
                    m_cant = st.number_input("Cantidad a botar a la basura", min_value=1, max_value=int(p_merma['stock_actual']) if p_merma['stock_actual'] > 0 else 1)
                    m_mot = st.selectbox("Motivo Exacto", ["Roto al instalar/mostrar", "Falla de Fábrica (Garantía Proveedor)", "Robo/Extravío"])
                    if st.form_submit_button("⚠️ CONFIRMAR PÉRDIDA", type="primary"):
                        exito_merma = False
                        if p_merma['stock_actual'] >= m_cant:
                            try:
                                supabase.table("productos").update({"stock_actual": p_merma['stock_actual'] - m_cant}).eq("codigo_barras", m_cod).execute()
                                supabase.table("mermas").insert({"producto_id": m_cod, "cantidad": m_cant, "motivo": m_mot, "perdida_monetaria": p_merma['costo_compra'] * m_cant}).execute()
                                st.session_state.iny_merma_cod = "" 
                                exito_merma = True
                            except: st.error(ERROR_ADMIN)
                        else: st.error("❌ No tienes stock suficiente.")
                        if exito_merma: st.success("✅ Baja exitosa."); time.sleep(1.5); st.rerun()
            else: st.warning("⚠️ Código no encontrado.")
        except: st.error(ERROR_ADMIN)

    st.divider()
    st.write("### 📉 Historial de Mermas del Turno")
    try:
        lc_dt = get_last_cierre_dt()
        mermas_db = supabase.table("mermas").select("*, productos(nombre)").execute()
        if mermas_db.data:
            df_m = pd.DataFrame(mermas_db.data)
            df_m['created_dt'] = pd.to_datetime(df_m['created_at'], utc=True)
            df_m_filt = df_m[df_m['created_dt'] > lc_dt] 
            if not df_m_filt.empty:
                df_m_filt['Producto'] = df_m_filt['productos'].apply(lambda x: x['nombre'] if isinstance(x, dict) else 'N/A')
                df_m_filt['Fecha'] = df_m_filt['created_dt'].dt.strftime('%d/%m/%Y %H:%M')
                df_show_m = df_m_filt[['Fecha', 'Producto', 'cantidad', 'motivo', 'perdida_monetaria']]
                df_show_m.columns = ['Fecha', 'Producto', 'Cantidad Pérdida', 'Motivo del Daño', 'Impacto Monetario (S/.)']
                st.dataframe(df_show_m, use_container_width=True)
            else: st.info("✅ No hay mermas en este turno.")
        else: st.info("✅ No hay mermas en este turno.")
    except: pass

# ==========================================
# 📊 MÓDULO 5: REPORTES Y CIERRE DE CAJA (Z) 
# ==========================================
elif menu == "📊 REPORTES (CAJA)":
    st.subheader("Auditoría Contable de Turno")
    
    # VISTA 1: TICKET Z (CIERRE FINALIZADO)
    if st.session_state.ticket_cierre:
        tk = st.session_state.ticket_cierre
        st.success("✅ Caja cerrada. Todos los historiales de reportes se han reiniciado a cero.")
        
        ticket_z_html = f"""
        <div class="ticket-termico">
            <center><b>ACCESORIOS JORDAN</b></center>
            <center><b>REPORTE Z (FIN DE TURNO)</b></center>
            --------------------------------<br>
            FECHA CIERRE: {tk['fecha']}<br>
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
            <center>Stock físico e inicial actualizado.</center>
        </div>
        """
        st.markdown(ticket_z_html, unsafe_allow_html=True)
        
        if st.button("🧹 Iniciar Nuevo Turno (Pantalla Limpia)", type="primary"):
            st.session_state.ticket_cierre = None
            st.rerun()

    # VISTA 2: DASHBOARD EN TIEMPO REAL Y BOTÓN DE CIERRE (MODO LIBRE)
    else:
        try:
            last_cierre_dt = get_last_cierre_dt()
            st.caption(f"⏱️ Monitoreando ventas desde el último corte: {last_cierre_dt.strftime('%d/%m/%Y %H:%M')}")

            detalles = supabase.table("ventas_detalle").select("*, productos(nombre, costo_compra), ventas_cabecera(created_at, ticket_numero)").execute()
            devs = supabase.table("devoluciones").select("*, productos(costo_compra)").execute()
            mermas = supabase.table("mermas").select("*").execute()
            
            total_ventas_brutas, total_costo_vendido = 0.0, 0.0
            total_devoluciones, costo_recuperado_devs = 0.0, 0.0
            total_perdida_mermas = 0.0
            cant_vendida, cant_devuelta, cant_merma = 0, 0, 0
            
            df_rep_filtered = pd.DataFrame()
            
            if detalles.data:
                df_rep = pd.DataFrame(detalles.data)
                df_rep['created_dt'] = pd.to_datetime(df_rep['ventas_cabecera'].apply(lambda x: x['created_at'] if isinstance(x, dict) else '2000-01-01'), utc=True)
                df_rep_filtered = df_rep[df_rep['created_dt'] > last_cierre_dt] 
                
                if not df_rep_filtered.empty:
                    df_rep_filtered['Costo Unitario'] = df_rep_filtered['productos'].apply(lambda x: float(x['costo_compra']) if isinstance(x, dict) and x.get('costo_compra') else 0.0)
                    df_rep_filtered['Costo Total'] = df_rep_filtered['Costo Unitario'] * df_rep_filtered['cantidad']
                    total_ventas_brutas = df_rep_filtered['subtotal'].sum()
                    total_costo_vendido = df_rep_filtered['Costo Total'].sum()
                    cant_vendida = int(df_rep_filtered['cantidad'].sum())
            
            if devs.data:
                df_devs = pd.DataFrame(devs.data)
                df_devs['created_dt'] = pd.to_datetime(df_devs['created_at'], utc=True)
                df_devs_filt = df_devs[df_devs['created_dt'] > last_cierre_dt]
                
                if not df_devs_filt.empty:
                    df_devs_filt['Costo Unitario Dev'] = df_devs_filt['productos'].apply(lambda x: float(x['costo_compra']) if isinstance(x, dict) and x.get('costo_compra') else 0.0)
                    costo_recuperado_devs = (df_devs_filt['Costo Unitario Dev'] * df_devs_filt['cantidad']).sum()
                    total_devoluciones = df_devs_filt['dinero_devuelto'].sum()
                    cant_devuelta = int(df_devs_filt['cantidad'].sum())
            
            if mermas.data:
                df_mer = pd.DataFrame(mermas.data)
                df_mer['created_dt'] = pd.to_datetime(df_mer['created_at'], utc=True)
                df_mer_filt = df_mer[df_mer['created_dt'] > last_cierre_dt]
                if not df_mer_filt.empty:
                    total_perdida_mermas = df_mer_filt['perdida_monetaria'].sum()
                    cant_merma = int(df_mer_filt['cantidad'].sum())
            
            capital_invertido_real = total_costo_vendido - costo_recuperado_devs
            caja_neta_real = total_ventas_brutas - total_devoluciones
            ganancia_neta_real = caja_neta_real - capital_invertido_real - total_perdida_mermas
            
            st.markdown("##### 💵 Balance de Caja (Dinero Físico)")
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"<div class='metric-box'><div class='metric-title'>Ventas Brutas</div><div class='metric-value'>S/. {total_ventas_brutas:.2f}</div></div>", unsafe_allow_html=True)
            c2.markdown(f"<div class='metric-box'><div class='metric-title'>Dinero Devuelto</div><div class='metric-value metric-red'>- S/. {total_devoluciones:.2f}</div></div>", unsafe_allow_html=True)
            c3.markdown(f"<div class='metric-box'><div class='metric-title'>CAJA NETA</div><div class='metric-value metric-green'>S/. {caja_neta_real:.2f}</div></div>", unsafe_allow_html=True)
            
            st.write("")
            st.markdown("##### 📈 Rendimiento Operativo (Utilidad)")
            c4, c5, c6 = st.columns(3)
            c4.markdown(f"<div class='metric-box'><div class='metric-title'>Capital Invertido (Costo)</div><div class='metric-value metric-orange'>S/. {capital_invertido_real:.2f}</div></div>", unsafe_allow_html=True)
            c5.markdown(f"<div class='metric-box'><div class='metric-title'>Mermas (Pérdidas)</div><div class='metric-value metric-red'>- S/. {total_perdida_mermas:.2f}</div></div>", unsafe_allow_html=True)
            c6.markdown(f"<div class='metric-box'><div class='metric-title'>UTILIDAD NETA PURA</div><div class='metric-value metric-green'>S/. {ganancia_neta_real:.2f}</div></div>", unsafe_allow_html=True)
            
            st.markdown('<div class="cierre-box">', unsafe_allow_html=True)
            st.write("### 🛑 CORTAR CAJA Y GENERAR TICKET Z")
            st.write("Esta acción generará tu reporte final, guardará el historial contable, y **convertirá tu Stock Actual en tu nuevo Stock Inicial** para el próximo turno.")
            
            with st.form("form_cierre", clear_on_submit=True):
                st.write("*(Modo pruebas: No se requiere contraseña para cerrar caja)*")
                if st.form_submit_button("🔒 APROBAR CIERRE DE CAJA DIRECTO", type="primary"):
                    try:
                        # 1. Guardar Corte en Base de Datos
                        supabase.table("cierres_caja").insert({
                            "total_ventas": float(total_ventas_brutas),
                            "utilidad": float(ganancia_neta_real),
                            "total_mermas": float(total_perdida_mermas),
                            "total_devoluciones": float(total_devoluciones)
                        }).execute()
                        
                        # 2. LA MAGIA: Igualar Stock Inicial al Stock Actual
                        prods_res = supabase.table("productos").select("codigo_barras, stock_actual").execute()
                        if prods_res.data:
                            for prod in prods_res.data:
                                supabase.table("productos").update({"stock_inicial": prod['stock_actual']}).eq("codigo_barras", prod['codigo_barras']).execute()
                        
                        # 3. Preparar Ticket Visual
                        st.session_state.ticket_cierre = {
                            'fecha': datetime.now().strftime('%d/%m/%Y %H:%M'),
                            'cant_vendida': cant_vendida,
                            'tot_ventas': total_ventas_brutas,
                            'capital_inv': capital_invertido_real,
                            'cant_devuelta': cant_devuelta,
                            'tot_dev': total_devoluciones,
                            'cant_merma': cant_merma,
                            'tot_merma': total_perdida_mermas,
                            'caja_neta': caja_neta_real,
                            'utilidad': ganancia_neta_real
                        }
                        st.rerun() 
                    except Exception as e: st.error("🚨 Error crítico de conexión al ejecutar el cierre.")
            st.markdown('</div>', unsafe_allow_html=True)

            st.divider()
            st.write("### 📝 Detalle Ítem por Ítem (Solo Turno Actual)")
            if not df_rep_filtered.empty:
                df_rep_filtered['Ticket'] = df_rep_filtered['ventas_cabecera'].apply(lambda x: x['ticket_numero'] if isinstance(x, dict) else 'N/A')
                df_rep_filtered['Fecha'] = df_rep_filtered['created_dt'].dt.strftime('%d/%m/%Y %H:%M')
                df_rep_filtered['Producto'] = df_rep_filtered['productos'].apply(lambda x: x['nombre'] if isinstance(x, dict) else 'Desconocido')
                df_rep_filtered['Ganancia Bruta'] = df_rep_filtered['subtotal'] - df_rep_filtered['Costo Total']
                
                df_show = df_rep_filtered[['Fecha', 'Ticket', 'Producto', 'cantidad', 'precio_unitario', 'subtotal', 'Ganancia Bruta']]
                df_show.columns = ['Fecha', 'Ticket', 'Producto', 'Cant.', 'Venta Unit. (S/.)', 'Ingreso Total (S/.)', 'Ganancia (S/.)']
                for col in ['Venta Unit. (S/.)', 'Ingreso Total (S/.)', 'Ganancia (S/.)']: df_show[col] = df_show[col].apply(lambda x: f"S/. {x:.2f}")
                st.dataframe(df_show, use_container_width=True)
            else: st.info("No hay ventas en este turno.")
        except Exception as e: st.error(ERROR_ADMIN)
