import streamlit as st
import pandas as pd
import plotly.graph_objects as go

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
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str).str.strip()
    return df

# --- NORMALIZACIÓN DE CLAVES ---
# Ajusta estos flags según tu formato real
KEEP_LEADING_ZEROS = True         # Pon False si NO deben compararse con ceros a la izquierda
KEEP_HYPHENS = False              # Pon True si el guion '-' es significativo en tus MNE

def norm_mne_series(s: pd.Series) -> pd.Series:
    s = (s.astype(str)
           .str.upper()
           .str.strip()
           .str.replace(r"\s+", "", regex=True))
    if not KEEP_HYPHENS:
        s = s.str.replace(r"[^A-Z0-9]", "", regex=True)  # quita todo lo no alfanumérico
    # Si no queremos ceros a la izquierda, se remueven
    if not KEEP_LEADING_ZEROS:
        s = s.str.replace(r"^0+", "", regex=True)
    return s

# --- FUNCIÓN DE ESTILO ---
def apply_custom_styling(df):
    if df.empty:
        return df
    def highlight_logic(data):
        style_df = pd.DataFrame('', index=data.index, columns=data.columns)
        mask_critical = (data['faltante'] > data['QOH']) & (data['faltante'] > 0)
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
debug_mode = st.sidebar.checkbox("🛠️ Modo depuración", value=False)

if file_stock and file_jobs:
    df_stock = load_data(file_stock)
    df_jobs = load_data(file_jobs)

    # --- PREPARACIÓN DE DATOS ---
    # Normaliza claves para cruce
    df_stock['Mne_Dash8_norm'] = norm_mne_series(df_stock['Mne_Dash8'])
    df_jobs['mne_number_norm'] = norm_mne_series(df_jobs['mne_number'])

    # Conversión numérica
    cols_num = ['QOH', 'required_part_quantity', 'planned_quantity']
    for c in cols_num:
        if c in df_stock.columns:
            df_stock[c] = pd.to_numeric(df_stock[c], errors='coerce').fillna(0).astype(int)

    # Fechas y renombrados
    df_jobs['scheduled_date'] = pd.to_datetime(df_jobs['scheduled_date']).dt.date
    df_stock = df_stock.rename(columns={'planned_quantity': 'OPEN ORDERS', 'part_action': 'REQUISITO'})

    # --- FILTROS DE SIDEBAR (comodines) ---
    st.sidebar.header("🔍 Buscadores por Comodín")
    w_mne = st.sidebar.text_input("Filtrar por MNE (Dash8)")
    w_desc = st.sidebar.text_input("Filtrar por Descripción")
    w_me = st.sidebar.text_input("Filtrar por Part Number (m_e)")

    f_stock = df_stock.copy()
    if w_mne:
        f_stock = f_stock[f_stock['Mne_Dash8'].str.contains(w_mne, case=False, na=False)]
    if w_desc:
        f_stock = f_stock[f_stock['description'].str.contains(w_desc, case=False, na=False)]
    if w_me:
        f_stock = f_stock[f_stock['m_e'].str.contains(w_me, case=False, na=False)]

    # Métricas de faltantes y estado
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
        "REQUISITO": st.column_config.TextColumn("REQUISITO"),
        "bin": st.column_config.TextColumn("BIN"),
    }

    # --- TAB 1: PLANIFICADOR ---
    with tab1:
        st.markdown('<p class="main-header">Filtrado por Tareas Programadas</p>', unsafe_allow_html=True)
        fechas_disponibles = sorted(df_jobs['scheduled_date'].unique())
        sel_date = st.date_input("Selecciona Fecha del Calendario:", value=fechas_disponibles[0] if fechas_disponibles else None)

        jobs_day = df_jobs[df_jobs['scheduled_date'] == sel_date].copy() if sel_date else df_jobs.iloc[0:0].copy()

        st.subheader(f"Tareas Programadas para hoy ({len(jobs_day)})")
        st.dataframe(
            jobs_day[['mne_number', 'mne_description', 'package_description']],
            use_container_width=True, hide_index=True
        )

        st.subheader("📦 MATERIALES NECESARIOS PARA ESTAS TAREAS")
        # Cruce determinista con merge sobre claves normalizadas
        mats_for_day = f_stock.merge(
            jobs_day[['mne_number_norm']].drop_duplicates(),
            left_on='Mne_Dash8_norm',
            right_on='mne_number_norm',
            how='inner'
        )

        # Cálculo en subset
        if not mats_for_day.empty:
            mats_for_day['faltante'] = (mats_for_day['required_part_quantity'] - mats_for_day['QOH']).clip(lower=0).astype(int)
            mats_for_day['estado'] = mats_for_day['faltante'].apply(lambda x: "⚠️ PEDIR" if x > 0 else "✅ OK")
            styled_mat = apply_custom_styling(mats_for_day[v_cols])
            st.dataframe(styled_mat, use_container_width=True, column_config=col_config, hide_index=True)
            st.info(f"Se encontraron {len(mats_for_day)} materiales asociados a las tareas programadas.")
        else:
            if len(jobs_day) == 0:
                st.warning("No hay tareas programadas para la fecha seleccionada.")
            else:
                st.warning("No hay materiales en el almacén vinculados a los MNE de esta fecha.")

        # --- DEPURACIÓN OPCIONAL ---
        if debug_mode:
            st.markdown("### 🛠️ Depuración de claves")
            st.write("Muestras de stock (raw vs norm):", f_stock[['Mne_Dash8', 'Mne_Dash8_norm']].head(10))
            st.write("Muestras de jobs (raw vs norm):", jobs_day[['mne_number', 'mne_number_norm']].head(10))
            st.write("Unique stock MNE_norm:", f_stock['Mne_Dash8_norm'].nunique())
            st.write("Unique jobs MNE_norm (día):", jobs_day['mne_number_norm'].nunique())
            # Cuántos MNE del día están en el stock
            in_stock_mask = jobs_day['mne_number_norm'].isin(f_stock['Mne_Dash8_norm'])
            st.write("MNE del día presentes en stock:", jobs_day.loc[in_stock_mask, 'mne_number_norm'].unique().tolist())
            st.write("MNE del día ausentes en stock:", jobs_day.loc[~in_stock_mask, 'mne_number_norm'].unique().tolist())

    # --- TAB 2: STOCK COMPLETO ---
    with tab2:
        st.markdown('<p class="main-header">Inventario General (Filtros Sidebar)</p>', unsafe_allow_html=True)
        df_gen = f_stock[v_cols].reset_index(drop=True)
        if len(df_gen) > 800:
            st.warning(f"Mostrando {len(df_gen)} filas. Resaltado de color desactivado por volumen de datos.")
            st.dataframe(df_gen, use_container_width=True, column_config=col_config, hide_index=True)
        else:
            st.dataframe(apply_custom_styling(df_gen), use_container_width=True, column_config=col_config, hide_index=True)

    # --- TAB 3: GRÁFICO ---
    with tab3:
        st.markdown('<p class="main-header">Gráfico de Stock vs Requerido</p>', unsafe_allow_html=True)
        df_plot = f_stock.head(25)
        if not df_plot.empty:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=df_plot['m_e'], y=df_plot['QOH'], name='Stock Actual', marker_color='#005DAA'))
            fig.add_trace(go.Scatter(x=df_plot['m_e'], y=df_plot['required_part_quantity'], mode='markers',
                                     name='Requerido', marker=dict(symbol='star', size=12, color='orange')))
            fig.update_layout(xaxis_title="Part Number", yaxis_title="Cantidad", template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Sin datos para mostrar.")

else:
    st.info("👈 Por favor, carga los dos archivos CSV para iniciar.")
