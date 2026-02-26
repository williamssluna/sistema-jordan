import streamlit as st
from supabase import create_client
import pandas as pd
import zxingcpp
import cv2
import numpy as np
from datetime import datetime
import time

# --- 1. CONEXIÓN AL CEREBRO (SUPABASE) ---
URL_SUPABASE = "https://degzltrjrzqbahdonmmb.supabase.co"
KEY_SUPABASE = "sb_publishable_td5_vXX42LYc8PlTAbBgVg_-xCp-94r"
supabase = create_client(URL_SUPABASE, KEY_SUPABASE)

st.set_page_config(page_title="JORDAN POS SMART", layout="wide", page_icon="📱")

# --- 2. MENSAJE OFICIAL DE SOPORTE ---
ERROR_ADMIN = "🚨 Ocurrió un error. Contactar al administrador: **Williams Luna - Celular: 95555555**"

# --- 3. ESTILO VISUAL PROFESIONAL ---
st.markdown("""
    <style>
    .stApp { background-color: #f1f5f9; }
    .main-header { font-size: 26px; font-weight: 800; color: #1e3a8a; text-align: center; padding: 15px; border-bottom: 4px solid #1e3a8a; margin-bottom: 20px; }
    .css-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 5px solid #2563eb; margin-bottom: 15px; }
    .ticket-termico { background: white; color: black; font-family: 'Courier New', monospace; padding: 15px; border: 1px dashed #333; width: 100%; max-width: 320px; margin: 0 auto; line-height: 1.2; font-size: 14px; }
    .stButton>button { border-radius: 6px; font-weight: bold; height: 3.5em; width: 100%; }
    .resumen-duplicado { background-color: #fff3cd; color: #856404; padding: 15px; border-radius: 8px; border: 1px solid #ffeeba; }
    .info-caja { background-color: #e0f2fe; color: #0369a1; padding: 15px; border-radius: 8px; border: 1px solid #bae6fd; margin-bottom: 15px; font-weight: 500;}
    .metric-box { background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); text-align: center;}
    .metric-title { font-size: 14px; color: #64748b; font-weight: 600; text-transform: uppercase;}
    .metric-value { font-size: 24px; font-weight: 800; color: #0f172a;}
    .metric-green { color: #16a34a; }
    .metric-red { color: #dc2626; }
    .cierre-box { background-color: #fef2f2; border: 2px solid #fca5a5; padding: 20px; border-radius: 10px; margin-top: 20px;}
    </style>
    """, unsafe_allow_html=True)

# --- 4. MEMORIA DEL SISTEMA Y SEGURIDAD (STATE) ---
keys_to_init = {
    'carrito': [], 'last_ticket': None,
    'iny_alm_cod': "", 'iny_dev_cod': "", 'iny_merma_cod': "",
    'cam_v_key': 0, 'cam_a_key': 0, 'cam_d_key': 0, 'cam_m_key': 0,
    'admin_auth': False
}
for k, v in keys_to_init.items():
    if k not in st.session_state: st.session_state[k] = v

# --- 5. FUNCIONES DE APOYO (CÁMARA "OJO DE HALCÓN") ---
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
    except: return None

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
                    if item['id'] == code: item['cant'] += 1; exist = True
                if not exist:
                    st.session_state.carrito.append({
                        'id': code, 'nombre': p['nombre'], 
                        'precio': float(p['precio_lista']), 
                        'cant': 1, 'costo': float(p['costo_compra']),
                        'p_min': float(p['precio_minimo'])
                    })
                st.success(f"Añadido: {p['nombre']}")
                exito = True
            else: st.error("❌ Sin stock disponible.")
        else: st.warning("⚠️ Producto no encontrado.")
    except Exception as e: st.error(ERROR_ADMIN)
    return exito

# --- CABECERA ---
st.markdown('<div class="main-header">📱 ACCESORIOS JORDAN | SMART POS</div>', unsafe_allow_html=True)

# --- 6. SISTEMA DE LOGIN Y MENÚ DINÁMICO ---
st.sidebar.markdown("### 🏢 Panel de Control")

if st.session_state.admin_auth:
    menu_options = ["🛒 VENTAS (POS)", "📦 ALMACÉN PRO", "🔄 DEVOLUCIONES", "⚠️ MERMAS/DAÑOS", "📊 REPORTES (CAJA)"]
else:
    menu_options = ["🛒 VENTAS (POS)", "🔄 DEVOLUCIONES", "⚠️ MERMAS/DAÑOS"]

menu = st.sidebar.radio("SISTEMA DE GESTIÓN", menu_options)
st.sidebar.divider()

if not st.session_state.admin_auth:
    st.sidebar.markdown("#### 🔐 Acceso Privado")
    usuario = st.sidebar.text_input("Usuario")
    clave = st.sidebar.text_input("Contraseña", type="password")
    if st.sidebar.button("Entrar", use_container_width=True):
        if usuario == "admin" and clave == "123456":
            st.session_state.admin_auth = True
            st.rerun()
        else:
            st.sidebar.error("❌ Credenciales incorrectas")
else:
    st.sidebar.success("✅ Modo Administrador")
    if st.sidebar.button("🔒 Cerrar Sesión Segura", use_container_width=True):
        st.session_state.admin_auth = False
        st.rerun()

# ==========================================
# 🛒 MÓDULO 1: VENTAS (POS)
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
        st.subheader("🛍️ Carrito")
        if not st.session_state.carrito: 
            st.info("🛒 Aún no se han agregado productos al carrito.")
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
        
        # --- TICKET INTELIGENTE ---
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
# 📦 MÓDULO 2: ALMACÉN PRO (SOLO ADMIN)
# ==========================================
elif menu == "📦 ALMACÉN PRO" and st.session_state.admin_auth:
    st.subheader("Gestión de Inventario")
    t1, t2, t3, t4 = st.tabs(["➕ Ingreso", "⚙️ Configuración", "📋 Inventario", "📉 Historial Mermas"])
    
    with t1:
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        with st.expander("📷 ABRIR ESCÁNER", expanded=True):
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
                                <b>⚠️ ESTE PRODUCTO YA EXISTE</b><br>
                                <b>Nombre:</b> {p_ex['nombre']} | <b>Marca:</b> {m_nom} | <b>Categoría:</b> {c_nom}<br>
                                <b>Stock Actual:</b> {p_ex['stock_actual']} ud. | <b>Precio:</b> S/. {p_ex['precio_lista']}<br>
                                <i>👉 Ve a 'Inventario' para sumarle más cantidad.</i>
                            </div>
                            """, unsafe_allow_html=True)
                            st.session_state.cam_a_key += 1 
                        else:
                            st.session_state.iny_alm_cod = code_a 
                            st.session_state.cam_a_key += 1 
                            st.success(f"¡Código capturado con éxito: {code_a}!")
                            time.sleep(1); st.rerun() 
                    except Exception as e: st.error(ERROR_ADMIN)
                else: st.error("⚠️ La foto está muy borrosa. Intenta darle más luz.")
        
        cats = load_data("categorias")
        mars = load_data("marcas")
        
        with st.form("form_nuevo", clear_on_submit=True):
            c_cod = st.text_input("Código de Barras", value=st.session_state.iny_alm_cod)
            c_nom = st.text_input("Nombre / Descripción del Accesorio")
            
            f1, f2, f3 = st.columns(3)
            cat_list = cats['nombre'].tolist() if not cats.empty else ["Aún no hay categorías"]
            mar_list = mars['nombre'].tolist() if not mars.empty else ["Aún no hay marcas"]
            
            f_cat = f1.selectbox("Categoría", cat_list)
            f_mar = f2.selectbox("Marca", mar_list)
            f_cal = f3.selectbox("Calidad", ["Genérico", "Original", "AAA", "Alta Gama"])
            
            f4, f5, f6, f7 = st.columns(4)
            f_costo = f4.number_input("Costo Compra (S/.)", min_value=0.0, step=0.5)
            f_pmin = f6.number_input("Precio Mínimo (S/.)", min_value=0.0, step=0.5)
            f_venta = f5.number_input("Precio Venta Sugerido (S/.)", min_value=0.0, step=0.5)
            f_stock = f7.number_input("Stock Inicial", min_value=1, step=1)
            
            if st.form_submit_button("🚀 GUARDAR EN INVENTARIO", type="primary"):
                exito_guardar = False
                if c_cod and c_nom and not cats.empty and not mars.empty:
                    try:
                        check_exist = supabase.table("productos").select("codigo_barras").eq("codigo_barras", c_cod).execute()
                        if check_exist.data:
                            st.error("❌ Este código ya existe en la base de datos.")
                        else:
                            cid = int(cats[cats['nombre'] == f_cat]['id'].iloc[0])
                            mid = int(mars[mars['nombre'] == f_mar]['id'].iloc[0])
                            supabase.table("productos").insert({
                                "codigo_barras": c_cod, "nombre": c_nom, 
                                "categoria_id": cid, "marca_id": mid, "calidad": f_cal, 
                                "costo_compra": f_costo, "precio_lista": f_venta, 
                                "precio_minimo": f_pmin, "stock_actual": f_stock, "stock_inicial": f_stock
                            }).execute()
                            st.session_state.iny_alm_cod = "" 
                            exito_guardar = True
                    except Exception as e: st.error(ERROR_ADMIN)
                else: 
                    st.warning("⚠️ Debes rellenar código, nombre y tener creadas Categorías y Marcas.")
                
                if exito_guardar:
                    st.success("✅ Producto registrado exitosamente.")
                    time.sleep(1.5); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with t2:
        st.write("### Configuración del Sistema")
        c_left, c_right = st.columns(2)
        with c_left:
            st.markdown('<div class="css-card">', unsafe_allow_html=True)
            st.write("#### 📂 Categorías")
            with st.form("f_cat", clear_on_submit=True):
                new_c = st.text_input("Crear Categoría")
                if st.form_submit_button("➕ Guardar", type="primary"):
                    if new_c: 
                        try:
                            supabase.table("categorias").insert({"nombre": new_c}).execute()
                            st.success("Guardada."); time.sleep(1); st.rerun()
                        except Exception as e: st.error(ERROR_ADMIN)
            cats_df = load_data("categorias")
            if not cats_df.empty:
                del_c = st.selectbox("Eliminar Categoría", ["..."] + cats_df['nombre'].tolist())
                if st.button("🗑️ Borrar Categoría"):
                    if del_c != "...": 
                        try:
                            supabase.table("categorias").delete().eq("nombre", del_c).execute()
                            st.rerun()
                        except Exception as e: st.error(ERROR_ADMIN)
            else: st.info("📭 Sin categorías.")
            st.markdown('</div>', unsafe_allow_html=True)
            
        with c_right:
            st.markdown('<div class="css-card">', unsafe_allow_html=True)
            st.write("#### ®️ Marcas")
            with st.form("f_mar", clear_on_submit=True):
                new_m = st.text_input("Crear Marca")
                if st.form_submit_button("➕ Guardar", type="primary"):
                    if new_m: 
                        try:
                            supabase.table("marcas").insert({"nombre": new_m}).execute()
                            st.success("Guardada."); time.sleep(1); st.rerun()
                        except Exception as e: st.error(ERROR_ADMIN)
            mars_df = load_data("marcas")
            if not mars_df.empty:
                del_m = st.selectbox("Eliminar Marca", ["..."] + mars_df['nombre'].tolist())
                if st.button("🗑️ Borrar Marca"):
                    if del_m != "...": 
                        try:
                            supabase.table("marcas").delete().eq("nombre", del_m).execute()
                            st.rerun()
                        except Exception as e: st.error(ERROR_ADMIN)
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
                
                # Manejo seguro si la columna stock_inicial recién fue creada
                if 'stock_inicial' not in df.columns: df['stock_inicial'] = df['stock_actual']
                df['stock_inicial'] = df.apply(lambda row: row.get('stock_inicial') if pd.notnull(row.get('stock_inicial')) else row['stock_actual'], axis=1)

                df_show = df[['codigo_barras', 'nombre', 'Categoría', 'Marca', 'stock_inicial', 'stock_actual', 'costo_compra', 'precio_minimo', 'precio_lista']]
                df_show.columns = ['Código', 'Nombre', 'Categoría', 'Marca', 'Stock Inic.', 'Stock Act.', 'Costo (S/.)', 'P. Mín (S/.)', 'P. Venta (S/.)']
                
                st.dataframe(df_show, use_container_width=True)
                
                st.divider()
                st.write("### ⚡ Reabastecimiento Rápido")
                st.info("Suma stock rápidamente a un producto existente.")
                col_r1, col_r2 = st.columns([3, 1])
                
                prod_options = [f"{row['codigo_barras']} - {row['nombre']} (Stock Act: {row['stock_actual']})" for idx, row in df.iterrows()]
                selected_prod = col_r1.selectbox("Selecciona el producto a recargar:", ["Seleccionar..."] + prod_options)
                add_stock = col_r2.number_input("Cantidad a sumar", min_value=1, step=1)
                
                if st.button("➕ Sumar al Stock", type="primary"):
                    exito_re = False
                    if selected_prod != "Seleccionar...":
                        code_to_update = selected_prod.split(" - ")[0]
                        current_stock = int(df[df['codigo_barras'] == code_to_update]['stock_actual'].iloc[0])
                        current_initial = int(df[df['codigo_barras'] == code_to_update]['stock_inicial'].iloc[0])
                        
                        try:
                            supabase.table("productos").update({
                                "stock_actual": current_stock + add_stock, 
                                "stock_inicial": current_initial + add_stock
                            }).eq("codigo_barras", code_to_update).execute()
                            exito_re = True
                        except Exception as e: st.error(ERROR_ADMIN)
                        
                        if exito_re:
                            st.success(f"✅ Stock actualizado. Nuevo stock: {current_stock + add_stock}")
                            time.sleep(1.5); st.rerun() 
            else: 
                st.info("📭 Aún no se han registrado productos en el inventario.")
        except Exception as e: st.error(ERROR_ADMIN)
        
    with t4:
        st.write("### 📉 Historial de Mermas y Pérdidas")
        st.info("Recuento de todo el inventario dañado o extraviado y su impacto en el capital.")
        try:
            mermas_db = supabase.table("mermas").select("*, productos(nombre)").execute()
            if mermas_db.data:
                df_m = pd.DataFrame(mermas_db.data)
                df_m['Producto'] = df_m['productos'].apply(lambda x: x['nombre'] if isinstance(x, dict) else 'N/A')
                df_m['Fecha'] = pd.to_datetime(df_m['created_at']).dt.strftime('%d/%m/%Y %H:%M')
                
                df_show_m = df_m[['Fecha', 'Producto', 'cantidad', 'motivo', 'perdida_monetaria']]
                df_show_m.columns = ['Fecha', 'Producto', 'Cantidad Pérdida', 'Motivo del Daño', 'Impacto Monetario (S/.)']
                
                st.dataframe(df_show_m, use_container_width=True)
                
                total_perdida = df_m['perdida_monetaria'].sum()
                st.markdown(f"<h3 style='color:#dc2626;'>Impacto Total al Capital: S/. {total_perdida:.2f}</h3>", unsafe_allow_html=True)
            else:
                st.success("✅ ¡Excelente! Aún no se han registrado mermas o pérdidas de inventario.")
        except Exception as e:
            st.error(ERROR_ADMIN)

# ==========================================
# 🔄 MÓDULO 3: DEVOLUCIONES
# ==========================================
elif menu == "🔄 DEVOLUCIONES":
    st.subheader("Gestión de Devoluciones de Clientes")
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
                    st.success(f"✅ Ticket encontrado. Método original: {v_cab.data[0]['metodo_pago']}")
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
                            except Exception as e: st.error(ERROR_ADMIN)
                            if exito_dev: st.success("✅ Dinero descontado de caja y producto vuelto a vitrina."); time.sleep(1.5); st.rerun()
                else: st.warning("⚠️ Ticket no encontrado en el sistema.")
            except Exception as e: st.error(ERROR_ADMIN)
            
        else:
            try:
                p_db = supabase.table("productos").select("*").eq("codigo_barras", search_dev).execute()
                if p_db.data:
                    p = p_db.data[0]
                    st.markdown(f"<div class='info-caja'>📦 Producto detectado: <b>{p['nombre']}</b><br>Precio lista: S/. {p['precio_lista']}</div>", unsafe_allow_html=True)
                    
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
                                    supabase.table("devoluciones").insert({
                                        "producto_id": p['codigo_barras'],
                                        "cantidad": dev_cant,
                                        "motivo": motivo_dev,
                                        "dinero_devuelto": total_reembolso,
                                        "estado_producto": "Vuelve a tienda"
                                    }).execute()
                                    
                                    st.session_state.iny_dev_cod = ""
                                    exito_dl = True
                                except Exception as e: st.error(ERROR_ADMIN)
                            else:
                                st.warning("⚠️ Debes escribir el motivo por el cual el cliente devolvió el producto.")
                            
                            if exito_dl:
                                st.success(f"✅ Se retornaron {dev_cant} unidades a vitrina y se descontó S/. {total_reembolso} de la caja del día.")
                                time.sleep(2); st.rerun()
                else:
                    st.warning("⚠️ El código ingresado no corresponde a ningún producto.")
            except Exception as e: st.error(ERROR_ADMIN)

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
                st.markdown(f"<div class='info-caja'>🛑 <b>A PUNTO DE DAR DE BAJA:</b> {p_merma['nombre']}<br>Tienes <b>{p_merma['stock_actual']}</b> unidades en tienda.<br>Cada unidad dañada te cuesta <b>S/. {p_merma['costo_compra']}</b> de capital.</div>", unsafe_allow_html=True)
                
                with st.form("form_merma", clear_on_submit=True):
                    m_cant = st.number_input("Cantidad a descontar y botar a la basura", min_value=1, max_value=int(p_merma['stock_actual']) if p_merma['stock_actual'] > 0 else 1)
                    m_mot = st.selectbox("Motivo Exacto", ["Roto al instalar/mostrar", "Falla de Fábrica (Garantía Proveedor)", "Robo/Extravío"])
                    
                    if st.form_submit_button("⚠️ CONFIRMAR PÉRDIDA Y DESCONTAR", type="primary"):
                        exito_merma = False
                        if p_merma['stock_actual'] >= m_cant:
                            try:
                                supabase.table("productos").update({"stock_actual": p_merma['stock_actual'] - m_cant}).eq("codigo_barras", m_cod).execute()
                                supabase.table("mermas").insert({"producto_id": m_cod, "cantidad": m_cant, "motivo": m_mot, "perdida_monetaria": p_merma['costo_compra'] * m_cant}).execute()
                                st.session_state.iny_merma_cod = "" 
                                exito_merma = True
                            except Exception as e: st.error(ERROR_ADMIN)
                        else: 
                            st.error("❌ No puedes dar de baja más stock del que tienes.")
                        
                        if exito_merma:
                            st.success(f"✅ Baja exitosa. Se descontaron {m_cant} unidades de tu inventario."); time.sleep(1.5); st.rerun()
            else:
                st.warning("⚠️ Código de producto no encontrado en el sistema.")
        except Exception as e:
            st.error(ERROR_ADMIN)

# ==========================================
# 📊 MÓDULO 5: REPORTES Y CIERRE DE CAJA (SOLO ADMIN)
# ==========================================
elif menu == "📊 REPORTES (CAJA)" and st.session_state.admin_auth:
    st.subheader("Auditoría de Caja y Cierre de Turno")
    try:
        # 1. Obtener la última fecha de cierre para filtrar operaciones nuevas
        try:
            cierres_db = supabase.table("cierres_caja").select("*").order("fecha_cierre", desc=True).limit(1).execute()
            last_cierre_str = cierres_db.data[0]['fecha_cierre'] if cierres_db.data else "2000-01-01T00:00:00Z"
            last_cierre_dt = pd.to_datetime(last_cierre_str, utc=True)
            st.caption(f"⏱️ Mostrando operaciones desde el último cierre: {last_cierre_dt.strftime('%d/%m/%Y %H:%M')}")
        except:
            last_cierre_dt = pd.to_datetime("2000-01-01T00:00:00Z", utc=True)

        # 2. Extraer TODA la data y filtrarla por la fecha del último cierre
        detalles = supabase.table("ventas_detalle").select("*, productos(nombre, costo_compra), ventas_cabecera(created_at, ticket_numero)").execute()
        devs = supabase.table("devoluciones").select("*").execute()
        mermas = supabase.table("mermas").select("*").execute()
        
        total_ventas_brutas = 0.0
        total_costo_vendido = 0.0
        total_devoluciones = 0.0
        total_perdida_mermas = 0.0
        
        df_rep_filtered = pd.DataFrame()
        
        # Filtro Inteligente de Ventas
        if detalles.data:
            df_rep = pd.DataFrame(detalles.data)
            df_rep['created_dt'] = pd.to_datetime(df_rep['ventas_cabecera'].apply(lambda x: x['created_at'] if isinstance(x, dict) else '2000-01-01'), utc=True)
            df_rep_filtered = df_rep[df_rep['created_dt'] > last_cierre_dt] 
            
            if not df_rep_filtered.empty:
                df_rep_filtered['Costo Unitario'] = df_rep_filtered['productos'].apply(lambda x: float(x['costo_compra']) if isinstance(x, dict) and x.get('costo_compra') else 0.0)
                df_rep_filtered['Costo Total'] = df_rep_filtered['Costo Unitario'] * df_rep_filtered['cantidad']
                total_ventas_brutas = df_rep_filtered['subtotal'].sum()
                total_costo_vendido = df_rep_filtered['Costo Total'].sum()
            
        # Filtro Inteligente de Devoluciones
        if devs.data:
            df_devs = pd.DataFrame(devs.data)
            df_devs['created_dt'] = pd.to_datetime(df_devs['created_at'], utc=True)
            df_devs_filt = df_devs[df_devs['created_dt'] > last_cierre_dt]
            total_devoluciones = df_devs_filt['dinero_devuelto'].sum() if not df_devs_filt.empty else 0.0
            
        # Filtro Inteligente de Mermas
        if mermas.data:
            df_mer = pd.DataFrame(mermas.data)
            df_mer['created_dt'] = pd.to_datetime(df_mer['created_at'], utc=True)
            df_mer_filt = df_mer[df_mer['created_dt'] > last_cierre_dt]
            total_perdida_mermas = df_mer_filt['perdida_monetaria'].sum() if not df_mer_filt.empty else 0.0
            
        caja_neta_real = total_ventas_brutas - total_devoluciones
        ganancia_neta_real = caja_neta_real - total_costo_vendido - total_perdida_mermas
        
        # 3. Mostrar Paneles Gerenciales del Turno Actual
        st.markdown("##### 💵 Cuadre de Efectivo del Turno")
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"<div class='metric-box'><div class='metric-title'>Ventas Brutas</div><div class='metric-value'>S/. {total_ventas_brutas:.2f}</div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='metric-box'><div class='metric-title'>Dinero Devuelto</div><div class='metric-value metric-red'>- S/. {total_devoluciones:.2f}</div></div>", unsafe_allow_html=True)
        c3.markdown(f"<div class='metric-box'><div class='metric-title'>Caja Neto (Físico en tienda)</div><div class='metric-value metric-green'>S/. {caja_neta_real:.2f}</div></div>", unsafe_allow_html=True)
        
        st.write("")
        st.markdown("##### 📈 Rendimiento del Negocio (Utilidad del Turno)")
        c4, c5 = st.columns(2)
        c4.markdown(f"<div class='metric-box'><div class='metric-title'>Pérdidas por Merma</div><div class='metric-value metric-red'>- S/. {total_perdida_mermas:.2f}</div></div>", unsafe_allow_html=True)
        c5.markdown(f"<div class='metric-box'><div class='metric-title'>Utilidad Neta Pura</div><div class='metric-value metric-green'>S/. {ganancia_neta_real:.2f}</div></div>", unsafe_allow_html=True)
        
        # --- BLOQUE DE CIERRE DE CAJA ---
        st.markdown('<div class="cierre-box">', unsafe_allow_html=True)
        st.write("### 🛑 EJECUTAR CIERRE DE CAJA (FIN DE TURNO)")
        st.write("Al realizar el cierre, los paneles de arriba se reiniciarán a S/. 0.00 para iniciar un nuevo día o turno. **El inventario físico permanecerá intacto.**")
        
        with st.form("form_cierre", clear_on_submit=True):
            clave_cierre = st.text_input("Ingresa la clave de Administrador para autorizar el corte", type="password")
            if st.form_submit_button("🔒 CONFIRMAR Y CORTAR CAJA", type="primary"):
                if clave_cierre == "123456":
                    try:
                        # Guardamos los totales históricos en la tabla de cierres
                        supabase.table("cierres_caja").insert({
                            "total_ventas": float(total_ventas_brutas),
                            "utilidad": float(ganancia_neta_real),
                            "total_mermas": float(total_perdida_mermas),
                            "total_devoluciones": float(total_devoluciones)
                        }).execute()
                        st.success("✅ ¡Caja cerrada exitosamente! Los contadores de dinero se han reiniciado.")
                        time.sleep(2); st.rerun()
                    except Exception as e:
                        st.error("🚨 Error crítico. Por favor ejecuta el código SQL en Supabase primero para crear la tabla de cierres.")
                else:
                    st.error("❌ Clave incorrecta. Solo el administrador puede cerrar la caja.")
        st.markdown('</div>', unsafe_allow_html=True)

        st.divider()
        st.write("### 📝 Detalle de Ventas del Turno Actual")
        if not df_rep_filtered.empty:
            df_rep_filtered['Ticket'] = df_rep_filtered['ventas_cabecera'].apply(lambda x: x['ticket_numero'] if isinstance(x, dict) else 'N/A')
            df_rep_filtered['Fecha'] = df_rep_filtered['created_dt'].dt.strftime('%d/%m/%Y %H:%M')
            df_rep_filtered['Producto'] = df_rep_filtered['productos'].apply(lambda x: x['nombre'] if isinstance(x, dict) else 'Desconocido')
            df_rep_filtered['Ganancia Bruta'] = df_rep_filtered['subtotal'] - df_rep_filtered['Costo Total']
            
            df_show = df_rep_filtered[['Fecha', 'Ticket', 'Producto', 'cantidad', 'precio_unitario', 'subtotal', 'Ganancia Bruta']]
            df_show.columns = ['Fecha', 'Ticket', 'Producto', 'Cant.', 'Venta Unit. (S/.)', 'Ingreso Total (S/.)', 'Ganancia (S/.)']
            
            for col in ['Venta Unit. (S/.)', 'Ingreso Total (S/.)', 'Ganancia (S/.)']:
                df_show[col] = df_show[col].apply(lambda x: f"S/. {x:.2f}")
                
            st.dataframe(df_show, use_container_width=True)
        else:
            st.info("No hay operaciones registradas en el turno actual.")
            
    except Exception as e:
        st.error(f"{ERROR_ADMIN}")
