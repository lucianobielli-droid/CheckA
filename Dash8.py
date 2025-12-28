import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="United Airlines - Materials Dashboard", layout="wide")

# Estilo CSS para forzar el ajuste de texto en encabezados y mejorar visualización
st.markdown("""
    <style>
    /* Ajuste para que los encabezados de las tablas ocupen más espacio si es necesario */
    .stDataFrame th {
        white-space: normal !important;
        vertical-align: bottom !important;
        line-height: 1.2 !important;
    }
    </style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data(file):
    return pd.read_csv(file)

def to_excel(df):
    output = BytesIO()
    # Usamos openpyxl como alternativa común si xlsxwriter no está
    try:
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
    except:
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

# --- SIDEBAR ---
st.sidebar.image("https://upload.wikimedia.org/wikipedia/en/thumb/e/e0/United_Airlines_Logo.svg/1200px-United_Airlines_Logo.svg.png", width=200)
st.sidebar.title("Gestión de Materiales")

file_stock = st.sidebar.file_uploader("1️⃣ Base de Stock (EZESTOCK_FINAL)", type=["csv"])
file_jobs = st.sidebar.file_uploader("2️⃣ Trabajos Programados (WPEZE_Filter)", type=["csv"])

if file_stock and file_jobs:
    df_stock = load_data(file_stock)
    df_jobs = load_data(file_jobs)

    # Limpieza de datos numéricos
    cols_num = ['QOH', 'required_part_quantity', 'planned_quantity']
    for col in cols_num:
        if col in df_stock.columns:
            df_stock[col] = pd.to_numeric(df_stock[col], errors='coerce').fillna(0)

    df_jobs['scheduled_date'] = pd.to_datetime(df_jobs['scheduled_date']).dt.date

    # --- SELECTORES DE FILTRO (SIDEBAR) ---
    st.sidebar.header("🔍 Filtros de Búsqueda")
    
    # Búsqueda por MNE (comodín)
    search_mne = st.sidebar.text_input("Buscar por MNE (ej: 27-05)")
    # Búsqueda por m_e (comodín) - NUEVO
    search_me = st.sidebar.text_input("Buscar por Part Number / m_e (ej: 75-25)")

    # Filtrado lógico de la base de stock
    df_filtered_stock = df_stock.copy()
    if search_mne:
        df_filtered_stock = df_filtered_stock[df_filtered_stock['Mne_Dash8'].str.contains(search_mne, case=False, na=False)]
    if search_me:
        df_filtered_stock = df_filtered_stock[df_filtered_stock['m_e'].str.contains(search_me, case=False, na=False)]

    modo = st.sidebar.radio("Selecciona una vista:", ["📅 Planificador por Fecha", "📦 Análisis de Stock General"])

    # Configuración de columnas para que los encabezados se vean mejor
    col_config = {
        "estado": st.column_config.TextColumn("Estado (Stock)", width="small"),
        "m_e": st.column_config.TextColumn("Part Number (m_e)", width="medium"),
        "description": st.column_config.TextColumn("Descripción del Material", width="large"),
        "QOH": st.column_config.NumberColumn("Stock Actual (QOH)", width="small"),
        "required_part_quantity": st.column_config.NumberColumn("Cant. Requerida (Req)", width="small"),
        "planned_quantity": st.column_config.NumberColumn("Cant. Planificada (Plan)", width="small"),
        "faltante": st.column_config.NumberColumn("Faltante Calculado", width="small"),
        "bin": st.column_config.TextColumn("Ubicación (Bin)", width="medium")
    }

    if modo == "📅 Planificador por Fecha":
        st.header("📅 Planificador de Materiales por Actividad")
        
        fechas_disponibles = sorted(df_jobs['scheduled_date'].unique())
        selected_date = st.date_input("Fecha del calendario:", value=fechas_disponibles[0] if fechas_disponibles else None)

        jobs_today = df_jobs[df_jobs['scheduled_date'] == selected_date]
        
        if not jobs_today.empty:
            st.subheader(f"Actividades para el {selected_date}")
            st.dataframe(jobs_today[['mne_number', 'mne_description', 'package_description']], use_container_width=True)

            mne_list = jobs_today['mne_number'].unique()
            # Aplicamos también los filtros de búsqueda de la sidebar si existen
            materiales_necesarios = df_filtered_stock[df_filtered_stock['Mne_Dash8'].isin(mne_list)]

            if not materiales_necesarios.empty:
                resumen = materiales_necesarios.groupby(['m_e', 'description', 'manufacturer_part_number', 'bin']).agg({
                    'required_part_quantity': 'sum',
                    'planned_quantity': 'sum', # AGREGADO
                    'QOH': 'first'
                }).reset_index()

                resumen['faltante'] = (resumen['required_part_quantity'] - resumen['QOH']).clip(lower=0)
                resumen['estado'] = resumen['faltante'].apply(lambda x: "⚠️ PEDIR" if x > 0 else "✅ OK")

                # Reordenar para visualización
                resumen = resumen[['estado', 'm_e', 'description', 'QOH', 'required_part_quantity', 'planned_quantity', 'faltante', 'bin']]

                st.subheader("📦 Detalle de Materiales Requeridos")
                st.dataframe(
                    resumen.style.map(lambda x: 'background-color: #ffcccc' if x == "⚠️ PEDIR" else '', subset=['estado']),
                    use_container_width=True,
                    column_config=col_config
                )
            else:
                st.warning("No hay materiales vinculados a estos MNE en la base de stock.")

    else:
        st.header("📦 Análisis General de Stock")
        
        # Mostramos la base filtrada por los buscadores de la sidebar
        resumen_gen = df_filtered_stock.groupby(['m_e', 'description', 'Mne_Dash8', 'bin']).agg({
            'required_part_quantity': 'sum',
            'planned_quantity': 'sum', # AGREGADO
            'QOH': 'first'
        }).reset_index()

        resumen_gen['faltante'] = (resumen_gen['required_part_quantity'] - resumen_gen['QOH']).clip(lower=0)
        resumen_gen['estado'] = resumen_gen['faltante'].apply(lambda x: "⚠️ PEDIR" if x > 0 else "✅ OK")

        st.dataframe(
            resumen_gen[['estado', 'm_e', 'Mne_Dash8', 'description', 'QOH', 'required_part_quantity', 'planned_quantity', 'faltante', 'bin']],
            use_container_width=True,
            column_config=col_config
        )

else:
    st.info("👈 Sube los archivos CSV para activar el panel.")
