import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from io import BytesIO

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="United Airlines - Materials Dashboard", layout="wide")

st.markdown("""
    <style>
    .stDataFrame th { white-space: normal !important; }
    .main-header { font-size: 24px; font-weight: bold; color: #005DAA; }
    .critical-text { color: #b30000; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data(file):
    df = pd.read_csv(file)
    # Limpieza inicial de strings para llaves de cruce
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str).str.strip()
    return df

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')
    return output.getvalue()

# --- CARGA DE DATOS ---
st.sidebar.image("https://upload.wikimedia.org/wikipedia/en/thumb/e/e0/United_Airlines_Logo.svg/1200px-United_Airlines_Logo.svg.png", width=200)
st.sidebar.title("Material Control")

file_stock = st.sidebar.file_uploader("1️⃣ EZESTOCK_FINAL (CSV)", type=["csv"])
file_jobs = st.sidebar.file_uploader("2️⃣ WPEZE_Filter (CSV)", type=["csv"])

if file_stock and file_jobs:
    df_stock = load_data(file_stock)
    df_jobs = load_data(file_jobs)

    # --- PREPARACIÓN ---
    # Convertir números y quitar decimales
    cols_num = ['QOH', 'required_part_quantity', 'planned_quantity']
    for c in cols_num:
        if c in df_stock.columns:
            df_stock[c] = pd.to_numeric(df_stock[c], errors='coerce').fillna(0).astype(int)

    # Ajuste de fechas
    df_jobs['scheduled_date'] = pd.to_datetime(df_jobs['scheduled_date']).dt.date
    
    # Renombrar según solicitud
    df_stock = df_stock.rename(columns={'planned_quantity': 'OPEN ORDERS', 'part_action': 'REQUISITO'})
    
    # --- FILTROS SIDEBAR ---
    st.sidebar.header("🔍 Buscadores Globales")
    w_mne = st.sidebar.text_input("MNE / Dash8")
    w_desc = st.sidebar.text_input("Descripción")
    w_me = st.sidebar.text_input("Part Number (m_e)")

    # Stock Maestro Filtrado
    f_stock = df_stock.copy()
    if w_mne:
        f_stock = f_stock[f_stock['Mne_Dash8'].str.contains(w_mne, case=False, na=False)]
    if w_desc:
        f_stock = f_stock[f_stock['description'].str.contains(w_desc, case=False, na=False)]
    if w_me:
        f_stock = f_stock[f_stock['m_e'].str.contains(w_me, case=False, na=False)]

    # Cálculo de faltantes
    f_stock['faltante'] = (f_stock['required_part_quantity'] - f_stock['QOH']).clip(lower=0).astype(int)
    f_stock['estado'] = f_stock['faltante'].apply(lambda x: "⚠️ PEDIR" if x > 0 else "✅ OK")
    
    v_cols = ['estado', 'm_e', 'description', 'QOH', 'required_part_quantity', 'faltante', 'OPEN ORDERS', 'REQUISITO', 'bin']

    # --- LÓGICA DE ESTILOS ---
    def apply_style(df):
        def row_style(row):
            # Rojo: Faltante > Stock disponible
            if row['faltante'] > row['QOH'] and row['faltante'] > 0:
                return ['background-color: #ffcccc'] * len(row)
            # Amarillo: Hay faltante normal
            elif row['faltante'] > 0:
                return ['background-color: #fff4e5'] * len(row)
            return [''] * len(row)
        
        try:
            return df.style.apply(row_style, axis=1)
        except:
            return df # Si falla por tamaño, devuelve el df normal

    # --- INTERFAZ ---
    tab1, tab2, tab3 = st.tabs(["📅 Planificador", "📦 Stock General", "📈 Gráfico"])

    col_config = {
        "estado": st.column_config.TextColumn("ESTADO", width="small"),
        "m_e": st.column_config.TextColumn("PN (m_e)", width="medium"),
        "description": st.column_config.TextColumn("DESCRIPCIÓN", width="large"),
        "QOH": st.column_config.NumberColumn("STOCK", format="%d"),
        "faltante": st.column_config.NumberColumn("FALTANTE", format="%d"),
        "OPEN ORDERS": st.column_config.NumberColumn("O. ORDERS", format="%d"),
    }

    with tab1:
        st.markdown('<p class="main-header">Filtrado por Tareas del Día</p>', unsafe_allow_html=True)
        fechas = sorted(df_jobs['scheduled_date'].unique())
        sel_date = st.date_input("Fecha:", value=fechas[0] if fechas else None)

        # Trabajos
        jobs_day = df_jobs[df_jobs['scheduled_date'] == sel_date].copy()
        st.subheader(f"Tareas Programadas ({len(jobs_day)})")
        st.dataframe(jobs_day[['mne_number', 'mne_description', 'package_description']], use_container_width=True, hide_index=True)

        # MATERIALES NECESARIOS PARA ESAS TAREAS
        st.subheader("📦 Materiales necesarios para estas tareas")
        mne_list = jobs_day['mne_number'].unique().tolist()
        
        # Filtro: Solo materiales cuyo Mne_Dash8 esté en la lista de tareas del día
        mat_hoy = f_stock[f_stock['Mne_Dash8'].isin(mne_list)].reset_index(drop=True)

        if not mat_hoy.empty:
            st.dataframe(apply_style(mat_hoy[v_cols]), use_container_width=True, column_config=col_config, hide_index=True)
        else:
            st.info("No se encontraron materiales requeridos para los MNE de esta fecha.")

    with tab2:
        st.markdown('<p class="main-header">Inventario General</p>', unsafe_allow_html=True)
        # Mostramos los primeros 1000 para evitar errores de memoria si no hay filtros
        df_gen = f_stock[v_cols].reset_index(drop=True)
        if len(df_gen) > 1000:
            st.warning("Mostrando los primeros 1000 resultados. Use los filtros para ver piezas específicas.")
            df_gen = df_gen.head(1000)
        
        st.dataframe(apply_style(df_gen), use_container_width=True, column_config=col_config, hide_index=True)

    with tab3:
        st.markdown('<p class="main-header">Comparativa Stock vs Requerido</p>', unsafe_allow_html=True)
        df_plot = f_stock.head(30)
        if not df_plot.empty:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=df_plot['m_e'], y=df_plot['QOH'], name='Stock', marker_color='#005DAA'))
            fig.add_trace(go.Scatter(x=df_plot['m_e'], y=df_plot['required_part_quantity'], mode='markers', name='Requerido', marker=dict(symbol='star', size=12, color='orange')))
            fig.update_layout(template="plotly_white", margin=dict(t=20))
            st.plotly_chart(fig, use_container_width=True)

else:
    st.info("👈 Por favor, carga los archivos CSV.")
