import streamlit as st
import pandas as pd
import plotly.express as px

st.title("Dashboard de materiales por Mne_Dash8")

uploaded_file = st.file_uploader("📂 Selecciona tu archivo CSV", type=["csv"])
if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)

    mne_valor = st.selectbox("Selecciona el valor de Mne_Dash8", sorted(df["Mne_Dash8"].unique()))
    search_text = st.text_input("Buscar dentro de la tabla dinámica")

    filtered = df[df["Mne_Dash8"] == mne_valor]
    if search_text.strip():
        mask = filtered.apply(lambda row: row.astype(str).str.contains(search_text, case=False).any(), axis=1)
        filtered = filtered[mask]

    col1, col2, col3 = st.columns(3)
    col1.metric("📊 Total registros", len(filtered))
    col2.metric("📑 Columnas", len(filtered.columns))
    col3.metric("🔎 Valores únicos", filtered.nunique().sum())

    st.subheader("Tabla dinámica")
    st.dataframe(filtered)

    csv = filtered.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Descargar CSV", csv, "tabla_filtrada.csv", "text/csv")

    excel_path = "tabla_filtrada.xlsx"
    filtered.to_excel(excel_path, index=False)
    st.download_button("📥 Descargar Excel", open(excel_path, "rb"), "tabla_filtrada.xlsx")

    columna = st.selectbox("Selecciona la columna para graficar", [c for c in filtered.columns if c != "Mne_Dash8"])
    tipo = st.selectbox("Selecciona el tipo de gráfico", ["Barras", "Pie Chart", "Línea"])

    conteo = filtered[columna].value_counts().reset_index()
    conteo.columns = [columna, "Cantidad"]

    if tipo == "Barras":
        fig = px.bar(conteo, x=columna, y="Cantidad", title=f"Distribución de '{columna}'")
    elif tipo == "Pie Chart":
        fig = px.pie(conteo, names=columna, values="Cantidad", title=f"Distribución de '{columna}'")
    elif tipo == "Línea":
        fig = px.line(conteo, x=columna, y="Cantidad", title=f"Distribución de '{columna}'")
    else:
        fig = px.histogram(filtered, x=columna, title=f"Distribución de '{columna}'")

    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("👆 Sube un archivo CSV para comenzar")
