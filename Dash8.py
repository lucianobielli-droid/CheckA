import streamlit as st
import pandas as pd
import plotly.express as px

# --- LOGO UNITED AIRLINES EN LA BARRA LATERAL ---
st.sidebar.image("united_logo.png", width=200)
st.sidebar.title("Dashboard de materiales")

uploaded_file = st.sidebar.file_uploader("📂 Selecciona tu archivo CSV", type=["csv"])
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
            qoh = float(row["QOH"])
            req = float(row["required_part_quantity"])
            if qoh < req:
                return ["background-color: #ffcccc"] * len(row)  # rojo claro
        except Exception:
            pass
        return [""] * len(row)

    # --- SELECTORES PRINCIPALES ---
    if "Mne_Dash8" in df.columns:
        # Filtro con comodín
        search_mne = st.sidebar.text_input("🔎 Filtrar Mne_Dash8 por comodín (ej: '123')")
        if search_mne.strip():
            posibles = sorted([val for val in df["Mne_Dash8"].unique() if search_mne.lower() in str(val).lower()])
        else:
            posibles = sorted(df["Mne_Dash8"].unique())

        mne_valores = st.sidebar.multiselect("Selecciona uno o varios valores de Mne_Dash8", posibles)
        search_text = st.sidebar.text_input("Buscar dentro de la tabla dinámica")

        filtered = df[df["Mne_Dash8"].isin(mne_valores)] if mne_valores else df.copy()

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

        # --- PANEL INDEPENDIENTE: Análisis de stock ---
        st.header("📊 Panel de análisis de stock")

        df_filtrado = df[df["Mne_Dash8"].isin(mne_valores)] if mne_valores else df.copy()

        # Asegurar que las columnas numéricas sean números
        for col_num in ["required_part_quantity", "QOH"]:
            if col_num in df_filtrado.columns:
                df_filtrado[col_num] = pd.to_numeric(df_filtrado[col_num], errors="coerce").fillna(0)

        # Agrupar por las columnas solicitadas y sumar cantidades
        resumen = (
            df_filtrado.groupby(
                ["m_e", "description", "manufacturer_part_number", "bin", "part_action", "item_type"],
                as_index=False
            ).agg({"required_part_quantity": "sum", "QOH": "sum"})
        )

        # Calcular faltante y estado
        resumen["faltante"] = resumen["required_part_quantity"] - resumen["QOH"]
        resumen["estado"] = resumen["faltante"].apply(lambda x: "⚠️ Pedir piezas" if x > 0 else "✅ Stock suficiente")

        # Reordenar columnas con estado primero
        resumen = resumen[
            ["estado", "m_e", "description", "manufacturer_part_number", "bin",
             "QOH", "required_part_quantity", "faltante",
             "part_action", "item_type"]
        ]

        # KPI global: total faltante
        total_faltante = float(resumen["faltante"].sum())
        st.metric("📦 Total faltante en selección", f"{total_faltante:,.0f}")

        # --- RESALTAR FILAS DONDE FALTAN PIEZAS ---
        def highlight_faltante(row):
            if row["faltante"] > 0:
                return ["background-color: #ffcccc"] * len(row)  # rojo claro
            return [""] * len(row)

        st.subheader("Resumen de piezas para selección de Mne_Dash8")
        st.dataframe(resumen.style.apply(highlight_faltante, axis=1), use_container_width=True)

        # Gráfico de barras para visualizar faltantes con etiquetas de estado
        fig_resumen = px.bar(
            resumen,
            x="m_e",
            y="faltante",
            color="estado",
            title="Faltante de piezas por m_e en selección de Mne_Dash8",
            text="estado",  # etiqueta de texto encima de cada barra
            hover_data=["description", "manufacturer_part_number", "bin"]
        )
        fig_resumen.update_traces(textposition="outside")  # coloca las etiquetas fuera de la barra
        st.plotly_chart(fig_resumen, use_container_width=True)

else:
    st.info("👆 Sube un archivo CSV para comenzar")
