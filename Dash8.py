import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="United Airlines - Materials Dashboard", layout="wide")

# Inyección de CSS para forzar el ajuste de encabezados y estilos de tabla
st.markdown("""
    <style>
    .stDataFrame th { white-space: normal !important; vertical-align: bottom !important; }
    .main-header { font-size: 26px; font-weight: bold; color: #005DAA; }
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

# --- CARGA DE ARCHIVOS ---
st.sidebar.image("https://upload.wikimedia.org/wikipedia/en/thumb/e/e0/United_Airlines_Logo.svg/1200px-United_Airlines_Logo.svg.png", width=200)
st.sidebar.title("Control de Materiales")

file_stock = st.sidebar.file_uploader("1️⃣ Base de Stock (EZESTOCK_FINAL)", type=["csv"])
file_jobs = st.sidebar.file_uploader("2️⃣ Trabajos Programados (WPEZE_Filter)", type=["csv"])

if file_stock and file_jobs:
    df_stock = load_data(file_stock)
    df_jobs = load_data(file_jobs)

    # --- LIMPIEZA Y PREPARACIÓN ---
    # Limpiar llaves de cruce
    df_stock['Mne_Dash8'] = df_stock['Mne_Dash8'].astype(str).str.strip()
    df_jobs['mne_number'] = df_jobs['mne_number'].astype(str).str.strip()
    
    # Formatear números a enteros
    cols_num = ['QOH', 'required_part_quantity', 'planned_quantity']
    for c in cols_num:
        if c in df_stock.columns:
            df_stock[c] = pd.to_numeric(df_stock[c], errors='coerce').fillna(0).astype(int)

    df_jobs['scheduled_date'] = pd.to_datetime(df_jobs['scheduled_date']).dt.date
    
    # Renombrar columnas según solicitud
    df_stock = df_stock.rename(columns={'planned_quantity': 'OPEN ORDERS', 'part_action': 'REQUISITO'})
    
    # --- FILTROS GLOBALES (SIDEBAR) ---
    st.sidebar.header("🔍 Buscadores por Comodín")
    w_mne = st.sidebar.text_input("Filtrar por MNE (Dash8)")
    w_desc = st.sidebar.text_input("Filtrar por Descripción")
    w_me = st.sidebar.text_input("Filtrar por Part Number (m_e)")

    # Lógica de filtrado de Stock
    f_stock = df_stock.copy()
    if w_mne:
        f_stock = f_stock[f_stock['Mne_Dash8'].str.contains(w_mne, case=False, na=False)]
    if w_desc:
        f_stock = f_stock[f_stock['description'].str.contains(w_desc, case=False, na=False)]
    if w_me:
        f_stock = f_stock[f_stock['m_e'].str.contains(w_me, case=False, na=False)]

    # Cálculo de faltante
    f_stock['faltante'] = (f_stock['required_part_quantity'] - f_stock['QOH']).clip(lower=0).astype(int)
    f_stock['estado'] = f_stock['faltante'].apply(lambda x: "⚠️ PEDIR" if x > 0 else "✅ OK")

    # Orden de columnas solicitado
    v_cols = ['estado', 'm_e', 'description', 'QOH', 'required_part_quantity', 'faltante', 'OPEN ORDERS', 'REQUISITO', 'bin']

    # --- NAVEGACIÓN ---
    tab1, tab2, tab3 = st.tabs(["📅 Planificador", "📦 Stock General", "📈 Gráfico Interactivo"])

    # --- CONFIGURACIÓN DE TABLAS (Sin decimales y ajuste de ancho) ---
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

    # Función de resaltado dinámico
    def highlight_rows(row):
        style = [''] * len(row)
        # Resaltado CRÍTICO: Faltante > Stock Actual
        if row['faltante'] > row['QOH'] and row['faltante'] > 0:
            return ['background-color: #ffb3b3; color: black; font-weight: bold'] * len(row)
        # Resaltado NORMAL: Solo necesita pedir
        elif row['estado'] == "⚠️ PEDIR":
            return ['background-color: #fff2cc'] * len(row)
        return style

    # --- TAB 1: PLANIFICADOR ---
    with tab1:
        st.markdown('<p class="main-header">📅 Trabajos Programados y Materiales</p>', unsafe_allow_html=True)
        fechas = sorted(df_jobs['scheduled_date'].unique())
        sel_date = st.date_input("Selecciona Fecha del Calendario:", value=fechas[0] if fechas else None)

        # 1. Mostrar Trabajos del Día
        jobs_day = df_jobs[df_jobs['scheduled_date'] == sel_date].copy()
        
        # Filtrar trabajos también por descripción si el buscador está activo
        if w_desc:
            jobs_day = jobs_day[jobs_day['mne_description'].str.contains(w_desc, case=False, na=False)]

        st.subheader(f"Actividades Programadas ({len(jobs_day)})")
        st.dataframe(jobs_day[['mne_number', 'mne_description', 'package_description']], use_container_width=True)

        # 2. Mostrar Materiales Necesarios (Cruzando con MNE de los trabajos)
        st.subheader("📦 Materiales Requeridos para estas Actividades")
        mne_list = jobs_day['mne_number'].unique()
        
        # Filtramos la base de stock por los MNE del día y aplicamos los buscadores de la sidebar
        mat_hoy = f_stock[f_stock['Mne_Dash8'].isin(mne_list)].copy()

        if not mat_hoy.empty:
            st.dataframe(mat_hoy[v_cols].style.apply(highlight_rows, axis=1), 
                         use_container_width=True, column_config=col_config)
        else:
            st.info("No se encontraron materiales cargados en stock para los MNE de esta fecha.")

    # --- TAB 2: STOCK GENERAL ---
    with tab2:
        st.markdown('<p class="main-header">📦 Análisis Completo de Inventario</p>', unsafe_allow_html=True)
        st.dataframe(f_stock[v_cols].style.apply(highlight_rows, axis=1), 
                     use_container_width=True, column_config=col_config)

    # --- TAB 3: GRÁFICO INTERACTIVO ---
    with tab3:
        st.markdown('<p class="main-header">📈 Comparativa de Disponibilidad</p>', unsafe_allow_html=True)
        
        # El gráfico usa lo que ya está filtrado por los buscadores
        df_plot = f_stock.copy().head(30) # Limitamos a 30 para legibilidad
        
        if not df_plot.empty:
            fig = go.Figure()
            
            # Barras de Stock
            fig.add_trace(go.Bar(
                x=df_plot['m_e'], y=df_plot['QOH'],
                name='Stock Actual (QOH)', marker_color='#005DAA',
                hovertemplate="PN: %{x}<br>Stock: %{y}<extra></extra>"
            ))
            
            # Iconos de Requerimiento (Estrellas)
            fig.add_trace(go.Scatter(
                x=df_plot['m_e'], y=df_plot['required_part_quantity'],
                mode='markers', name='Requerido (Target)',
                marker=dict(symbol='star', size=14, color='#FF8C00', line=dict(width=1, color='black')),
                hovertemplate="PN: %{x}<br>Necesitas: %{y}<extra></extra>"
            ))

            fig.update_layout(
                title="Top 30 Items (Filtrados por Buscadores)",
                xaxis_title="Part Number (m_e)", yaxis_title="Cantidad",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                template="plotly_white", margin=dict(t=80)
            )
            st.plotly_chart(fig, use_container_width=True)
            st.caption("Nota: El gráfico se actualiza en tiempo real con los buscadores de la barra lateral.")
        else:
            st.warning("Aplica un filtro o busca un material para generar el gráfico.")

else:
    st.info("👈 Por favor, carga los dos archivos CSV para habilitar el tablero.")
