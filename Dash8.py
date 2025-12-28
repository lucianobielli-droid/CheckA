import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="United Airlines - Materials Dashboard", layout="wide")

# Estilo CSS para mejorar la visibilidad de los encabezados
st.markdown("""
    <style>
    .stDataFrame th { white-space: normal !important; }
    [data-testid="stMetricValue"] { font-size: 24px; }
    </style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data(file):
    return pd.read_csv(file)

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
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

    # --- LIMPIEZA Y FORMATEO DE DATOS ---
    cols_num = ['QOH', 'required_part_quantity', 'planned_quantity']
    for col in cols_num:
        if col in df_stock.columns:
            df_stock[col] = pd.to_numeric(df_stock[col], errors='coerce').fillna(0).astype(int)

    df_jobs['scheduled_date'] = pd.to_datetime(df_jobs['scheduled_date']).dt.date

    # --- FILTROS SIDEBAR ---
    st.sidebar.header("🔍 Buscadores")
    search_mne = st.sidebar.text_input("Filtrar por MNE (comodín)")
    search_me = st.sidebar.text_input("Filtrar por Part Number / m_e")

    # Aplicar filtros
    df_filtered_stock = df_stock.copy()
    if search_mne:
        df_filtered_stock = df_filtered_stock[df_filtered_stock['Mne_Dash8'].str.contains(search_mne, case=False, na=False)]
    if search_me:
        df_filtered_stock = df_filtered_stock[df_filtered_stock['m_e'].str.contains(search_me, case=False, na=False)]

    modo = st.sidebar.radio("Selecciona una vista:", ["📅 Planificador por Fecha", "📦 Análisis de Stock General", "📈 Gráfico Comparativo"])

    # --- CONFIGURACIÓN DE COLUMNAS (Ajuste de tamaño y nombres) ---
    col_config = {
        "estado": st.column_config.TextColumn("ESTADO", width="small"),
        "m_e": st.column_config.TextColumn("PART NUMBER (m_e)", width="medium"),
        "description": st.column_config.TextColumn("DESCRIPCIÓN", width="large"),
        "QOH": st.column_config.NumberColumn("STOCK ACTUAL", format="%d", width="small"),
        "required_part_quantity": st.column_config.NumberColumn("REQ.", format="%d", width="small"),
        "faltante": st.column_config.NumberColumn("FALTANTE CALC.", format="%d", width="small"),
        "OPEN ORDERS": st.column_config.NumberColumn("OPEN ORDERS", format="%d", width="small"),
        "REQUISITO": st.column_config.TextColumn("REQUISITO", width="medium"),
        "bin": st.column_config.TextColumn("UBICACIÓN (BIN)", width="small")
    }

    if modo == "📅 Planificador por Fecha":
        st.header("📅 Materiales por Fecha Programada")
        fechas = sorted(df_jobs['scheduled_date'].unique())
        selected_date = st.date_input("Selecciona fecha:", value=fechas[0] if fechas else None)
        
        jobs_today = df_jobs[df_jobs['scheduled_date'] == selected_date]
        if not jobs_today.empty:
            mne_list = jobs_today['mne_number'].unique()
            resumen = df_filtered_stock[df_filtered_stock['Mne_Dash8'].isin(mne_list)].copy()
            
            if not resumen.empty:
                # Renombrar y calcular
                resumen = resumen.rename(columns={'planned_quantity': 'OPEN ORDERS', 'part_action': 'REQUISITO'})
                resumen['faltante'] = (resumen['required_part_quantity'] - resumen['QOH']).clip(lower=0).astype(int)
                resumen['estado'] = resumen['faltante'].apply(lambda x: "⚠️ PEDIR" if x > 0 else "✅ OK")
                
                # Ordenar columnas según petición
                resumen = resumen[['estado', 'm_e', 'description', 'QOH', 'required_part_quantity', 'faltante', 'OPEN ORDERS', 'REQUISITO', 'bin']]
                
                st.dataframe(resumen.style.map(lambda x: 'color: red; font-weight: bold' if x == "⚠️ PEDIR" else '', subset=['estado']),
                             use_container_width=True, column_config=col_config)
            else:
                st.warning("No hay materiales vinculados para esta fecha.")

    elif modo == "📦 Análisis de Stock General":
        st.header("📦 Análisis General de Inventario")
        resumen_gen = df_filtered_stock.copy()
        resumen_gen = resumen_gen.rename(columns={'planned_quantity': 'OPEN ORDERS', 'part_action': 'REQUISITO'})
        resumen_gen['faltante'] = (resumen_gen['required_part_quantity'] - resumen_gen['QOH']).clip(lower=0).astype(int)
        resumen_gen['estado'] = resumen_gen['faltante'].apply(lambda x: "⚠️ PEDIR" if x > 0 else "✅ OK")
        
        resumen_gen = resumen_gen[['estado', 'm_e', 'description', 'QOH', 'required_part_quantity', 'faltante', 'OPEN ORDERS', 'REQUISITO', 'bin']]
        
        st.dataframe(resumen_gen, use_container_width=True, column_config=col_config)

    elif modo == "📈 Gráfico Comparativo":
        st.header("📈 Seguimiento Visual de Stock (QOH)")
        
        # Entrada de lista de M_Es proporcionada por el usuario
        lista_input = st.text_area("Pega aquí tu lista de Part Numbers (m_e) separados por comas o líneas:", 
                                   "75-2531-3-0088, 00-0712-3-0044, 78-2500-3-0985")
        
        lista_mes = [x.strip() for x in lista_input.replace('\n', ',').split(',') if x.strip()]
        df_plot = df_stock[df_stock['m_e'].isin(lista_mes)].drop_duplicates('m_e')

        if not df_plot.empty:
            # Gráfico Interactivo con iconos/marcadores
            fig = go.Figure()

            # Barras de Stock
            fig.add_trace(go.Bar(
                x=df_plot['m_e'],
                y=df_plot['QOH'],
                name='Stock Actual (QOH)',
                marker_color='royalblue',
                text=df_plot['QOH'],
                textposition='auto',
            ))

            # Añadir "Iconos" (marcadores de diamante para resaltar el nivel)
            fig.add_trace(go.Scatter(
                x=df_plot['m_e'],
                y=df_plot['QOH'] + (df_plot['QOH'].max()*0.05), # Un poco arriba de la barra
                mode='markers+text',
                name='Alerta/Estado',
                marker=dict(symbol='diamond', size=15, color='orange'),
                text=["📦" for _ in range(len(df_plot))],
                textposition="top center"
            ))

            fig.update_layout(
                title="Disponibilidad de Part Numbers Seleccionados",
                xaxis_title="Part Number (m_e)",
                yaxis_title="Cantidad en Mano",
                template="plotly_white",
                hovermode="x unified"
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Ingresa números de parte válidos para generar el gráfico.")

else:
    st.info("👈 Por favor, carga los archivos para comenzar.")
