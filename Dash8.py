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

# --- NORMALIZADOR DE CLAVES MNE ---
def norm_mne_series(series):
    return series.astype(str).str.upper().str.strip().str.replace(r"\s+", "", regex=True)

# --- ESTILO CONDICIONAL ---
def apply_custom_styling(df):
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

    if len(df) > 800:
        return df
    return df.style.apply(highlight_logic, axis=None)

# --- UTILIDAD: FILTRAR COLUMNAS NO VACÍAS ---
def filter_nonempty_columns(df, candidate_cols=None):
    if candidate_cols is None:
        candidate_cols = list(df.columns)
    cols = [c for c in candidate_cols if c in df.columns]
    def has_data(series):
        if series.dtype == 'object':
            return series.fillna('').astype(str).str.strip().ne('').any()
        return series.notna().any()
    return [c for c in cols if has_data(df[c])]

# --- SIDEBAR ---
st.sidebar.title("Material Control")
file_stock = st.sidebar.file_uploader("1️⃣ EZESTOCK_FINAL (CSV)", type=["csv"])
file_jobs = st.sidebar.file_uploader("2️⃣ WPEZE_Filter (CSV)", type=["csv"])
debug_mode = st.sidebar.checkbox("🛠️ Modo depuración", value=False)

# --- APP ---
if file_stock and file_jobs:
    df_stock = load_data(file_stock)
    df_jobs = load_data(file_jobs)

    # Tipificación numérica
    for c in ['QOH','required_part_quantity','planned_quantity','Intransit_qty']:
        if c in df_stock.columns:
            df_stock[c] = pd.to_numeric(df_stock[c], errors='coerce').fillna(0).astype(int)

    # Fecha de jobs
    if 'scheduled_date' in df_jobs.columns:
        df_jobs['scheduled_date'] = pd.to_datetime(df_jobs['scheduled_date'], errors='coerce').dt.date

    # Renombres
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
        f_stock['faltante'] = (f_stock['required_part_quantity'] - f_stock['QOH']).clip(lower=0).fillna(0).astype(int)
    else:
        f_stock['faltante'] = 0
    f_stock['estado'] = f_stock['faltante'].apply(lambda x: "⚠️ PEDIR" if x > 0 else "✅ OK")
    f_stock['Intransit_qty'] = pd.to_numeric(f_stock.get('Intransit_qty', 0), errors='coerce').fillna(0).astype(int)
    if 'QOH' in f_stock.columns:
        f_stock['stock_total_proyectado'] = (f_stock['QOH'] + f_stock['Intransit_qty']).astype(int)
    else:
        f_stock['stock_total_proyectado'] = f_stock['Intransit_qty']

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

    # Columnas visibles base
    v_cols = [
        'estado','Mne_Dash8','m_e','description','QOH','required_part_quantity',
        'faltante','OPEN ORDERS','REQUISITO','bin',
        'Intransit_qty','stock_total_proyectado','alerta_logistica'
    ]
    v_cols = [c for c in v_cols if c in f_stock.columns]

    # --- TABS ---
    tab1, tab2, tab3 = st.tabs(["📅 PLANIFICADOR DIARIO", "📦 STOCK COMPLETO", "📈 GRÁFICO"])

    # Config de columnas para Streamlit
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

        # Normalización de claves
        jobs_day['mne_number_norm'] = norm_mne_series(jobs_day['mne_number']) if 'mne_number' in jobs_day.columns else ""
        f_stock_plan = df_stock.copy()
        f_stock_plan['Mne_Dash8_norm'] = norm_mne_series(f_stock_plan['Mne_Dash8']) if 'Mne_Dash8' in f_stock_plan.columns else ""

        # Eliminar vacíos
        jobs_day = jobs_day[jobs_day['mne_number_norm'] != ""]
        f_stock_plan = f_stock_plan[f_stock_plan['Mne_Dash8_norm'] != ""]

        st.subheader(f"Tareas Programadas para hoy ({len(jobs_day)})")
        show_jobs_cols = filter_nonempty_columns(jobs_day, ['mne_number', 'mne_description', 'package_description', 'scheduled_date'])
        if len(show_jobs_cols) > 0 and len(jobs_day) > 0:
            st.dataframe(jobs_day[show_jobs_cols], use_container_width=True, hide_index=True)

        st.subheader("📦 MATERIALES NECESARIOS PARA ESTAS TAREAS")

        # Subset por MNE del día (nunca cae al inventario completo)
        if 'mne_number_norm' in jobs_day.columns and 'Mne_Dash8_norm' in f_stock_plan.columns:
            mne_set = set(jobs_day['mne_number_norm'].dropna().tolist())
            mne_set = {m for m in mne_set if m != "" and m.upper() != "NAN"}
            mats_for_day = f_stock_plan[f_stock_plan['Mne_Dash8_norm'].isin(mne_set)].copy()
        else:
            mats_for_day = pd.DataFrame()

        if not mats_for_day.empty:
            # Elimina duplicados exactos para evitar doble conteo
            dedup_subset_cols = [c for c in ['Mne_Dash8_norm', 'm_e', 'description', 'required_part_quantity', 'QOH', 'OPEN ORDERS', 'REQUISITO', 'bin'] if c in mats_for_day.columns]
            if len(dedup_subset_cols) > 0:
                mats_for_day = mats_for_day.drop_duplicates(subset=dedup_subset_cols)

            # Agrupar por MNE y Part Number, calcular métricas
            agg_dict = {}
            if 'description' in mats_for_day.columns: agg_dict['description'] = 'first'
            if 'QOH' in mats_for_day.columns: agg_dict['QOH'] = 'sum'
            if 'required_part_quantity' in mats_for_day.columns: agg_dict['required_part_quantity'] = 'max'
            if 'OPEN ORDERS' in mats_for_day.columns: agg_dict['OPEN ORDERS'] = 'sum'
            if 'REQUISITO' in mats_for_day.columns: agg_dict['REQUISITO'] = 'first'
            if 'bin' in mats_for_day.columns:
                agg_dict['bin'] = lambda x: ', '.join(sorted(set([str(v) for v in x if pd.notna(v)])))

            if {'Mne_Dash8_norm','m_e'}.issubset(mats_for_day.columns):
                mats_for_day_grouped = mats_for_day.groupby(['Mne_Dash8_norm','m_e'], as_index=False).agg(agg_dict)
            else:
                mats_for_day_grouped = mats_for_day.copy()

            # Recalcular métricas
            mats_for_day_grouped['QOH'] = pd.to_numeric(mats_for_day_grouped.get('QOH', 0), errors='coerce').fillna(0).astype(int)
            mats_for_day_grouped['required_part_quantity'] = pd.to_numeric(mats_for_day_grouped.get('required_part_quantity', 0), errors='coerce').fillna(0).astype(int)
            mats_for_day_grouped['Intransit_qty'] = pd.to_numeric(mats_for_day_grouped.get('Intransit_qty', 0), errors='coerce').fillna(0).astype(int)

            mats_for_day_grouped['faltante'] = (mats_for_day_grouped['required_part_quantity'] - mats_for_day_grouped['QOH']).clip(lower=0).astype(int)
            mats_for_day_grouped['estado'] = mats_for_day_grouped['faltante'].apply(lambda x: "⚠️ PEDIR" if x > 0 else "✅ OK")
            mats_for_day_grouped['stock_total_proyectado'] = (mats_for_day_grouped['QOH'] + mats_for_day_grouped['Intransit_qty']).astype(int)

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

            # Llenar vacíos amigables
            mats_for_day_grouped = mats_for_day_grouped.fillna({'description':'','REQUISITO':'','bin':'','faltante':0,'Intransit_qty':0,'stock_total_proyectado':0,'alerta_logistica':'OK'})

            # Selección columnas visibles y filtro no vacías
            preferred_cols = [
                'estado',
                'Mne_Dash8_norm','Mne_Dash8',
                'm_e','description','QOH','required_part_quantity',
                'faltante','OPEN ORDERS','REQUISITO','bin',
                'Intransit_qty','stock_total_proyectado','alerta_logistica'
            ]
            show_cols = filter_nonempty_columns(mats_for_day_grouped, preferred_cols)

            # Mostrar
            styled_mat = apply_custom_styling(mats_for_day_grouped[show_cols])
            st.dataframe(styled_mat, use_container_width=True, column_config=col_config, hide_index=True)
            st.info(f"Se encontraron {len(mats_for_day_grouped)} materiales agrupados para el plan.")

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
            if len(jobs_day) == 0:
                st.warning("No hay tareas programadas para la fecha seleccionada.")
            else:
                st.warning("No hay materiales en el almacén vinculados a los MNE de esta fecha.")

        # Depuración mejorada
        if debug_mode:
            st.markdown("### 🛠️ Depuración de claves y columnas críticas")
            crit_jobs = ['scheduled_date','mne_number']
            crit_stock = ['Mne_Dash8','m_e','QOH','required_part_quantity']
            missing_jobs = [c for c in crit_jobs if c not in df_jobs.columns]
            missing_stock = [c for c in crit_stock if c not in df_stock.columns]
            if missing_jobs or missing_stock:
                st.error(f"Faltan columnas críticas. Jobs: {missing_jobs if missing_jobs else 'OK'} | Stock: {missing_stock if missing_stock else 'OK'}")

            if 'Mne_Dash8' in f_stock_plan.columns:
                st.write("Muestras stock (raw vs norm):", f_stock_plan[['Mne_Dash8', 'Mne_Dash8_norm']].head(10))
            if 'mne_number' in jobs_day.columns:
                st.write("Muestras jobs (raw vs norm):", jobs_day[['mne_number', 'mne_number_norm']].head(10))
            if 'Mne_Dash8_norm' in f_stock_plan.columns:
                st.write("Blancos stock Mne_Dash8_norm:", int((f_stock_plan['Mne_Dash8_norm'] == '').sum()))
                st.write("Unique stock MNE_norm:", f_stock_plan['Mne_Dash8_norm'].nunique())
            if 'mne_number_norm' in jobs_day.columns:
                st.write("Blancos jobs mne_number_norm:", int((jobs_day['mne_number_norm'] == '').sum()))
                st.write("Unique jobs MNE_norm (día):", jobs_day['mne_number_norm'].nunique())
            mne_set_debug = set(jobs_day['mne_number_norm'].tolist())
            inter = set(f_stock_plan['Mne_Dash8_norm']).intersection(mne_set_debug)
            st.write("Intersección tamaño:", len(inter))
            st.write("Ejemplos en intersección:", list(inter)[:10])

    # --- TAB 2: STOCK COMPLETO ---
    with tab2:
        st.markdown('<p class="main-header">Inventario General (Filtros Sidebar)</p>', unsafe_allow_html=True)
        if len(v_cols) == 0:
            st.warning("No hay columnas compatibles para mostrar el inventario.")
        else:
            df_gen = f_stock[v_cols].reset_index(drop=True)
            # Filtrar columnas completamente vacías
            df_gen = df_gen.loc[:, filter_nonempty_columns(df_gen)]

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
                fig.add_trace(go.Scatter(
                    x=df_plot['m_e'],
                    y=df_plot['required_part_quantity'],
                    mode='markers',
                    name='Requerido',
                    marker=dict(symbol='star', size=12, color='orange')
                ))
                fig.update_layout(xaxis_title="Part Number", yaxis_title="Cantidad", template="plotly_white")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("Sin datos para graficar.")
        else:
            faltantes = needed_cols - set(f_stock.columns)
            st.warning(f"Faltan columnas necesarias para el gráfico: {', '.join(sorted(faltantes))}.")

else:
    st.info("👈 Por favor, carga los archivos EZESTOCK_FINAL y WPEZE_Filter para iniciar.")
