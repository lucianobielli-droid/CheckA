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
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    </style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data(file):
    df = pd.read_csv(file)
    # Limpieza profunda de strings para evitar fallos de cruce
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str).str.strip()
    return df

# --- FUNCIÓN DE ESTILO OPTIMIZADA ---
def apply_custom_styling(df):
    """Aplica estilos de color de forma segura y eficiente."""
    if df.empty:
        return df
    
    def highlight_logic(data):
        # Dataframe de estilos vacío
        style_df = pd.DataFrame('', index=data.index, columns=data.columns)
        
        # Máscaras lógicas
        # CRÍTICO: Faltante > Stock disponible (y hay faltante)
        mask_critical = (data['faltante'] > data['QOH']) & (data['faltante'] > 0)
        # NORMAL: Solo hay faltante
        mask_warning = (data['faltante'] > 0) & (~mask_critical)
        
        # Aplicar colores
        critical_style = 'background-color: #ffcccc; color: #b30000; font-weight: bold;'
        warning_style = 'background-color: #fff4e5;'
        
        for col in style_df.columns:
            style_df.loc[mask_critical, col] = critical_style
            style_df.loc[mask_warning, col] = warning_style
            
        return style_df

    # Solo aplicamos estilo si el dataframe no es masivo para evitar StreamlitAPIException
    if len(df) > 800:
        return df # Retorna sin estilo si es muy grande para seguridad
    
    return df.style.apply(highlight_logic, axis=None)

# --- CARGA DE ARCHIVOS ---
st.sidebar.image("https://upload.wikimedia.org/wikipedia/en/thumb/e/e0/United_Airlines_Logo.svg/1200px-United_Airlines_Logo.svg.png", width=200)
st.sidebar.title("Material Control")

file_stock = st.sidebar.file_uploader("1️⃣ EZESTOCK_FINAL (CSV)", type=["csv"])
file_jobs = st.sidebar.file_uploader("2️⃣ WPEZE_Filter (CSV)", type=["csv"])

if file_stock and file_jobs:
    df_stock = load_data(file_stock)
    df_jobs = load_data(file_jobs)

    # --- PREPARACIÓN DE DATOS ---
    # Limpiar llaves de unión (MNE)
    df_stock['Mne_Dash8'] = df_stock['Mne_Dash8'].astype(str).str.strip()
    df_jobs['mne_number'] = df_jobs['mne_number'].astype(str).str.strip()
    
    # Convertir números
    cols_num = ['QOH', 'required_part_quantity', 'planned_quantity']
    for c in cols_num:
        if c in df_stock.columns:
            df_stock[c] = pd.to_numeric(df_stock[c], errors='coerce').fillna(0).astype(int)

    df_jobs['scheduled_date'] = pd.to_datetime(df_jobs['scheduled_date']).dt.date
    df_stock = df_stock.rename(columns={'planned_quantity': 'OPEN ORDERS', 'part_action': 'REQUISITO'})

    # --- FILTROS DE SIDEBAR ---
    st.sidebar.header("🔍 Buscadores por Comodín")
    w_mne = st.sidebar.text_input("Filtrar por MNE (Dash8)")
    w_desc = st.sidebar.text_input("Filtrar por Descripción")
    w_me = st.sidebar.text_input("Filtrar por Part Number (m_e)")

    # Stock maestro (f_stock) filtrado por sidebar
    f_stock = df_stock.copy()
    if w_mne:
        f_stock = f_stock[f_stock['Mne_Dash8'].str.contains(w_mne, case=False, na=False)]
    if w_desc:
        f_stock = f_stock[f_stock['description'].str.contains(w_desc, case=False, na=False)]
    if w_me:
        f_stock = f_stock[f_stock['m_e'].str.contains(w_me, case=False, na=False)]

    # Cálculo de Faltantes
    f_stock['faltante'] = (f_stock['required_part_quantity'] - f_stock['QOH']).clip(lower=0).astype(int)
    f_stock['estado'] = f_stock['faltante'].apply(lambda x: "⚠️ PEDIR" if x > 0 else "✅ OK")
    
    v_cols = ['estado', 'm_e', 'description', 'QOH', 'required_part_quantity', 'faltante', 'OPEN ORDERS', 'REQUISITO', 'bin']

    # --- PESTAÑAS ---
    tab1, tab2, tab3 = st.tabs(["📅 PLANIFICADOR DIARIO", "📦 STOCK COMPLETO", "📈 GRÁFICO"])

    col_config = {
        "estado": st.column_config.TextColumn("ESTADO", width="small"),
        "m_e": st.column_config.TextColumn("PART NUMBER", width="medium"),
        "description": st.column_config.TextColumn("DESCRIPCIÓN", width="large"),
        "QOH": st.column_config.NumberColumn("STOCK ACT.", format="%d"),
        "faltante": st.column_config.NumberColumn("FALTANTE", format="%d"),
        "OPEN ORDERS": st.column_config.NumberColumn("O. ORDERS", format="%d"),
    }

    with tab1:
        st.markdown('<p class="main-header">Filtrado por Tareas Programadas</p>', unsafe_allow_html=True)
        fechas_disponibles = sorted(df_jobs['scheduled_date'].unique())
        sel_date = st.date_input("Selecciona Fecha del Calendario:", 
                                 value=fechas_disponibles[0] if fechas_disponibles else None)

        # 1. Trabajos del día seleccionado
        jobs_day = df_jobs[df_jobs['scheduled_date'] == sel_date].copy()
        st.subheader(f"Tareas Programadas para hoy ({len(jobs_day)})")
        st.dataframe(jobs_day[['mne_number', 'mne_description', 'package_description']], 
                     use_container_width=True, hide_index=True)

        # 2. Materiales cruce MNE exacto
        st.subheader("📦 MATERIALES NECESARIOS PARA ESTAS TAREAS")
        mne_list_del_dia = jobs_day['mne_number'].unique().tolist()
        
        # FILTRO CRÍTICO: Solo piezas cuyo Mne_Dash8 esté en la lista de tareas del día
        mat_hoy = f_stock[f_stock['Mne_Dash8'].isin(mne_list_del_dia)].reset_index(drop=True)

        if not mat_hoy.empty:
            st.info(f"Se encontraron {len(mat_hoy)} materiales asociados a las tareas programadas.")
            # Aplicar estilo solo a este subset (seguro contra crashes)
            styled_mat = apply_custom_styling(mat_hoy[v_cols])
            st.dataframe(styled_mat, use_container_width=True, column_config=col_config, hide_index=True)
        else:
            st.warning("No hay materiales en el almacén vinculados a los MNE de esta fecha.")

    with tab2:
        st.markdown('<p class="main-header">Inventario General (Filtros Sidebar)</p>', unsafe_allow_html=True)
        df_gen = f_stock[v_cols].reset_index(drop=True)
        
        # Seguridad: Si es muy grande, avisamos que no habrá color
        if len(df_gen) > 800:
            st.warning(f"Mostrando {len(df_gen)} filas. Resaltado de color desactivado por volumen de datos. Use los buscadores para ver piezas específicas con color.")
            st.dataframe(df_gen, use_container_width=True, column_config=col_config, hide_index=True)
        else:
            st.dataframe(apply_custom_styling(df_gen), use_container_width=True, column_config=col_config, hide_index=True)

    with tab3:
        st.markdown('<p class="main-header">Gráfico de Stock vs Requerido</p>', unsafe_allow_html=True)
        df_plot = f_stock.head(25) # Top 25
        if not df_plot.empty:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=df_plot['m_e'], y=df_plot['QOH'], name='Stock Actual', marker_color='#005DAA'))
            fig.add_trace(go.Scatter(x=df_plot['m_e'], y=df_plot['required_part_quantity'], mode='markers', 
                                     name='Requerido', marker=dict(symbol='star', size=12, color='orange')))
            fig.update_layout(xaxis_title="Part Number", yaxis_title="Cantidad", template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)

else:
    st.info("👈 Por favor, carga los dos archivos CSV para iniciar.")
