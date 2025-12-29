import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from io import BytesIO

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="United Airlines - Materials Dashboard", layout="wide")

# Estilos CSS
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
    try:
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Data')
    except:
        with pd.ExcelWriter(output) as writer:
            df.to_excel(writer, index=False, sheet_name='Data')
    return output.getvalue()

# --- FUNCIÓN DE ESTILO VECTORIZADA (OPTIMIZADA) ---
def highlight_vectorized(data):
    # Creamos un DataFrame de estilos con la misma forma que 'data', lleno de strings vacíos
    df_styles = pd.DataFrame('', index=data.index, columns=data.columns)
    
    # 1. Definimos las máscaras (Condiciones lógicas para toda la tabla)
    # Faltante CRÍTICO: Faltante > Stock Actual Y Faltante > 0
    mask_critical = (data['faltante'] > data['QOH']) & (data['faltante'] > 0)
    
    # Faltante REGULAR: Hay faltante pero no es mayor al stock (o es el resto de casos positivos)
    # Nota: Si prefieres que sea solo "Faltante > 0", ajustamos la lógica. 
    # Aquí: Amarillos son los que faltan pero NO son críticos.
    mask_warning = (data['faltante'] > 0) & (~mask_critical)
    
    # 2. Definimos los estilos CSS
    style_critical = 'background-color: #ffcccc; color: #b30000; font-weight: bold'
    style_warning = 'background-color: #fff4e5'
    
    # 3. Aplicamos el estilo a TODAS las columnas para las filas que cumplen la máscara
    # Esto es 100 veces más rápido que iterar fila por fila
    for col in df_styles.columns:
        df_styles.loc[mask_critical, col] = style_critical
        df_styles.loc[mask_warning, col] = style_warning
        
    return df_styles

# --- SIDEBAR ---
st.sidebar.image("https://upload.wikimedia.org/wikipedia/en/thumb/e/e0/United_Airlines_Logo.svg/1200px-United_Airlines_Logo.svg.png", width=200)
st.sidebar.title("Control de Materiales")

file_stock = st.sidebar.file_uploader("1️⃣ Base de Stock (EZESTOCK_FINAL)", type=["csv"])
file_jobs = st.sidebar.file_uploader("2️⃣ Trabajos Programados (WPEZE_Filter)", type=["csv"])

if file_stock and file_jobs:
    df_stock = load_data(file_stock)
    df_jobs = load_data(file_jobs)

    # --- LIMPIEZA DE DATOS ---
    df_stock['Mne_Dash8'] = df_stock['Mne_Dash8'].astype(str).str.strip()
    df_jobs['mne_number'] = df_jobs['mne_number'].astype(str).str.strip()
    
    cols_num = ['QOH', 'required_part_quantity', 'planned_quantity']
    for c in cols_num:
        if c in df_stock.columns:
            df_stock[c] = pd.to_numeric(df_stock[c], errors='coerce').fillna(0).astype(int)

    df_jobs['scheduled_date'] = pd.to_datetime(df_jobs['scheduled_date']).dt.date
    df_stock = df_stock.rename(columns={'planned_quantity': 'OPEN ORDERS', 'part_action': 'REQUISITO'})

    # --- BUSCADORES ---
    st.sidebar.header("🔍 Buscadores (Comodín)")
    w_mne = st.sidebar.text_input("Filtrar por MNE (Dash8)")
    w_desc = st.sidebar.text_input("Filtrar por Descripción")
    w_me = st.sidebar.text_input("Filtrar por Part Number (m_e)")

    # --- LÓGICA DE FILTRADO ---
    f_stock = df_stock.copy()
    
    if w_mne:
        f_stock = f_stock[f_stock['Mne_Dash8'].str.contains(w_mne, case=False, na=False)]
    if w_desc:
        f_stock = f_stock[f_stock['description'].str.contains(w_desc, case=False, na=False)]
    if w_me:
        f_stock = f_stock[f_stock['m_e'].str.contains(w_me, case=False, na=False)]

    f_stock['faltante'] = (f_stock['required_part_quantity'] - f_stock['QOH']).clip(lower=0).astype(int)
    f_stock['estado'] = f_stock['faltante'].apply(lambda x: "⚠️ PEDIR" if x > 0 else "✅ OK")

    # Orden de columnas
    v_cols = ['estado', 'm_e', 'description', 'QOH', 'required_part_quantity', 'faltante', 'OPEN ORDERS', 'REQUISITO', 'bin']

    # --- PESTAÑAS ---
    tab1, tab2, tab3 = st.tabs(["📅 Planificador", "📦 Stock General", "📈 Gráfico Interactivo"])

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

    # --- TAB 1: PLANIFICADOR ---
    with tab1:
        st.markdown('<p class="main-header">📅 Trabajos y Materiales</p>', unsafe_allow_html=True)
        fechas = sorted(df_jobs['scheduled_date'].unique())
        sel_date = st.date_input("Selecciona Fecha:", value=fechas[0] if fechas else None)

        jobs_day = df_jobs[df_jobs['scheduled_date'] == sel_date].copy()
        if w_desc:
            jobs_day = jobs_day[jobs_day['mne_description'].str.contains(w_desc, case=False, na=False)]

        st.subheader(f"Actividades ({len(jobs_day)})")
        st.dataframe(jobs_day[['mne_number', 'mne_description', 'package_description']], use_container_width=True, hide_index=True)

        st.subheader("📦 Materiales Requeridos")
        mne_list = jobs_day['mne_number'].unique()
        mat_hoy = f_stock[f_stock['Mne_Dash8'].isin(mne_list)].copy()

        if not mat_hoy.empty:
            # APLICAMOS EL ESTILO VECTORIZADO (axis=None)
            # Esto evita el error de StreamlitAPIException
            st.dataframe(
                mat_hoy[v_cols].reset_index(drop=True).style.apply(highlight_vectorized, axis=None), 
                use_container_width=True, 
                column_config=col_config,
                hide_index=True
            )
        else:
            st.info("No hay materiales en stock para estos trabajos.")

    # --- TAB 2: STOCK GENERAL ---
    with tab2:
        st.markdown('<p class="main-header">📦 Análisis de Inventario</p>', unsafe_allow_html=True)
        # Aquí también usamos el estilo vectorizado
        st.dataframe(
            f_stock[v_cols].reset_index(drop=True).style.apply(highlight_vectorized, axis=None), 
            use_container_width=True, 
            column_config=col_config,
            hide_index=True
        )

    # --- TAB 3: GRÁFICO ---
    with tab3:
        st.markdown('<p class="main-header">📈 Comparativa Visual</p>', unsafe_allow_html=True)
        df_plot = f_stock.copy().head(40)
        
        if not df_plot.empty:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df_plot['m_e'], y=df_plot['QOH'],
                name='Stock Actual', marker_color='#005DAA',
                text=df_plot['QOH'], textposition='auto'
            ))
            fig.add_trace(go.Scatter(
                x=df_plot['m_e'], y=df_plot['required_part_quantity'],
                mode='markers', name='Requerido',
                marker=dict(symbol='star', size=15, color='#FF8C00', line=dict(width=1, color='black'))
            ))
            fig.update_layout(title="Top 40 Items Filtrados", xaxis_title="Part Number", yaxis_title="Cantidad", template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Sin datos para mostrar.")

else:
    st.info("👈 Carga los archivos CSV.")
