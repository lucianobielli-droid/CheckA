import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from io import BytesIO

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="United Airlines - Materials Dashboard", layout="wide")

st.markdown("""
    <style>
    .stDataFrame th { white-space: normal !important; }
    .main-header { font-size: 24px; font-weight: bold; color: #005DAA; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data(file):
    df = pd.read_csv(file)
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str).str.strip()
    return df

# --- ESTILO CONDICIONAL ---
def apply_custom_styling(df):
    if df.empty:
        return df
    def highlight_logic(data):
        style_df = pd.DataFrame('', index=data.index, columns=data.columns)
        # Rojo: Faltante > Stock
        mask_critical = (data['faltante'] > data['QOH']) & (data['faltante'] > 0)
        # Amarillo: Solo faltante
        mask_warning = (data['faltante'] > 0) & (~mask_critical)
        
        critical_style = 'background-color: #ffcccc; color: #b30000; font-weight: bold;'
        warning_style = 'background-color: #fff4e5;'
        
        for col in style_df.columns:
            style_df.loc[mask_critical, col] = critical_style
            style_df.loc[mask_warning, col] = warning_style
        return style_df
    
    if len(df) > 800:
        return df
    return df.style.apply(highlight_logic, axis=None)

# --- SIDEBAR ---
st.sidebar.image("https://upload.wikimedia.org/wikipedia/en/thumb/e/e0/United_Airlines_Logo.svg/1200px-United_Airlines_Logo.svg.png", width=200)
st.sidebar.title("Material Control")

file_stock = st.sidebar.file_uploader("1️⃣ EZESTOCK_FINAL (CSV)", type=["csv"])
file_jobs = st.sidebar.file_uploader("2️⃣ WPEZE_Filter (CSV)", type=["csv"])

if file_stock and file_jobs:
    df_stock = load_data(file_stock)
    df_jobs = load_data(file_jobs)

    # --- PREPARACIÓN DATOS ---
    cols_num = ['QOH', 'required_part_quantity', 'planned_quantity']
    for c in cols_num:
        if c in df_stock.columns:
            df_stock[c] = pd.to_numeric(df_stock[c], errors='coerce').fillna(0).astype(int)

    df_jobs['scheduled_date'] = pd.to_datetime(df_jobs['scheduled_date']).dt.date
    df_stock = df_stock.rename(columns={'planned_quantity': 'OPEN ORDERS', 'part_action': 'REQUISITO'})

    # Filtros Globales (Sidebar)
    st.sidebar.header("🔍 Buscadores por Comodín")
    w_mne = st.sidebar.text_input("Filtrar por MNE (Dash8)")
    w_desc = st.sidebar.text_input("Filtrar por Descripción")
    w_me = st.sidebar.text_input("Filtrar por Part Number (m_e)")

    # Stock Maestro filtrado por sidebar
    f_stock = df_stock.copy()
    if w_mne:
        f_stock = f_stock[f_stock['Mne_Dash8'].str.contains(w_mne, case=False, na=False)]
    if w_desc:
        f_stock = f_stock[f_stock['description'].str.contains(w_desc, case=False, na=False)]
    if w_me:
        f_stock = f_stock[f_stock['m_e'].str.contains(w_me, case=False, na=False)]

    # Cálculo de métricas
    f_stock['faltante'] = (f_stock['required_part_quantity'] - f_stock['QOH']).clip(lower=0).astype(int)
    f_stock['estado'] = f_stock['faltante'].apply(lambda x: "⚠️ PEDIR" if x > 0 else "✅ OK")

    v_cols = ['estado', 'm_e', 'description', 'QOH', 'required_part_quantity', 'faltante', 'OPEN ORDERS', 'REQUISITO', 'bin']
    v_cols = [c for c in v_cols if c in f_stock.columns]

    # --- PESTAÑAS ---
    tab1, tab2, tab3 = st.tabs(["📅 PLANIFICADOR DIARIO", "📦 STOCK COMPLETO", "📈 GRÁFICO"])

    col_config = {
        "estado": st.column_config.TextColumn("ESTADO", width="small"),
        "m_e": st.column_config.TextColumn("PART NUMBER", width="medium"),
        "description": st.column_config.TextColumn("DESCRIPCIÓN", width="large"),
        "QOH": st.column_config.NumberColumn("STOCK ACT.", format="%d"),
        "required_part_quantity": st.column_config.NumberColumn("REQ.", format="%d"),
        "faltante": st.column_config.NumberColumn("FALTANTE", format="%d"),
        "OPEN ORDERS": st.column_config.NumberColumn("O. ORDERS", format="%d"),
    }

    # --- TAB 1: PLANIFICADOR (CORREGIDO) ---
    with tab1:
        st.markdown('<p class="main-header">Materiales para Tareas del Día</p>', unsafe_allow_html=True)
        
        fechas_disponibles = sorted(df_jobs['scheduled_date'].unique())
        sel_date = st.date_input("Selecciona Fecha:", value=fechas_disponibles[0] if fechas_disponibles else None)

        # 1. Obtener tareas del día
        jobs_today = df_jobs[df_jobs['scheduled_date'] == sel_date].copy()
        
        st.subheader(f"Tareas Programadas ({len(jobs_today)})")
        st.dataframe(jobs_today[['mne_number', 'mne_description', 'package_description']], use_container_width=True, hide_index=True)

        # 2. Filtrado Estricto de Materiales
        st.subheader("📦 MATERIALES NECESARIOS")
        
        # Extraemos la lista de MNEs únicos del día (limpios)
        mne_list = jobs_today['mne_number'].dropna().unique().tolist()
        mne_list = [str(x).strip() for x in mne_list if str(x).strip() != ""]

        if mne_list:
            # Filtramos el stock maestro para que SOLAMENTE contenga los MNE de la lista
            # Esto corrige el problema de "mostrar todo el stock"
            mat_plan = f_stock[f_stock['Mne_Dash8'].isin(mne_list)].reset_index(drop=True)

            if not mat_plan.empty:
                st.info(f"Se encontraron {len(mat_plan)} materiales asociados a los MNE del día.")
                st.dataframe(apply_custom_styling(mat_plan[v_cols]), use_container_width=True, column_config=col_config, hide_index=True)
            else:
                st.warning("No se encontraron materiales en stock para los MNE seleccionados.")
        else:
            st.info("No hay códigos MNE válidos en las tareas para esta fecha.")

    # --- TAB 2: STOCK COMPLETO ---
    with tab2:
        st.markdown('<p class="main-header">Inventario General</p>', unsafe_allow_html=True)
        df_gen = f_stock[v_cols].reset_index(drop=True)
        if len(df_gen) > 800:
            st.warning("Vista masiva: Resaltado desactivado.")
            st.dataframe(df_gen, use_container_width=True, column_config=col_config, hide_index=True)
        else:
            st.dataframe(apply_custom_styling(df_gen), use_container_width=True, column_config=col_config, hide_index=True)

    # --- TAB 3: GRÁFICO ---
    with tab3:
        st.markdown('<p class="main-header">Top 25 Items Filtrados</p>', unsafe_allow_html=True)
        df_plot = f_stock.head(25)
        if not df_plot.empty:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=df_plot['m_e'], y=df_plot['QOH'], name='Stock Actual', marker_color='#005DAA'))
            fig.add_trace(go.Scatter(x=df_plot['m_e'], y=df_plot['required_part_quantity'], mode='markers', name='Requerido', marker=dict(symbol='star', size=12, color='orange')))
            fig.update_layout(template="plotly_white", margin=dict(t=10))
            st.plotly_chart(fig, use_container_width=True)

else:
    st.info("👈 Carga los archivos para activar el tablero.")
