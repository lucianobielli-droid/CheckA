import streamlit as st
import pandas as pd
import plotly.express as px

st.title("Dashboard de materiales por Mne_Dash8")

uploaded_file = st.file_uploader("📂 Selecciona tu archivo CSV", type=["csv"])
if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)

    # --- ORDENAR COLUMNAS: primero las seleccionadas, luego el resto ---
    selected_columns = [
        "m_e",
        "description",
        "QOH",
        "uom",
        "required_part_quantity",
        "bin",
        "manufacturer_part_number",
        "part_action",
        "item_type"
    ]
    other_columns = [col for col in df.columns if col not in selected_columns]
    df = df[[col for col in selected_columns if col in df.columns] + other_columns]

    # --- RESALTAR FILAS DONDE QOH < required_part_quantity ---
    def highlight_low_stock(row):
        try:
            if row["QOH"] < row["required_part_quantity"]:
                return ["background-color: #ffcccc"] * len(row)  # rojo claro
        except Exception:
            pass
        return [""] * len(row)

    # --- SELECTORES PRINCIPALES ---
    if "Mne_Dash8" in df.columns:
        mne_valor = st.selectbox("Selecciona el valor de Mne_Dash8", sorted(df["Mne_Dash8"].unique()))
        search_text = st.text_input("Buscar dentro de la tabla dinámica")

        filtered = df[df["Mne_Dash8"] == mne_valor]
        if search_text.strip():
            mask = filtered.apply(lambda row: row.astype(str).str.contains(search_text, case=False).any(), axis=1)
            filtered = filtered[mask]

        # --- KPIs ---
        col1, col2, col3 = st.columns(3)
        col1.metric("📊 Total registros", len(filtered))
        col2.metric("📑 Columnas", len(filtered.columns))
        col3.metric("🔎 Valores únicos", filtered.nunique().sum())

        # --- TABLA ORDENADA Y RESALTADA ---
        st.subheader("Tabla ordenada y resaltada")
        st.dataframe(filtered.style.apply(highlight_low_stock, axis=1), use_container_width=True)

        # --- DESCARGAS ---
        csv = filtered.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Descargar CSV", csv, "tabla_filtrada.csv", "text/csv")

        excel_path = "tabla_filtrada.xlsx"
        filtered.to_excel(excel_path, index=False)
        st.download_button("📥 Descargar Excel", open(excel_path, "rb"), "tabla_filtrada.xlsx")

        # --- GRÁFICOS ---
        columna = st.selectbox("Selecciona la columna para graficar", [c for c in filtered.columns if c not in ["Mne_Dash8"]])
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

        # --- PANEL INDEPENDIENTE: Análisis de stock ---
        st.header("📊 Panel de análisis de stock")

        # Selector de Mne_Dash8
        mne_dash8_valor = st.selectbox("Selecciona un valor de Mne_Dash8 para análisis de stock", sorted(df["Mne_Dash8"].unique()))

        # Filtrar por el valor seleccionado
        df_filtrado = df[df["Mne_Dash8"] == mne_dash8_valor]

        # Agrupar por m_e y sumar required_part_quantity y QOH
        resumen = (
            df_filtrado.groupby("m_e", as_index=False)
                       .agg({"required_part_quantity": "sum", "QOH": "sum"})
        )

        # Calcular faltante y estado
        resumen["faltante"] = resumen["required_part_quantity"] - resumen["QOH"]
        resumen["estado"] = resumen["faltante"].apply(lambda x: "⚠️ Pedir piezas" if x > 0 else "✅ Stock suficiente")

        # KPI global: total faltante
        total_faltante = resumen["faltante"].sum()
        st.metric("📦 Total faltante en este Mne_Dash8", total_faltante)

        # Mostrar tabla resumen
        st.subheader(f"Resumen de piezas para Mne_Dash8 = {mne_dash8_valor}")
        st.dataframe(resumen, use_container_width=True)

        # Gráfico de barras para visualizar faltantes
        fig_resumen = px.bar(
            resumen,
            x="m_e",
            y="faltante",
            color="estado",
            title=f"Faltante de piezas por m_e en Mne_Dash8 = {mne_dash8_valor}",
            text="faltante"
        )
        st.plotly_chart(fig_resumen, use_container_width=True)

else:
    st.info("👆 Sube un archivo CSV para comenzar")


