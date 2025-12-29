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

# --- CARGA DE DATOS ---
@st.cache_data
def load_data(file):
    df = pd.read_csv(file)
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str).str.strip()
    return df

# --- NORMALIZACIÓN DE CLAVES (evita "NAN" como coincidencia) ---
def norm_mne_series(s: pd.Series) -> pd.Series:
    return (
        s.fillna("")
         .astype(str)
         .str.upper()
         .str.strip()
         .str.replace(r"\s+", "", regex=True)
         .replace("NAN", "")
    )

# --- ESTILO CONDICIONAL ---
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
st.sidebar.image(
    "https://upload.wikimedia.org/wikipedia/en/thumb/e/e0/United_Airlines_Logo.svg/1200px-United_Airlines_Logo.svg.png",
    width=200
)
st.sidebar.title("Material Control")

file_stock = st.sidebar.file_uploader("1️⃣ EZESTOCK_FINAL (CSV)", type=["csv"])
file_jobs = st.sidebar.file_uploader("2️⃣ WPEZE_Filter (CSV)", type=["csv"])
debug_mode = st.sidebar.checkbox("🛠️ Modo depuración", value=False)

# --- APP ---
if file_stock and file_jobs:
    # Datos base
    df_stock = load_data(file_stock)
    df_jobs = load_data(file_jobs)

    # Conversión numérica
    cols_num = ['QOH', 'required_part_quantity', 'planned_quantity']
    for c in cols_num:
        if c in df_stock.columns:
            df_stock[c] = pd.to_numeric(df_stock[c], errors='coerce').fillna(0).astype(int)

    # Fechas y renombres
    if 'scheduled_date' in df_jobs.columns:
        df_jobs['scheduled_date'] = pd.to_datetime(df_jobs['scheduled_date'], errors='coerce').dt.date
    df_stock = df_stock.rename(columns={'planned_quantity': 'OPEN ORDERS', 'part_action': 'REQUISITO'})

    # Filtros de inventario (no descartan piezas sin MNE)
    st.sidebar.header("🔍 Buscadores por Comodín")
    w_mne = st.sidebar.text_input("Filtrar por MNE (Dash8)")
    w_desc = st.sidebar.text_input("Filtrar por Descripción")
    w_me = st.sidebar.text_input("Filtrar por Part Number (m_e)")

    f_stock = df_stock.copy()
    if 'Mne_Dash8' in f_stock.columns and w_mne:
        f_stock = f_stock[f_stock['Mne_Dash8'].str.contains(w_mne, case=False, na=False)]
    if 'description' in f_stock.columns and w_desc:
        f_stock = f_stock[f_stock['description'].str_contains(w_desc, case=False, na=False)]
    if 'description' in f_stock.columns and w_desc and not 'str_contains' in dir(pd.Series.str):
        # Fallback para algunas versiones de pandas: usar str.contains
        f_stock = f_stock[f_stock['description'].str.contains(w_desc, case=False, na=False)]
    if 'm_e' in f_stock.columns and w_me:
        f_stock = f_stock[f_stock['m_e'].str.contains(w_me, case=False, na=False)]

    # Métricas de inventario
    if {'required_part_quantity', 'QOH'}.issubset(f_stock.columns):
        f_stock['faltante'] = (f_stock['required_part_quantity'] - f_stock['QOH']).clip(lower=0).astype(int)
        f_stock['estado'] = f_stock['faltante'].apply(lambda x: "⚠️ PEDIR" if x > 0 else "✅ OK")
    else:
        f_stock['faltante'] = 0
        f_stock['estado'] = "✅ OK"

    # Columnas visibles
    v_cols = [
        'estado', 'm_e', 'description', 'QOH', 'required_part_quantity',
        'faltante', 'OPEN ORDERS', 'REQUISITO', 'bin'
    ]
    v_cols = [c for c in v_cols if c in f_stock.columns]

    # Pestañas
    tab1, tab2, tab3 = st.tabs(["📅 PLANIFICADOR DIARIO", "📦 STOCK COMPLETO", "📈 GRÁFICO"])

    col_config = {
        "estado": st.column_config.TextColumn("ESTADO", width="small"),
        "m_e": st.column_config.TextColumn("PART NUMBER", width="medium"),
        "description": st.column_config.TextColumn("DESCRIPCIÓN", width="large"),
        "QOH": st.column_config.NumberColumn("STOCK ACT.", format="%d"),
        "required_part_quantity": st.column_config.NumberColumn("REQ.", format="%d"),
        "faltante": st.column_config.NumberColumn("FALTANTE", format="%d"),
        "OPEN ORDERS": st.column_config.NumberColumn("O. ORDERS", format="%d"),
        "REQUISITO": st.column_config.TextColumn("REQUISITO"),
        "bin": st.column_config.TextColumn("BIN"),
    }

    # --- TAB 1: PLANIFICADOR ---
    with tab1:
        st.markdown('<p class="main-header">Filtrado por Tareas Programadas</p>', unsafe_allow_html=True)

        fechas_disponibles = sorted(df_jobs['scheduled_date'].dropna().unique()) if 'scheduled_date' in df_jobs.columns else []
        sel_date = st.date_input(
            "Selecciona Fecha del Calendario:",
            value=fechas_disponibles[0] if len(fechas_disponibles) > 0 else None
        )

        jobs_day = df_jobs[df_jobs['scheduled_date'] == sel_date].copy() if sel_date and 'scheduled_date' in df_jobs.columns else df_jobs.iloc[0:0].copy()

        # Normalización SOLO para planificador
        jobs_day['mne_number_norm'] = norm_mne_series(jobs_day['mne_number']) if 'mne_number' in jobs_day.columns else ""
        f_stock_plan = df_stock.copy()
        f_stock_plan['Mne_Dash8_norm'] = norm_mne_series(f_stock_plan['Mne_Dash8']) if 'Mne_Dash8' in f_stock_plan.columns else ""

        # Claves válidas en planificador
        jobs_day = jobs_day[jobs_day['mne_number_norm'] != ""]
        f_stock_plan = f_stock_plan[f_stock_plan['Mne_Dash8_norm'] != ""]

        # Mostrar trabajos del día
        st.subheader(f"Tareas Programadas para hoy ({len(jobs_day)})")
        show_jobs_cols = [c for c in ['mne_number', 'mne_description', 'package_description'] if c in jobs_day.columns]
        if len(show_jobs_cols) > 0:
            st.dataframe(jobs_day[show_jobs_cols], use_container_width=True, hide_index=True)
        else:
            st.info("No hay columnas de descripción de tareas disponibles para mostrar.")

        # Filtrar materiales por coincidencia exacta
        st.subheader("📦 MATERIALES NECESARIOS PARA ESTAS TAREAS")
        mne_set = set(jobs_day['mne_number_norm'].tolist())
        if len(mne_set) == 0:
            mats_for_day = f_stock_plan.iloc[0:0].copy()
        else:
            mats_for_day = f_stock_plan[f_stock_plan['Mne_Dash8_norm'].isin(mne_set)].copy()

        if not mats_for_day.empty:
            if {'required_part_quantity', 'QOH'}.issubset(mats_for_day.columns):
                mats_for_day['faltante'] = (mats_for_day['required_part_quantity'] - mats_for_day['QOH']).clip(lower=0).astype(int)
                mats_for_day['estado'] = mats_for_day['faltante'].apply(lambda x: "⚠️ PEDIR" if x > 0 else "✅ OK")
            show_cols = [c for c in v_cols if c in mats_for_day.columns]
            styled_mat = apply_custom_styling(mats_for_day[show_cols]) if len(show_cols) > 0 else mats_for_day
            st.dataframe(styled_mat, use_container_width=True, column_config=col_config, hide_index=True)
            st.info(f"Se encontraron {len(mats_for_day)} materiales asociados a las tareas programadas.")
        else:
            if len(jobs_day) == 0:
                st.warning("No hay tareas programadas para la fecha seleccionada.")
            else:
                st.warning("No hay materiales en el almacén vinculados a los MNE de esta fecha.")

        # Depuración opcional
        if debug_mode:
            st.markdown("### 🛠️ Depuración de claves")
            if 'Mne_Dash8' in f_stock_plan.columns:
                st.write("Muestras stock (raw vs norm):", f_stock_plan[['Mne_Dash8', 'Mne_Dash8_norm']].head(10))
            if 'mne_number' in jobs_day.columns:
                st.write("Muestras jobs (raw vs norm):", jobs_day[['mne_number', 'mne_number_norm']].head(10))
            st.write("Blancos stock Mne_Dash8_norm:", int((f_stock_plan['Mne_Dash8_norm'] == '').sum()))
            st.write("Blancos jobs mne_number_norm:", int((jobs_day['mne_number_norm'] == '').sum()))
            st.write("Unique stock MNE_norm:", f_stock_plan['Mne_Dash8_norm'].nunique())
            st.write("Unique jobs MNE_norm (día):", jobs_day['mne_number_norm'].nunique())
            inter = set(f_stock_plan['Mne_Dash8_norm']).intersection(mne_set)
            st.write("Intersección tamaño:", len(inter))
            st.write("Ejemplos en intersección:", list(inter)[:10])

    # --- TAB 2: STOCK COMPLETO ---
    with tab2:
        st.markdown('<p class="main-header">Inventario General (Filtros Sidebar)</p>', unsafe_allow_html=True)
        if len(v_cols) == 0:
            st.warning("No hay columnas compatibles para mostrar el inventario.")
        else:
            df_gen = f_stock[v_cols].reset_index(drop=True)
            if len(df_gen) > 800:
                st.warning(f"Mostrando {len(df_gen)} filas. Resaltado de color desactivado por volumen de datos.")
                st.dataframe(df_gen, use_container_width=True, column_config=col_config, hide_index=True)
            else:
                st.dataframe(apply_custom_styling(df_gen), use_container_width=True, column_config=col_config, hide_index=True)

    # --- TAB 3: GRÁFICO ---
    with tab3:
        st.markdown('<p class="main-header">Gráfico de Stock vs Requerido</p>', unsafe_allow_html=True)
        needed_cols = {'m_e', 'QOH', 'required_part_quantity'}
        if needed_cols.issubset(f_stock.columns):
            df_plot = f_stock.head(25)
            if not df_plot.empty:
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=df_plot['m_e'], y=df_plot['QOH'],
                    name='Stock Actual', marker_color='#005DAA'
                ))
                fig.add_trace(go.Scatter(
                    x=df_plot['m_e'], y=df_plot['required_part_quantity'],
                    mode='markers', name='Requerido',
                    marker=dict(symbol='star', size=12, color='orange')
                ))
                fig.update_layout(xaxis_title="Part Number", yaxis_title="Cantidad", template="plotly_white")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("Sin datos para graficar.")
        else:
            st.warning("Faltan columnas necesarias para el gráfico: m_e, QOH y required_part_quantity.")

else:
    st.info("👈 Por favor, carga los dos archivos CSV para iniciar.")
