import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="United Airlines - Materials Dashboard", layout="wide")

# Estilo CSS para mejorar la visibilidad
st.markdown("""
    <style>
    .stDataFrame th { white-space: normal !important; }
    .main-header { font-size: 28px; font-weight: bold; color: #005DAA; margin-bottom: 20px; }
    </style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data(file):
    return pd.read_csv(file)

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')
    return output.getvalue()

# --- SIDEBAR ---
st.sidebar.image("https://upload.wikimedia.org/wikipedia/en/thumb/e/e0/United_Airlines_Logo.svg/1200px-United_Airlines_Logo.svg.png", width=200)
st.sidebar.title("Gestión de Materiales")

file_stock = st.sidebar.file_uploader("1️⃣ Base de Stock (EZESTOCK_FINAL)", type=["csv"])
file_jobs = st.sidebar.file_uploader("2️⃣ Trabajos Programados (WPEZE_Filter)", type=["csv"])

if file_stock and file_jobs:
    df_stock = load_data(file_stock)
    df_jobs = load_data(file_jobs)

    # --- LIMPIEZA DE DATOS ---
    # Convertir a enteros y manejar columnas
    for c in ['QOH', 'required_part_quantity', 'planned_quantity']:
        if c in df_stock.columns:
            df_stock[c] = pd.to_numeric(df_stock[c], errors='coerce').fillna(0).astype(int)
    
    df_jobs['scheduled_date'] = pd.to_datetime(df_jobs['scheduled_date']).dt.date
    df_stock = df_stock.rename(columns={'planned_quantity': 'OPEN ORDERS', 'part_action': 'REQUISITO'})

    # --- BUSCADORES GLOBALES (SIDEBAR) ---
    st.sidebar.header("🔍 Buscadores por Comodín")
    wildcard_mne = st.sidebar.text_input("MNE / Dash8 (ej: 27-05)")
    wildcard_desc = st.sidebar.text_input("Descripción (ej: FILTER)")
    wildcard_me = st.sidebar.text_input("Part Number / m_e (ej: 75-25)")

    # Filtrado lógico de Stock
    df_f_stock = df_stock.copy()
    if wildcard_mne:
        df_f_stock = df_f_stock[df_f_stock['Mne_Dash8'].str.contains(wildcard_mne, case=False, na=False)]
    if wildcard_desc:
        df_f_stock = df_f_stock[df_f_stock['description'].str.contains(wildcard_desc, case=False, na=False)]
    if wildcard_me:
        df_f_stock = df_f_stock[df_f_stock['m_e'].str.contains(wildcard_me, case=False, na=False)]

    # Cálculo de Faltantes
    df_f_stock['faltante'] = (df_f_stock['required_part_quantity'] - df_f_stock['QOH']).clip(lower=0).astype(int)
    df_f_stock['estado'] = df_f_stock['faltante'].apply(lambda x: "⚠️ PEDIR" if x > 0 else "✅ OK")

    # Reordenar columnas solicitado
    view_cols = ['estado', 'm_e', 'description', 'QOH', 'required_part_quantity', 'faltante', 'OPEN ORDERS', 'REQUISITO', 'bin']

    modo = st.sidebar.radio("Ir a:", ["📅 Planificador y Trabajos", "📦 Stock General", "📈 Gráfico Interactivo"])

    # --- CONFIGURACIÓN DE TABLAS ---
    col_config = {
        "estado": st.column_config.TextColumn("ESTADO", width="small"),
        "m_e": st.column_config.TextColumn("PART NUMBER (m_e)", width="medium"),
        "description": st.column_config.TextColumn("DESCRIPCIÓN", width="large"),
        "QOH": st.column_config.NumberColumn("STOCK ACTUAL", format="%d"),
        "required_part_quantity": st.column_config.NumberColumn("REQ.", format="%d"),
        "faltante": st.column_config.NumberColumn("FALTANTE CALC.", format="%d"),
        "OPEN ORDERS": st.column_config.NumberColumn("OPEN ORDERS", format="%d"),
        "REQUISITO": st.column_config.TextColumn("REQUISITO"),
        "bin": st.column_config.TextColumn("BIN")
    }

    if modo == "📅 Planificador y Trabajos":
        st.markdown('<p class="main-header">📅 Trabajos Programados y Materiales</p>', unsafe_allow_html=True)
        fechas = sorted(df_jobs['scheduled_date'].unique())
        selected_date = st.date_input("Selecciona Fecha:", value=fechas[0] if fechas else None)

        # Mostrar Trabajos
        jobs_today = df_jobs[df_jobs['scheduled_date'] == selected_date]
        if not jobs_today.empty:
            st.subheader(f"Actividades para el {selected_date}")
            st.dataframe(jobs_today[['mne_number', 'mne_description', 'package_description']], use_container_width=True)

            # Mostrar Materiales para esos trabajos
            mne_today = jobs_today['mne_number'].unique()
            resumen_hoy = df_f_stock[df_f_stock['Mne_Dash8'].isin(mne_today)]
            
            st.subheader("📦 Materiales Necesarios para estas Actividades")
            if not resumen_hoy.empty:
                st.dataframe(resumen_hoy[view_cols], use_container_width=True, column_config=col_config)
            else:
                st.info("No se encontraron materiales para los MNE programados en esta fecha.")
        else:
            st.warning("No hay trabajos programados para la fecha seleccionada.")

    elif modo == "📦 Stock General":
        st.markdown('<p class="main-header">📦 Análisis de Inventario</p>', unsafe_allow_html=True)
        st.dataframe(df_f_stock[view_cols], use_container_width=True, column_config=col_config)

    elif modo == "📈 Gráfico Interactivo":
        st.markdown('<p class="main-header">📈 Comparativa de Stock Actual</p>', unsafe_allow_html=True)
        
        # El gráfico toma lo filtrado por los buscadores + una lista manual opcional
        lista_manual = st.text_input("Opcional: Agrega Part Numbers manuales separados por coma (ej: 75-2531-3-0088, ...)")
        
        df_plot = df_f_stock.copy()
        if lista_manual:
            mes_list = [x.strip() for x in lista_manual.split(',')]
            df_plot = df_plot[df_plot['m_e'].isin(mes_list)]

        if not df_plot.empty:
            # Limitamos a los primeros 25 para que el gráfico no se sature
            df_plot = df_plot.head(25)
            
            fig = go.Figure()
            # Barra de Stock Actual
            fig.add_trace(go.Bar(
                x=df_plot['m_e'], y=df_plot['QOH'],
                name='Stock (QOH)', marker_color='#005DAA',
                text=df_plot['QOH'], textposition='outside'
            ))
            # Marcador de Requisito (Icono interactivo)
            fig.add_trace(go.Scatter(
                x=df_plot['m_e'], y=df_plot['required_part_quantity'],
                mode='markers', name='Requerido',
                marker=dict(symbol='star', size=12, color='orange'),
                hovertemplate="Requerido: %{y}"
            ))

            fig.update_layout(
                title="Top 25 Items Filtrados: Stock Actual vs Requerido",
                xaxis_title="Part Number", yaxis_title="Cantidad",
                legend_title="Leyenda", barmode='group'
            )
            st.plotly_chart(fig, use_container_width=True)
            
            st.info("💡 El gráfico muestra los primeros 25 resultados según tus filtros de búsqueda (MNE, Descripción o m_e).")
        else:
            st.warning("No hay datos que coincidan con los filtros para generar el gráfico.")

else:
    st.info("👈 Sube los archivos CSV para comenzar.")
