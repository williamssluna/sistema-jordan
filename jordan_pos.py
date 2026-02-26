import streamlit as st
from supabase import create_client
import pandas as pd
import zxingcpp
from PIL import Image
import numpy as np
import cv2
import time
from datetime import datetime

# --- 1. CONEXIÓN A SUPABASE ---
URL_SUPABASE = "https://degzltrjrzqbahdonmmb.supabase.co"
KEY_SUPABASE = "sb_publishable_td5_vXX42LYc8PlTAbBgVg_-xCp-94r"

try:
    supabase = create_client(URL_SUPABASE, KEY_SUPABASE)
except Exception as e:
    st.error(f"Error de conexión: {e}")

st.set_page_config(page_title="JORDAN POS PRO", layout="centered", page_icon="🛍️")

# --- 2. ESTILO VISUAL PROFESIONAL ---
st.markdown("""
    <style>
    .stApp { background-color: #f4f6f9; }
    .css-card { 
        background-color: white; 
        padding: 25px; 
        border-radius: 12px; 
        box-shadow: 0 4px 12px rgba(0,0,0,0.08); 
        margin-bottom: 20px; 
        border-left: 5px solid #007bff;
    }
    .stButton>button { width: 100%; height: 60px; font-size: 18px; border-radius: 8px; font-weight: 700; transition: 0.2s; }
    .stButton>button:hover { transform: scale(1.02); }
    
    /* TICKET */
    .ticket-box {
        background-color: #fff;
        border: 1px solid #ddd;
        padding: 20px;
        text-align: center;
        margin-bottom: 20px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        position: relative;
    }
    .ticket-header { font-size: 18px; font-weight: bold; color: #333; margin-bottom: 5px; text-transform: uppercase; border-bottom: 2px dashed #333; padding-bottom: 10px; }
    .ticket-item { font-size: 24px; color: #000; font-weight: 800; margin: 15px 0; }
    .ticket-price { font-size: 36px; font-weight: bold; color: #28a745; margin: 10px 0; }
    .ticket-info { font-size: 14px; color: #666; display: flex; justify-content: space-between; margin-top: 15px; border-top: 1px dashed #ccc; padding-top: 10px;}
    
    /* ALERTAS */
    .alert-danger { background-color: #f8d7da; color: #721c24; padding: 10px; border-radius: 5px; border: 1px solid #f5c6cb; font-weight: bold; text-align: center; }
    .alert-warning { background-color: #fff3cd; color: #856404; padding: 10px; border-radius: 5px; border: 1px solid #ffeeba; font-weight: bold; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. MEMORIA DEL SISTEMA ---
if 'admin_login' not in st.session_state: st.session_state.admin_login = False
if 'input_v' not in st.session_state: st.session_state.input_v = ""
if 'scan_agregar' not in st.session_state: st.session_state.scan_agregar = ""
if 'exito_agregar' not in st.session_state: st.session_state.exito_agregar = False
if 'ticket_final' not in st.session_state: st.session_state.ticket_final = None

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

def ejecutar_venta(codigo, stock_actual, nombre_prod):
    try:
        precio_real = st.session_state.precio_final_input
        datos_venta = {
            "producto_id": codigo, 
            "precio_final_vendido": precio_real,
            "vendedor_nombre": "Vendedor"
        }
        supabase.table("ventas").insert(datos_venta).execute()
        
        nuevo_stock = int(stock_actual) - 1
        supabase.table("productos").update({"stock_actual": nuevo_stock}).eq("codigo_barras", codigo).execute()
        
        st.session_state.ticket_final = {
            "nombre": nombre_prod,
            "precio": precio_real,
            "hora": datetime.now().strftime("%I:%M %p"),
            "fecha": datetime.now().strftime("%d/%m/%Y")
        }
        st.session_state.input_v = "" 
        
    except Exception as e:
        st.error(f"Error crítico DB: {e}")

def guardar_producto_nuevo(codigo, nombre, costo, stock, p_venta, p_min):
    if codigo and nombre:
        try:
            codigo = codigo.strip()
            supabase.table("productos").insert({
                "codigo_barras": codigo, "nombre": nombre, "costo_compra": costo,
                "precio_lista": p_venta, "precio_minimo": p_min, "stock_actual": stock
            }).execute()
            st.session_state.scan_agregar = "" 
            st.session_state.exito_agregar = True
        except Exception as e:
            st.error(f"Error DB: {e}")

def limpiar_agregar():
    st.session_state.scan_agregar = ""

def cerrar_ticket():
    st.session_state.ticket_final = None

def check_login(clave_unica):
    if not st.session_state.admin_login:
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        st.warning("🔒 Acceso Gerencial Requerido")
        c1, c2 = st.columns(2)
        u = c1.text_input("Usuario", key=f"user_{clave_unica}")
        p = c2.text_input("Clave", type="password", key=f"pass_{clave_unica}")
        if st.button("🔓 Desbloquear Sistema", key=f"btn_{clave_unica}"):
            if u == "admin" and p == "12345":
                st.session_state.admin_login = True
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        return False
    return True

st.title("🛍️ Accesorios Jordan POS")
tabs = st.tabs(["🛒 PUNTO DE VENTA", "📦 REGISTRAR STOCK", "📊 REPORTES PRO"])

# ==================================================
# PESTAÑA 1: VENTA
# ==================================================
with tabs[0]:
    if st.session_state.ticket_final:
        t = st.session_state.ticket_final
        st.balloons()
        
        st.markdown(f"""
        <div class="ticket-box">
            <div class="ticket-header">Accesorios Jordan<br>Comprobante</div>
            <div class="ticket-item">{t['nombre']}</div>
            <div class="ticket-price">S/. {t['precio']:.2f}</div>
            <div class="ticket-info">
                <span>📅 {t['fecha']}</span>
                <span>⏰ {t['hora']}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("✨ NUEVA VENTA", on_click=cerrar_ticket):
            st.rerun()
            
    else:
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        
        with st.expander("📷 ACTIVAR CÁMARA", expanded=True):
            img_v = st.camera_input("Escáner", key="cam_venta", label_visibility="hidden")
            if img_v:
                code = procesar_imagen_avanzado(img_v)
                if code:
                    if code != st.session_state.input_v:
                        st.session_state.input_v = code 
                        st.rerun()

        cod_input = st.text_input("🔍 Buscar por Código", key="input_v", placeholder="Escanea o escribe...")

        if st.button("🧹 Limpiar Búsqueda", key="btn_limpiar_vender"):
            st.session_state.input_v = ""
            st.rerun()

        if cod_input:
            cod_limpio = cod_input.strip()
            res = supabase.table("productos").select("*").eq("codigo_barras", cod_limpio).execute()
            
            if res.data:
                p = res.data[0]
                st.markdown(f"""
                <div style="background-color:#e9ecef; padding:15px; border-radius:10px; margin-top:10px;">
                    <h3 style="margin:0; color:#333;">📦 {p['nombre']}</h3>
                    <p style="margin:0; color:#666;">Stock Disponible: <b>{p['stock_actual']} unid.</b></p>
                </div>
                """, unsafe_allow_html=True)
                
                costo_compra = float(p['costo_compra'])
                precio_min = float(p['precio_minimo'])
                precio_sugerido = float(p['precio_lista'])
                
                st.write("")
                col_p1, col_p2 = st.columns(2)
                col_p1.metric("Precio Sugerido", f"S/. {precio_sugerido:.2f}")
                
                precio_final = st.number_input("💵 PRECIO FINAL (S/.)", value=precio_sugerido, step=0.5, key="precio_final_input")
                
                venta_permitida = True
                if precio_final < costo_compra:
                    st.markdown(f'<div class="alert-danger">⛔ VENTA BLOQUEADA: Precio menor al costo (S/. {costo_compra:.2f})</div>', unsafe_allow_html=True)
                    venta_permitida = False
                elif precio_final < precio_min:
                    st.markdown(f'<div class="alert-warning">⚠️ PRECIO BAJO: Menor al mínimo (S/. {precio_min:.2f})</div>', unsafe_allow_html=True)
                
                if p['stock_actual'] <= 0:
                    st.error("❌ SIN STOCK")
                    venta_permitida = False

                st.write("")
                if venta_permitida:
                    st.button("✅ CONFIRMAR", on_click=ejecutar_venta, args=(cod_limpio, p['stock_actual'], p['nombre']), type="primary")
            else:
                st.warning(f"Producto no encontrado: {cod_limpio}")

        st.markdown('</div>', unsafe_allow_html=True)

# ==================================================
# PESTAÑA 2: AGREGAR
# ==================================================
with tabs[1]:
    if check_login("tab_agregar"):
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        c_head, c_lock = st.columns([3,1])
        c_head.subheader("📦 Ingreso")
        if c_lock.button("🔒 Salir", key="logout_1"):
            st.session_state.admin_login = False
            st.rerun()
            
        if st.session_state.exito_agregar:
            st.success("✅ ¡Registrado!")
            st.session_state.exito_agregar = False

        with st.expander("📷 ESCANEAR CÓDIGO NUEVO", expanded=True):
            img_a = st.camera_input("Scan", key="cam_add", label_visibility="hidden")
            if img_a:
                code_a = procesar_imagen_avanzado(img_a)
                if code_a:
                    if code_a != st.session_state.scan_agregar:
                        st.session_state.scan_agregar = code_a
                        st.rerun()
                    else:
                        st.success(f"Capturado: {code_a}")

        c_barras = st.text_input("Código de Barras", key="scan_agregar", placeholder="Escanea o escribe...") 
        nombre = st.text_input("Nombre del Producto", placeholder="Ej. Audífonos...")
        
        c1, c2 = st.columns(2)
        costo = c1.number_input("🔴 Costo (S/.)", min_value=0.0, step=0.5)
        stock = c2.number_input("📦 Stock", min_value=1, step=1)
        
        c3, c4 = st.columns(2)
        p_venta = c3.number_input("🟢 Precio Venta (S/.)", min_value=0.0, step=0.5)
        p_min = c4.number_input("🟠 Precio Mínimo (S/.)", min_value=0.0, step=0.5)
        
        if costo > 0 and p_venta > 0:
            margen = p_venta - costo
            st.info(f"📊 Ganancia estimada: S/. {margen:.2f}")
        
        st.write("---")
        
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            if st.button("🧹 Limpiar", key="btn_limpiar_agregar", on_click=limpiar_agregar): pass
        with col_b2:
            st.button("💾 GUARDAR", on_click=guardar_producto_nuevo, args=(c_barras, nombre, costo, stock, p_venta, p_min), type="primary")
            
        st.markdown('</div>', unsafe_allow_html=True)

# ==================================================
# PESTAÑA 3: REPORTES (CORREGIDO PARA ERROR DE COLUMNAS)
# ==================================================
with tabs[2]:
    if check_login("tab_almacen"):
        st.markdown('<div class="css-card">', unsafe_allow_html=True)
        st.subheader("📊 Inteligencia de Negocios")
        if st.button("🔒 Cerrar Sesión", key="logout_2"):
            st.session_state.admin_login = False
            st.rerun()

        modo = st.radio("Reporte:", ["📉 Análisis de Rentabilidad", "📋 Inventario y Stock", "🗑️ Eliminar Producto"])
        st.write("---")

        if modo == "📉 Análisis de Rentabilidad":
            res_ventas = supabase.table("ventas").select("*").execute()
            res_prod = supabase.table("productos").select("*").execute()
            
            if res_ventas.data and res_prod.data:
                df_ventas = pd.DataFrame(res_ventas.data)
                df_prod = pd.DataFrame(res_prod.data)
                
                # CORRECCIÓN KEYERROR: Estandarizamos tipos
                df_ventas['producto_id'] = df_ventas['producto_id'].astype(str)
                df_prod['codigo_barras'] = df_prod['codigo_barras'].astype(str)

                # UNIÓN Y CORRECCIÓN DE NOMBRES DUPLICADOS
                # Si ambos tienen 'created_at', pandas crea _x y _y.
                # Lo solucionamos renombrando después del merge
                df_full = pd.merge(df_ventas, df_prod, left_on='producto_id', right_on='codigo_barras', how='left')
                
                # BUSCAMOS LA COLUMNA DE FECHA CORRECTA
                # A veces se llama 'created_at', a veces 'created_at_x'
                col_fecha = 'created_at'
                if 'created_at_x' in df_full.columns:
                    col_fecha = 'created_at_x'
                elif 'created_at' not in df_full.columns and 'created_at_y' in df_full.columns:
                    col_fecha = 'created_at_y'
                
                df_full['ganancia_real'] = df_full['precio_final_vendido'] - df_full['costo_compra'].fillna(0)
                
                total_vendido = df_full['precio_final_vendido'].sum()
                ganancia_total = df_full['ganancia_real'].sum()
                
                m1, m2, m3 = st.columns(3)
                m1.metric("Ventas Totales", f"S/. {total_vendido:.2f}")
                m2.metric("Ganancia Neta", f"S/. {ganancia_total:.2f}", delta="Dinero Real")
                m3.metric("Transacciones", len(df_full))
                
                st.write("📜 **Detalle:**")
                
                # PREPARAMOS TABLA FINAL SEGURA
                df_show = pd.DataFrame()
                df_show['Fecha'] = df_full[col_fecha]
                df_show['Producto'] = df_full['nombre'].fillna("Producto Borrado")
                df_show['Precio Venta'] = df_full['precio_final_vendido']
                df_show['Ganancia'] = df_full['ganancia_real']
                
                st.dataframe(df_show.sort_values('Fecha', ascending=False), use_container_width=True)
            else:
                st.info("No hay datos suficientes para el reporte.")

        elif modo == "📋 Inventario y Stock":
            res = supabase.table("productos").select("*").execute()
            if res.data:
                df = pd.DataFrame(res.data)
                stock_critico = df[df['stock_actual'] <= 2]
                if not stock_critico.empty:
                    st.warning(f"⚠️ {len(stock_critico)} productos con bajo stock!")
                
                st.dataframe(df[['nombre', 'stock_actual', 'costo_compra', 'precio_lista', 'codigo_barras']], use_container_width=True)

        elif modo == "🗑️ Eliminar Producto":
            code_del = st.text_input("Código a eliminar")
            st.markdown('<span class="btn-rojo">', unsafe_allow_html=True)
            if st.button("🗑️ BORRAR"):
                supabase.table("productos").delete().eq("codigo_barras", code_del).execute()
                st.success("Eliminado.")
                time.sleep(1)
                st.rerun()
            st.markdown('</span>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
