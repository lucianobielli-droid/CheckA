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

def norm_mne_series(s: pd.Series) -> pd.Series:
    return (s.fillna("")
             .astype(str)
             .str.upper()
             .str.strip()
             .str.replace(r"\s+", "", regex=True)
             .replace("NAN", ""))

# --- ESTILO CONDICIONAL ---
def apply_custom_styling(df):
    if df.empty or isinstance(df, pd.io.formats.style.Styler):
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

    # --- NORMALIZACIONES / TIPOS ---
    for c in ['QOH','required_part_quantity','planned_quantity','Intransit_qty','OPEN ORDERS']:
        if c in df_stock.columns:
            df_stock[c] = pd.to_numeric(df_stock[c], errors='coerce').fillna(0).astype(int)

    if 'scheduled_date' in df_jobs.columns:
        df_jobs['scheduled_date'] = pd.to_datetime(df_jobs['scheduled_date'], errors='coerce').dt.date

    # Renombrar si es necesario
    df_stock = df_stock.rename(columns={'planned_quantity': 'OPEN ORDERS', 'part_action': 'REQUISITO'})

    # Claves normalizadas
    df_stock['Mne_Dash8_norm'] = norm_mne_series(df_stock['Mne_Dash8']) if 'Mne_Dash8' in df_stock.columns else ''
    df_jobs['mne_number_norm'] = norm_mne_series(df_jobs['mne_number']) if 'mne_number' in df_jobs.columns else ''

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

    # --- MÉTRICAS BASE (inventario general) ---
    if {'required_part_quantity','QOH'}.issubset(f_stock.columns):
        f_stock['faltante'] = (f_stock['required_part_quantity'] - f_stock['QOH']).clip(lower=0).astype(int)
    else:
        f_stock['faltante'] = 0
    f_stock['estado'] = f_stock['faltante'].apply(lambda x: "⚠️ PEDIR" if x > 0 else "✅ OK")

    # Cobertura total y alerta logística (usa Intransit_qty ya presente en EZESTOCK_FINAL)
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
        jobs_day = jobs_day[jobs_day['mne_number_norm'] != ""] if 'mne_number_norm' in jobs_day.columns else jobs_day

        st.subheader(f"Tareas Programadas para hoy ({len(jobs_day)})")
        show_jobs_cols = [c for c in ['mne_number', 'mne_description', 'package_description'] if c in jobs_day.columns]
        if len(show_jobs_cols) > 0 and len(jobs_day) > 0:
            st.dataframe(jobs_day[show_jobs_cols], use_container_width=True, hide_index=True)

        st.subheader("📦 MATERIALES NECESARIOS PARA ESTAS TAREAS")
        # Subset por MNE del día
        mne_set = set(jobs_day['mne_number_norm'].tolist()) if 'mne_number_norm' in jobs_day.columns else set()
        f_plan = f_stock[f_stock['Mne_Dash8_norm'].isin(mne_set)].copy() if len(mne_set) > 0 else f_stock.iloc[0:0].copy()

        if not f_plan.empty:
            # Agrupar por MNE + Part Number; sumar QOH, OPEN ORDERS e Intransit_qty; concatenar BIN; usar max para requerimiento
            group_keys = [k for k in ['Mne_Dash8_norm','m_e'] if k in f_plan.columns]
            agg_dict = {
                'description': 'first',
                'QOH': 'sum',
                'required_part_quantity': 'max',   # evita doble conteo del requerimiento
                'OPEN ORDERS': 'sum',
                'REQUISITO': 'first',
                'Intransit_qty': 'sum',
            }
            if 'bin' in f_plan.columns:
                agg_dict['bin'] = lambda x: ', '.join(sorted(set([str(v) for v in x if pd.notna(v)])))

            mats_for_day_grouped = f_plan.groupby(group_keys, as_index=False).agg(agg_dict)

            # Recalcular métricas derivadas
            mats_for_day_grouped['faltante'] = (mats_for_day_grouped['required_part_quantity'] - mats_for_day_grouped['QOH']).clip(lower=0).astype(int)
            mats_for_day_grouped['estado'] = mats_for_day_grouped['faltante'].apply(lambda x: "⚠️ PEDIR" if x > 0 else "✅ OK")
            mats_for_day_grouped['stock_total_proyectado'] = mats_for_day_grouped['QOH'] + mats_for_day_grouped['Intransit_qty']

            def alerta_row(row):
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
            mats_for_day_grouped['alerta_logistica'] = mats_for_day_grouped.apply(alerta_row, axis=1)

            # Columnas a mostrar
            show_cols = [c for c in [
                'estado','Mne_Dash8_norm','m_e','description','QOH','required_part_quantity',
                'faltante','OPEN ORDERS','REQUISITO','bin',
                'Intransit_qty','stock_total_proyectado','alerta_logistica'
            ] if c in mats_for_day_grouped.columns]

            styled_mat = apply_custom_styling(mats_for_day_grouped[show_cols])
            st.dataframe(styled_mat, use_container_width=True, column_config=col_config, hide_index=True)
            st.info(f"Se encontraron {len(mats_for_day_grouped)} materiales agrupados por MNE.")

            # Descargas
            csv_all = mats_for_day_grouped[show_cols].to_csv(index=False).encode('utf-8')
            st.download_button(
                label="⬇️ Descargar materiales del planificador (CSV)",
                data=csv_all,
                file_name=f"materiales_planificador_{sel_date}.csv",
                mime="text/csv"
            )
            to_order = mats_for_day_grouped[mats_for_day_grouped['alerta_logistica'].str.contains("PEDIR", na=False)]
            if not to_order.empty:
                csv_order = to_order[show_cols].to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="⬇️ Descargar materiales a pedir (CSV)",
                    data=csv_order,
                    file_name=f"materiales_a_pedir_{sel_date}.csv",
                    mime="text/csv"
                )
            else:
                st.info("No hay materiales en estado ⚠️ PEDIR para descargar.")
        else:
            st.warning("No hay materiales vinculados a los MNE de la fecha seleccionada.")

        # Depuración opcional
        if debug_mode:
            st.markdown("### 🛠️ Depuración")
            if 'mne_number' in jobs_day.columns:
                st.write("Jobs (raw vs norm):", jobs_day[['mne_number','mne_number_norm']].head(10))
            st.write("Stock (raw vs norm):", f_stock[['Mne_Dash8','Mne_Dash8_norm','m_e']].head(10))
            inter = set(f_stock['Mne_Dash8_norm']).intersection(mne_set)
            st.write("Intersección MNE stock vs jobs:", len(inter))

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
