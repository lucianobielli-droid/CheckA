import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="United Airlines - Materials Dashboard", layout="wide")

@st.cache_data
def load_data(file):
    return pd.read_csv(file)

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

# --- SIDEBAR: CARGA DE ARCHIVOS ---
st.sidebar.image("https://upload.wikimedia.org/wikipedia/en/thumb/e/e0/United_Airlines_Logo.svg/1200px-United_Airlines_Logo.svg.png", width=200)
st.sidebar.title("Gestión de Materiales")

file_stock = st.sidebar.file_uploader("1️⃣ Base de Stock (EZESTOCK_FINAL)", type=["csv"])
file_jobs = st.sidebar.file_uploader("2️⃣ Trabajos Programados (WPEZE_Filter)", type=["csv"])

if file_stock and file_jobs:
    df_stock = load_data(file_stock)
    df_jobs = load_data(file_jobs)

    # Limpieza de datos
    df_jobs['scheduled_date'] = pd.to_datetime(df_jobs['scheduled_date']).dt.date
    df_stock['QOH'] = pd.to_numeric(df_stock['QOH'], errors='coerce').fillna(0)
    df_stock['required_part_quantity'] = pd.to_numeric(df_stock['required_part_quantity'], errors='coerce').fillna(0)

    # Selector de Modo
    modo = st.sidebar.radio("Selecciona una vista:", ["📅 Planificador por Fecha", "📦 Análisis de Stock General"])

    if modo == "📅 Planificador por Fecha":
        st.header("📅 Planificador de Materiales por Actividad")
        
        # 1. Selector de fecha
        fechas_disponibles = sorted(df_jobs['scheduled_date'].unique())
        selected_date = st.date_input("Selecciona una fecha del calendario:", 
                                     value=fechas_disponibles[0] if fechas_disponibles else None,
                                     min_value=min(fechas_disponibles) if fechas_disponibles else None,
                                     max_value=max(fechas_disponibles) if fechas_disponibles else None)

        # 2. Filtrar trabajos del día
        jobs_today = df_jobs[df_jobs['scheduled_date'] == selected_date]
        
        if not jobs_today.empty:
            st.subheader(f"Actividades para el {selected_date}")
            st.table(jobs_today[['mne_number', 'mne_description', 'package_description']])

            # 3. Cruzar con Base de Stock
            # Buscamos los materiales asociados a los mne_number programados
            mne_list = jobs_today['mne_number'].unique()
            materiales_necesarios = df_stock[df_stock['Mne_Dash8'].isin(mne_list)]

            if not materiales_necesarios.empty:
                # Consolidar materiales por si varios trabajos piden lo mismo
                resumen = materiales_necesarios.groupby(['m_e', 'description', 'manufacturer_part_number', 'bin']).agg({
                    'required_part_quantity': 'sum',
                    'QOH': 'first'
                }).reset_index()

                resumen['faltante'] = (resumen['required_part_quantity'] - resumen['QOH']).clip(lower=0)
                resumen['estado'] = resumen['faltante'].apply(lambda x: "⚠️ PEDIR" if x > 0 else "✅ OK")

                st.subheader("📦 Materiales Requeridos para el día")
                
                # Estilo de tabla
                def highlight_stock(row):
                    return ['background-color: #ffcccc' if row.estado == "⚠️ PEDIR" else '' for _ in row]

                st.dataframe(resumen.style.apply(highlight_stock, axis=1), use_container_width=True)

                # KPIs del día
                col1, col2 = st.columns(2)
                col1.metric("Items Faltantes", len(resumen[resumen['faltante'] > 0]))
                col2.metric("Total Unidades a Pedir", int(resumen['faltante'].sum()))

                # Botón de Descarga
                st.download_button("📥 Descargar Lista de Picking (Excel)", 
                                  data=to_excel(resumen), 
                                  file_name=f"materiales_{selected_date}.xlsx")
            else:
                st.warning("No se encontraron materiales cargados en la base de stock para estos códigos MNE.")
        else:
            st.info("No hay trabajos programados para la fecha seleccionada.")

    else:
        # --- MODO ANÁLISIS GENERAL (Tu lógica original mejorada) ---
        st.header("📦 Análisis General de Stock")
        search_mne = st.sidebar.text_input("🔎 Filtrar por MNE (comodín)")
        
        todos_mne = sorted(df_stock["Mne_Dash8"].dropna().unique())
        if search_mne:
            opciones = [v for v in todos_mne if search_mne.lower() in str(v).lower()]
        else:
            opciones = todos_mne

        seleccion = st.sidebar.multiselect("Selecciona MNEs:", opciones)
        
        df_final = df_stock[df_stock["Mne_Dash8"].isin(seleccion)] if seleccion else df_stock
        
        # ... (Aquí puedes mantener el resto de tu lógica de gráficos y tablas generales)
        st.dataframe(df_final.head(100), use_container_width=True)
        st.info("Filtra por la barra lateral para ver el análisis detallado.")

else:
    st.info("👈 Por favor, sube AMBAS bases de datos (Stock y Trabajos) en la barra lateral para comenzar.")
