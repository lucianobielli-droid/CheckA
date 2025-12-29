import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pandas.io.formats.style import Styler  # Import correcto

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

# --- ESTILO CONDICIONAL ---
def apply_custom_styling(df):
    # Evita fallar si df ya es un Styler o está vacío
    if isinstance(df, Styler):
        return df
    if hasattr(df, "empty") and df.empty:
        return df

    def highlight_logic(data):
        style_df = pd.DataFrame('', index=data.index, columns=data.columns)
        if {'faltante','QOH'}.issubset(data.columns):
            mask_critical = (data['faltante'] > data['QOH']) & (data['faltante'] > 0)
            mask_warning = (data['faltante'] > 0) & (~mask_critical)
            critical_style = 'background-color: #ffcccc; color: #b30000; font-weight: bold;'
            warning_style = 'background-color: #fff4e5;'
            for col in style_df.columns:
                style_df.loc[mask_critical, col] = critical_style
                style_df.loc[mask_warning, col] = warning_style
        return style_df

    # Evitar estilos en grandes volúmenes por rendimiento
    if len(df) > 800:
        return df
    return df.style.apply(highlight_logic, axis=None)

# --- SIDEBAR ---
st.sidebar.title("Material Control")
file_stock = st.sidebar.file_uploader("1️⃣ EZESTOCK_FINAL (CSV)", type=["csv"])
file_jobs = st.sidebar.file_uploader("2️⃣ WPEZE_Filter (CSV)", type=["csv"])
debug_mode = st.sidebar.checkbox("🛠️ Modo depuración", value=False)

# --- APP ---
if file_stock and file_jobs:
    df_stock = load_data(file_stock)
    df_jobs = load_data(file_jobs)

    # --- PREPARACIÓN GENERAL ---
    for c in ['QOH','required_part_quantity','planned_quantity','Intransit_qty']:
        if c in df_stock.columns:
            df_stock[c] = pd.to_numeric(df_stock[c], errors='coerce').fillna(0).astype(int)

    if 'scheduled_date' in df_jobs.columns:
        df_jobs['scheduled_date'] = pd.to_datetime(df_jobs['scheduled_date'], errors='coerce').dt.date

    # Renombrar para consistencia
    df_stock = df_stock.rename(columns={'planned_quantity': 'OPEN ORDERS', 'part_action': 'REQUISITO'})

    # --- FILTROS INVENTARIO ---
    st.sidebar.header("🔍 Buscadores por Comodín")
    w_mne = st.sidebar.text_input("Filtrar por MNE (Dash8)")
    w_desc = st.sidebar.text_input("Filtrar por Descripción")
    w_me = st.sidebar.text_input("Filtrar por Part Number (m_e)")

    f_stock = df_stock.copy()
    if 'Mne_Dash8' in f_stock.columns and w_mne:
        f_stock = f_stock[f_stock['Mne_Dash8'].str.contains(w_mne, case=False, na=False)]
    if 'description' in f_stock.columns and w_desc:
        f_stock = f_stock[f_stock['description'].str.contains(w_desc, case=False, na=False)]
    if 'm_e' in f_stock.columns and w_me:
        f_stock = f_stock[f_stock['m_e'].str.contains(w_me, case=False, na=False)]

    # --- MÉTRICAS ---
    if {'required_part_quantity','QOH'}.issubset(f_stock.columns):
        f_stock['faltante'] = (f_stock['required_part_quantity'] - f_stock['QOH']).clip(lower=0).astype(int)
    else:
        f_stock['faltante'] = 0
    f_stock['estado'] = f_stock['faltante'].apply(lambda x: "⚠️ PEDIR" if x > 0 else "✅ OK")

    if 'Intransit_qty' not in f_stock.columns:
        f_stock['Intransit_qty'] = 0
    f_stock['stock_total_proyectado'] = f_stock['QOH'] + f_stock['Intransit_qty']

    def alerta(row):
        f = int(row.get('faltante', 0))
        tr = int(row.get('Intransit_qty', 0))
        if f > 0:
            if tr >= f:
                return "✅ EN CAMINO (Cubre faltante)"
            elif tr > 0:
                return "⚠️ PEDIR (Tránsito insuficiente)"
            else:
                return "⚠️ PEDIR"
        return "OK"
    f_stock['alerta_logistica'] = f_stock.apply(alerta, axis=1)

    # --- COLUMNAS VISIBLES ---
    v_cols = [
        'estado','Mne_Dash8','m_e','description','QOH','required_part_quantity',
        'faltante','OPEN ORDERS','REQUISITO','bin',
        'Intransit_qty','stock_total_proyectado','alerta_logistica'
    ]
    v_cols = [c for c in v_cols if c in f_stock.columns]

    # --- PESTAÑAS ---
    tab1, tab2, tab3 = st.tabs(["📅 PLANIFICADOR DIARIO", "📦 STOCK COMPLETO", "📈 GRÁFICO"])

    col_config = {
        "estado": st.column_config.TextColumn("ESTADO", width="small"),
        "Mne_Dash8": st.column_config.TextColumn("MNE (Dash8)", width="medium"),
        "m_e": st.column_config.TextColumn("PART NUMBER", width="medium"),
        "description": st.column_config.TextColumn("DESCRIPCIÓN", width="large"),
        "QOH": st.column_config.NumberColumn("STOCK ACT.", format="%d"),
        "required_part_quantity": st.column_config.NumberColumn("REQ.", format="%d"),
        "faltante": st.column_config.NumberColumn("FALTANTE", format="%d"),
        "OPEN ORDERS": st.column_config.NumberColumn("O. ORDERS", format="%d"),
        "REQUISITO": st.column_config.TextColumn("REQUISITO"),
        "bin": st.column_config.TextColumn("BIN"),
        "Intransit_qty": st.column_config.NumberColumn("EN TRANSITO", format="%d"),
        "stock_total_proyectado": st.column_config.NumberColumn("STOCK TOTAL PROYECTADO", format="%d"),
        "alerta_logistica": st.column_config.TextColumn("ALERTA LOGÍSTICA", width="large"),
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

        st.subheader(f"Tareas Programadas para hoy ({len(jobs_day)})")
        show_jobs_cols = [c for c in ['mne_number', 'mne_description', 'package_description', 'scheduled_date'] if c in jobs_day.columns]
        if len(show_jobs_cols) > 0 and len(jobs_day) > 0:
            st.dataframe(jobs_day[show_jobs_cols], use_container_width=True, hide_index=True)

        st.subheader("📦 MATERIALES NECESARIOS PARA ESTAS TAREAS")
        df_plan = f_stock[v_cols].reset_index(drop=True)
        st.dataframe(apply_custom_styling(df_plan), use_container_width=True, column_config=col_config, hide_index=True)

        # Descargas del planificador
        csv_all = df_plan.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="⬇️ Descargar materiales del planificador (CSV)",
            data=csv_all,
            file_name=f"materiales_planificador_{sel_date}.csv",
            mime="text/csv"
        )

        to_order = df_plan[df_plan['alerta_logistica'].str.contains("PEDIR", na=False)]
        if not to_order.empty:
            csv_order = to_order.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="⬇️ Descargar materiales a pedir (CSV)",
                data=csv_order,
                file_name=f"materiales_a_pedir_{sel_date}.csv",
                mime="text/csv"
            )
        else:
            st.info("No hay materiales en estado ⚠️ PEDIR para descargar.")

        if debug_mode:
            st.markdown("### 🛠️ Depuración")
            st.write("Inventario (muestras):", f_stock.head(10))
            st.write("Jobs (muestras):", df_jobs.head(10))

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

            # Descarga del inventario filtrado
            csv_stock = df_gen.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="⬇️ Descargar inventario filtrado (CSV)",
                data=csv_stock,
                file_name="inventario_filtrado.csv",
                mime="text/csv"
            )

    # --- TAB 3: GRÁFICO ---
    with tab3:
        st.markdown('<p class="main-header">Gráfico de Stock vs Requerido</p>', unsafe_allow_html=True)
        needed_cols = {'m_e', 'QOH', 'required_part_quantity'}
        if needed_cols.issubset(f_stock.columns):
            df_plot = f_stock.head(25)
            if not df_plot.empty:
                fig = go.Figure()
                fig.add_trace(go.Bar(x=df_plot['m_e'], y=df_plot['QOH'], name='Stock Actual', marker_color='#005DAA'))
                fig.add_trace(go.Scatter(x=df_plot['m_e'], y=df_plot['required_part_quantity'], mode='markers', name='Requerido',
                                         marker=dict(symbol='star', size=12, color='orange')))
                fig.update_layout(xaxis_title="Part Number", yaxis_title="Cantidad", template="plotly_white")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("Sin datos para graficar.")
        else:
            st.warning("Faltan columnas necesarias para el gráfico: m_e, QOH y required_part_quantity.")

else:
    st.info("👈 Por favor, carga los archivos EZESTOCK_FINAL y WPEZE_Filter para iniciar.")
