import streamlit as st
from supabase import create_client
import pandas as pd
import zxingcpp
from PIL import Image
import numpy as np
import cv2
import time

# --- 1. CONEXIÓN A SUPABASE ---
URL_SUPABASE = "https://degzltrjrzqbahdonmmb.supabase.co"
KEY_SUPABASE = "sb_publishable_td5_vXX42LYc8PlTAbBgVg_-xCp-94r"

try:
    supabase = create_client(URL_SUPABASE, KEY_SUPABASE)
except Exception as e:
    st.error(f"Error de conexión: {e}")

st.set_page_config(page_title="JORDAN POS", layout="centered", page_icon="📱")

# --- 2. ESTILO VISUAL ---
st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; }
    .css-card { background-color: white; padding: 20px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; }
    .stButton>button { width: 100%; height: 60px; font-size: 18px; border-radius: 12px; font-weight: bold; }
    .btn-verde>button { background-color: #28a745; color: white; border: none; }
    .btn-rojo>button { background-color: #dc3545; color: white; border: none; }
    .btn-azul>button { background-color: #007bff; color: white; border: none; }
    .success-scan { background-color: #d1e7dd; color: #0f5132; padding: 15px; border-radius: 10px; text-align: center; font-weight: bold; font-size: 20px; margin: 10px 0; border: 1px solid #badbcc; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. MEMORIA DEL SISTEMA ---
if 'admin_login' not in st.session_state: st.session_state.admin_login = False
if 'input_v' not in st.session_state: st.session_state.input_v = ""
if 'scan_agregar' not in st.session_state: st.session_state.scan_agregar = ""
if 'mensaje_exito' not in st.session_state: st.session_state.mensaje_exito = False

# --- 4. FUNCIONES ---
def procesar_imagen_avanzado(uploaded_file):
    if uploaded_file is None: return None
    file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
    img_original = cv2.imdecode(file_bytes, 1)
    
    h, w, _ = img_original.shape
    start_row, start_col = int(h * 0.25), int(w * 0.25)
    end_row, end_col = int(h * 0.75), int(w * 0.75)
    img_crop = img_original[start_row:end_row, start_col:end_col]

    imagenes = [img_crop, cv2.cvtColor(img_crop, cv2.COLOR_BGR2GRAY), img_original]
    
    for img in imagenes:
        try:
            res = zxingcpp.read_barcodes(img)
            if res: return res[0].text
        except: continue
    return None

def ejecutar_venta(codigo, precio, stock_actual):
    try:
        datos_venta = {
            "producto_id": codigo, 
            "precio_final_vendido": precio,
            "vendedor_nombre": "Vendedor"
        }
        supabase.table("ventas").insert(datos_venta).execute()
        
        nuevo_stock = int(stock_actual) - 1
        supabase.table("productos").update({"stock_actual": nuevo_stock}).eq("codigo_barras", codigo).execute()
        
        st.session_state.input_v = ""
        st.session_state.mensaje_exito = True
        
    except Exception as e:
        st.error(f"Error al guardar: {e}")

# --- 5. LOGIN ---
def check_login(clave_unica):
    if not st.session_state.admin_login:
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        st.warning("🔒 Área Restringida")
        c1, c2 = st.columns(2)
        u = c1.text_input("Usuario", key=f"user_{clave_unica}")
        p = c2.text_input("Clave", type="password", key=f"pass_{clave_unica}")
        
        st.markdown('<span class="btn-azul">', unsafe_allow_html=True)
        if st.button("Ingresar", key=f"btn_{clave_unica}"):
            if u == "admin" and p == "12345":
                st.session_state.admin_login = True
                st.rerun()
            else:
                st.error("Datos incorrectos")
        st.markdown('</span></div>', unsafe_allow_html=True)
        return False
    return True

st.title("📱 Accesorios Jordan")
tabs = st.tabs(["🛒 VENDER", "➕ AGREGAR", "📊 ALMACÉN"])

# ==================================================
# PESTAÑA 1: VENDER
# ==================================================
with tabs[0]:
    st.markdown('<div class="css-card">', unsafe_allow_html=True)
    st.subheader("Punto de Venta")
    
    if st.session_state.mensaje_exito:
        st.balloons()
        st.success("✅ ¡Venta Realizada con Éxito!")
        st.session_state.mensaje_exito = False

    with st.expander("📷 ABRIR ESCÁNER", expanded=True):
        img_v = st.camera_input("Toma la foto", key="cam_venta")
        if img_v:
            # LÓGICA ANTI-BUCLE
            code = procesar_imagen_avanzado(img_v)
            if code:
                if code != st.session_state.input_v:
                    st.session_state.input_v = code 
                    st.rerun()
                else:
                    st.success(f"Detectado: {code}")
            else:
                st.warning("⚠️ No se detectó.")

    cod_input = st.text_input("Código de Barras", key="input_v")

    # SOLUCIÓN ERROR: Agregamos key="btn_limpiar_vender" para que sea único
    if st.button("🧹 Limpiar", key="btn_limpiar_vender"):
        st.session_state.input_v = ""
        st.rerun()

    if cod_input:
        cod_limpio = cod_input.strip()
        res = supabase.table("productos").select("*").eq("codigo_barras", cod_limpio).execute()
        
        if res.data:
            p = res.data[0]
            st.success("✅ ENCONTRADO")
            st.info(f"📦 **{p['nombre']}**")
            st.markdown(f"### Precio: S/. {p['precio_lista']}")
            p_final = st.number_input("Precio Final S/.", value=float(p['precio_lista']), step=0.5)
            
            st.markdown('<span class="btn-verde">', unsafe_allow_html=True)
            st.button("✅ CONFIRMAR VENTA", on_click=ejecutar_venta, args=(cod_limpio, p_final, p['stock_actual']))
            st.markdown('</span>', unsafe_allow_html=True)
        else:
            st.warning(f"El código {cod_limpio} no existe.")
    st.markdown('</div>', unsafe_allow_html=True)

# ==================================================
# PESTAÑA 2: AGREGAR
# ==================================================
with tabs[1]:
    if check_login("tab_agregar"):
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        c_head, c_lock = st.columns([3,1])
        c_head.subheader("Nuevo Producto")
        if c_lock.button("🔒 Salir", key="logout_1"):
            st.session_state.admin_login = False
            st.rerun()

        # 1. ESCÁNER (CON ANTI-BUCLE)
        with st.expander("📷 ABRIR ESCÁNER", expanded=True):
            img_a = st.camera_input("Escanear nuevo", key="cam_add")
            if img_a:
                code_a = procesar_imagen_avanzado(img_a)
                if code_a:
                    # SOLO recargamos si el código es NUEVO
                    if code_a != st.session_state.scan_agregar:
                        st.session_state.scan_agregar = code_a
                        st.rerun()
                    else:
                        # Si es el mismo, solo mostramos el aviso (pero no recargamos, así baja al formulario)
                        st.success(f"¡Capturado: {code_a}!")

        # 2. CAMPOS (Conectados a memoria)
        st.write("---")
        c_barras = st.text_input("Código de Barras", key="scan_agregar") 
        nombre = st.text_input("Nombre del Producto")
        
        c1, c2 = st.columns(2)
        costo = c1.number_input("Costo Compra", min_value=0.0)
        stock = c2.number_input("Stock Inicial", min_value=1)
        
        c3, c4 = st.columns(2)
        p_venta = c3.number_input("Precio Venta", min_value=0.0)
        p_min = c4.number_input("Precio Mínimo", min_value=0.0)
        
        st.markdown('<span class="btn-azul">', unsafe_allow_html=True)
        
        if st.button("💾 GUARDAR PRODUCTO"):
            if c_barras and nombre:
                try:
                    c_barras = c_barras.strip()
                    supabase.table("productos").insert({
                        "codigo_barras": c_barras, "nombre": nombre, "costo_compra": costo,
                        "precio_lista": p_venta, "precio_minimo": p_min, "stock_actual": stock
                    }).execute()
                    st.success(f"✅ {nombre} agregado.")
                    st.session_state.scan_agregar = "" 
                    time.sleep(1.5)
                    st.rerun()
                except Exception as e:
                    if "duplicate key" in str(e):
                        st.error("⛔ ERROR: Código duplicado.")
                    else: st.error(f"Error: {e}")
            else:
                st.warning("Falta nombre o código.")
        st.markdown('</span>', unsafe_allow_html=True)
        
        # SOLUCIÓN ERROR: Agregamos key="btn_limpiar_agregar" para que sea único
        if st.button("🧹 Limpiar", key="btn_limpiar_agregar"):
            st.session_state.scan_agregar = ""
            st.rerun()
            
        st.markdown('</div>', unsafe_allow_html=True)

# ==================================================
# PESTAÑA 3: ALMACÉN
# ==================================================
with tabs[2]:
    if check_login("tab_almacen"):
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        st.subheader("Control de Inventario")
        if st.button("🔒 Cerrar Sesión", key="logout_2"):
            st.session_state.admin_login = False
            st.rerun()

        modo = st.radio("Opciones:", ["📋 Ver Inventario", "🗑️ Eliminar Producto", "💰 Reporte Ventas"])
        st.write("---")

        if modo == "📋 Ver Inventario":
            res = supabase.table("productos").select("*").execute()
            if res.data:
                df = pd.DataFrame(res.data)
                st.dataframe(df[['nombre', 'stock_actual', 'precio_lista', 'codigo_barras']], use_container_width=True)

        elif modo == "🗑️ Eliminar Producto":
            code_del = st.text_input("Código a borrar")
            st.markdown('<span class="btn-rojo">', unsafe_allow_html=True)
            if st.button("🗑️ BORRAR DEFINITIVAMENTE"):
                supabase.table("productos").delete().eq("codigo_barras", code_del).execute()
                st.success("Producto eliminado.")
                time.sleep(1)
                st.rerun()
            st.markdown('</span>', unsafe_allow_html=True)

        elif modo == "💰 Reporte Ventas":
            ventas = supabase.table("ventas").select("*").execute()
            if ventas.data:
                df = pd.DataFrame(ventas.data)
                total = df['precio_final_vendido'].sum()
                st.metric("Total Vendido Hoy", f"S/. {total:.2f}")
                st.dataframe(df.tail(10), use_container_width=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
