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
ERROR_ADMIN = "🚨 Ocurrió un error. Contactar al administrador: **Williams Luna - Celular: 95555555**"

# --- 3. ESTILO VISUAL PROFESIONAL ---
st.markdown("""
    <style>
    .stApp { background-color: #f1f5f9; }
    .main-header { font-size: 26px; font-weight: 800; color: #1e3a8a; text-align: center; padding: 15px; border-bottom: 4px solid #1e3a8a; margin-bottom: 20px; }
    .css-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 5px solid #2563eb; margin-bottom: 15px; }
    .ticket-termico { background: white; color: black; font-family: 'Courier New', monospace; padding: 15px; border: 1px dashed #333; width: 100%; max-width: 300px; margin: 0 auto; line-height: 1.2; font-size: 14px; }
    .stButton>button { border-radius: 6px; font-weight: bold; height: 3.5em; width: 100%; }
    .resumen-duplicado { background-color: #fff3cd; color: #856404; padding: 15px; border-radius: 8px; border: 1px solid #ffeeba; }
    </style>
    """, unsafe_allow_html=True)

# --- 4. MEMORIA DEL SISTEMA (STATE) ---
# Separamos las variables inyectadas de las llaves (keys) de los widgets para evitar el error rojo
keys_to_init = {
    'carrito': [], 'last_ticket': None,
    'iny_alm_cod': "", 'iny_dev_cod': "", 'iny_merma_cod': "",
    'cam_v_key': 0, 'cam_a_key': 0, 'cam_d_key': 0, 'cam_m_key': 0
}
for k, v in keys_to_init.items():
    if k not in st.session_state: st.session_state[k] = v

# --- 5. FUNCIONES DE APOYO (CÁMARA "OJO DE HALCÓN") ---
def scan_pos(image):
    if not image: return None
    try:
        file_bytes = np.asarray(bytearray(image.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, 1)
        
        # Arsenal de procesamiento de imagen
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enh = clahe.apply(gray)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        scale_down = cv2.resize(gray, None, fx=0.6, fy=0.6, interpolation=cv2.INTER_AREA)
        scale_up = cv2.resize(gray, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
        
        # Prueba 6 versiones de la imagen con 3 rotaciones = 18 intentos agresivos
        variantes = [img, gray, enh, thresh, scale_down, scale_up]
        for var in variantes:
            for rot in [None, cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_90_COUNTERCLOCKWISE]:
                test_img = cv2.rotate(var, rot) if rot else var
                res = zxingcpp.read_barcodes(test_img)
                if res: return res[0].text
        return None
    except:
        return None

def load_data(table):
    try:
        res = supabase.table(table).select("*").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except: return pd.DataFrame()

# --- CABECERA ---
st.markdown('<div class="main-header">📱 ACCESORIOS JORDAN | SMART POS v5.2</div>', unsafe_allow_html=True)

menu = st.sidebar.radio("SISTEMA DE GESTIÓN", ["🛒 VENTAS (POS)", "📦 ALMACÉN PRO", "🔄 DEVOLUCIONES", "⚠️ MERMAS/DAÑOS", "📊 REPORTES"])

# ==========================================
# 🛒 MÓDULO 1: VENTAS (POS)
# ==========================================
if menu == "🛒 VENTAS (POS)":
    col_v1, col_v2 = st.columns([1.5, 1.2])
    with col_v1:
        st.subheader("🔍 Escáner de Productos")
        with st.expander("📷 ABRIR ESCÁNER", expanded=True):
            img = st.camera_input("Lector", key=f"scanner_venta_{st.session_state.cam_v_key}", label_visibility="hidden")
            if img:
                code = scan_pos(img)
                if code:
                    exito_cam = False
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
                                st.session_state.cam_v_key += 1 
                                exito_cam = True
                            else: st.error("❌ Sin stock disponible.")
                        else: st.warning("⚠️ Producto no encontrado en el sistema.")
                    except Exception as e: st.error(ERROR_ADMIN)
                    
                    if exito_cam: time.sleep(0.5); st.rerun()
                else:
                    st.error("⚠️ Foto muy borrosa o mal enfocada. Intenta darle más luz o acércate.")

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
            except Exception as e: st.error(ERROR_ADMIN)

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
                exito_pago = False
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
                    exito_pago = True
                except Exception as e: st.error(ERROR_ADMIN)
                
                if exito_pago: st.rerun() 
        
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
    t1, t2, t3 = st.tabs(["➕ Ingresar Mercadería", "⚙️ Configurar Listas", "📋 Inventario y Reabastecimiento"])
    
    with t1:
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        with st.expander("📷 ABRIR ESCÁNER", expanded=True):
            img_a = st.camera_input("Scanner Almacén", key=f"cam_almacen_{st.session_state.cam_a_key}")
            if img_a:
                code_a = scan_pos(img_a)
                if code_a: 
                    try:
                        # Verificación de Duplicados al instante
                        check = supabase.table("productos").select("*, categorias(nombre), marcas(nombre)").eq("codigo_barras", code_a).execute()
                        if check.data:
                            p_ex = check.data[0]
                            c_nom = p_ex['categorias']['nombre'] if p_ex['categorias'] else 'N/A'
                            m_nom = p_ex['marcas']['nombre'] if p_ex['marcas'] else 'N/A'
                            st.markdown(f"""
                            <div class="resumen-duplicado">
                                <b>⚠️ ESTE PRODUCTO YA EXISTE</b><br>
                                <b>Nombre:</b> {p_ex['nombre']} | <b>Marca:</b> {m_nom} | <b>Categoría:</b> {c_nom}<br>
                                <b>Stock:</b> {p_ex['stock_actual']} ud. | <b>Precio:</b> S/. {p_ex['precio_lista']}<br>
                                <i>👉 Ve a 'Inventario y Reabastecimiento' para sumarle más cantidad.</i>
                            </div>
                            """, unsafe_allow_html=True)
                            st.session_state.cam_a_key += 1 
                        else:
                            st.session_state.iny_alm_cod = code_a # Inyección limpia
                            st.session_state.cam_a_key += 1 
                            st.success(f"¡Código capturado con éxito: {code_a}!")
                            time.sleep(1); st.rerun() 
                    except Exception as e: st.error(ERROR_ADMIN)
                else:
                    st.error("⚠️ La foto está muy borrosa. Intenta darle más luz o enfocar mejor.")
        
        cats = load_data("categorias")
        mars = load_data("marcas")
        
        with st.form("form_nuevo", clear_on_submit=True):
            # Usamos "value" alimentado por la inyección. SIN "key" rígido para evitar el error rojo.
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
            f_venta = f5.number_input("Precio Venta (S/.)", min_value=0.0, step=0.5)
            f_pmin = f6.number_input("Precio Mínimo (S/.)", min_value=0.0, step=0.5)
            f_stock = f7.number_input("Stock Inicial", min_value=1, step=1)
            
            if st.form_submit_button("🚀 GUARDAR EN INVENTARIO", type="primary"):
                exito_guardar = False
                if c_cod and c_nom and not cats.empty and not mars.empty:
                    try:
                        check_exist = supabase.table("productos").select("codigo_barras").eq("codigo_barras", c_cod).execute()
                        if check_exist.data:
                            st.error("❌ Este código de barras ya existe en la base de datos.")
                        else:
                            cid = int(cats[cats['nombre'] == f_cat]['id'].iloc[0])
                            mid = int(mars[mars['nombre'] == f_mar]['id'].iloc[0])
                            supabase.table("productos").insert({
                                "codigo_barras": c_cod, "nombre": c_nom, 
                                "categoria_id": cid, "marca_id": mid, "calidad": f_cal, 
                                "costo_compra": f_costo, "precio_lista": f_venta, 
                                "precio_minimo": f_pmin, "stock_actual": f_stock
                            }).execute()
                            
                            st.session_state.iny_alm_cod = "" # Limpiamos memoria
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
                df_show = df[['codigo_barras', 'nombre', 'Categoría', 'Marca', 'calidad', 'stock_actual', 'precio_lista', 'precio_minimo']]
                st.dataframe(df_show, use_container_width=True)
                
                st.divider()
                st.write("### ⚡ Reabastecimiento Rápido")
                st.info("Suma stock rápidamente a un producto existente.")
                col_r1, col_r2 = st.columns([3, 1])
                
                prod_options = [f"{row['codigo_barras']} - {row['nombre']} (Stock: {row['stock_actual']})" for idx, row in df.iterrows()]
                selected_prod = col_r1.selectbox("Selecciona el producto a recargar:", ["Seleccionar..."] + prod_options)
                add_stock = col_r2.number_input("Cantidad a sumar", min_value=1, step=1)
                
                if st.button("➕ Sumar al Stock", type="primary"):
                    exito_re = False
                    if selected_prod != "Seleccionar...":
                        code_to_update = selected_prod.split(" - ")[0]
                        current_stock = int(df[df['codigo_barras'] == code_to_update]['stock_actual'].iloc[0])
                        new_stock = current_stock + add_stock
                        try:
                            supabase.table("productos").update({"stock_actual": new_stock}).eq("codigo_barras", code_to_update).execute()
                            exito_re = True
                        except Exception as e: st.error(ERROR_ADMIN)
                        
                        if exito_re:
                            st.success(f"✅ Stock actualizado. Nuevo stock: {new_stock}")
                            time.sleep(1.5); st.rerun() 
            else: 
                st.info("📭 Aún no se han registrado productos en el inventario.")
        except Exception as e: st.error(ERROR_ADMIN)

# ==========================================
# 🔄 MÓDULO 3: DEVOLUCIONES
# ==========================================
elif menu == "🔄 DEVOLUCIONES":
    st.subheader("Gestión de Devoluciones de Clientes")
    with st.expander("📷 ESCANEAR TICKET O PRODUCTO", expanded=False):
        img_dev = st.camera_input("Scanner Devolución", key=f"cam_dev_{st.session_state.cam_d_key}")
        if img_dev:
            code_dev = scan_pos(img_dev)
            if code_dev:
                st.session_state.iny_dev_cod = code_dev 
                st.session_state.cam_d_key += 1 
                st.rerun()
            else: st.warning("⚠️ No se detectó código. Intenta enfocar mejor.")

    tick = st.text_input("Ingresa el Número de Ticket o Código", value=st.session_state.iny_dev_cod)
    if tick:
        try:
            v_cab = supabase.table("ventas_cabecera").select("*").eq("ticket_numero", tick).execute()
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
                            supabase.table("devoluciones").insert({"producto_id": d['producto_id'], "cantidad": d['cantidad'], "motivo": "Devolución", "dinero_devuelto": d['subtotal'], "estado_producto": "Vuelve a tienda"}).execute()
                            st.session_state.iny_dev_cod = "" 
                            exito_dev = True
                        except Exception as e: st.error(ERROR_ADMIN)
                        if exito_dev: st.success("✅ Dinero descontado y producto vuelto a vitrina."); time.sleep(1.5); st.rerun()
            else: st.warning("⚠️ Ticket no encontrado en el sistema. Verifica el número.")
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

    with st.form("form_merma", clear_on_submit=True):
        m_cod = st.text_input("Código de Barras del Producto Dañado", value=st.session_state.iny_merma_cod)
        m_cant = st.number_input("Cantidad a descontar", min_value=1)
        m_mot = st.selectbox("Motivo Exacto", ["Roto al instalar/mostrar", "Falla de Fábrica (Garantía Proveedor)", "Robo/Extravío"])
        
        if st.form_submit_button("⚠️ CONFIRMAR PÉRDIDA Y DESCONTAR", type="primary"):
            exito_merma = False
            if m_cod:
                try:
                    p_inf = supabase.table("productos").select("stock_actual, costo_compra, nombre").eq("codigo_barras", m_cod).execute()
                    if p_inf.data:
                        if p_inf.data[0]['stock_actual'] >= m_cant:
                            supabase.table("productos").update({"stock_actual": p_inf.data[0]['stock_actual'] - m_cant}).eq("codigo_barras", m_cod).execute()
                            supabase.table("mermas").insert({"producto_id": m_cod, "cantidad": m_cant, "motivo": m_mot, "perdida_monetaria": p_inf.data[0]['costo_compra'] * m_cant}).execute()
                            st.session_state.iny_merma_cod = "" 
                            exito_merma = True
                        else: st.error("❌ No puedes dar de baja más stock del que tienes.")
                    else: st.warning("⚠️ Código de producto inválido o no existe en inventario.")
                except Exception as e: st.error(ERROR_ADMIN)
            else: st.warning("⚠️ Debes ingresar o escanear un código de barras.")
            
            if exito_merma:
                st.success(f"✅ Baja exitosa: {m_cant} ud. de {p_inf.data[0]['nombre']}"); time.sleep(1.5); st.rerun()

# ==========================================
# 📊 MÓDULO 5: REPORTES
# ==========================================
elif menu == "📊 REPORTES":
    st.subheader("Centro de Análisis Financiero")
    v_full = load_data("ventas_cabecera")
    if not v_full.empty:
        m1, m2 = st.columns(2)
        m1.metric("Ingresos Totales (Bruto)", f"S/. {v_full['total_venta'].sum():.2f}")
        m2.metric("Total de Ventas Realizadas", len(v_full))
        
        if 'created_at' in v_full.columns:
            v_full['fecha'] = pd.to_datetime(v_full['created_at']).dt.date
            fig = px.bar(v_full.groupby('fecha')['total_venta'].sum().reset_index(), x="fecha", y="total_venta", title="Ingresos por Día")
            st.plotly_chart(fig, use_container_width=True)
    else: st.info("📭 Aún no se han registrado ventas para generar reportes.")
