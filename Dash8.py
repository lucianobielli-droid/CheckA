import streamlit as st
import pandas as pd
import plotly.express as px

# --- LOGO UNITED AIRLINES EN LA BARRA LATERAL ---
st.sidebar.image("united_logo.png", width=200)
st.sidebar.title("Dashboard de materiales")

uploaded_file = st.sidebar.file_uploader("📂 Selecciona tu archivo CSV", type=["csv"])
if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)

    # --- Ajustes de Pandas para mostrar todas las columnas ---
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", None)

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

    # --- SELECTORES PRINCIPALES ---
    if "Mne_Dash8" in df.columns:
        # Campo de búsqueda con comodín
        search_mne = st.sidebar.text_input("🔎 Filtrar Mne_Dash8 por comodín (ej: '123')")

        # Lista completa de valores
        todos_valores = sorted(df["Mne_Dash8"].unique())

        # Filtrar según comodín
        if search_mne.strip():
            posibles = [val for val in todos_valores if search_mne.lower() in str(val).lower()]
        else:
            posibles = todos_valores

        # Multiselect que mantiene selección
        mne_valores = st.sidebar.multiselect(
            "Selecciona uno o varios valores de Mne_Dash8",
            options=posibles,
            default=[]
        )

        # Filtrar el dataframe según selección
        filtered = df[df["Mne_Dash8"].isin(mne_valores)] if mne_valores else df.copy()

        # --- TABLA ORDENADA ---
        st.subheader("Tabla ordenada y resaltada")
        st.dataframe(filtered, use_container_width=True)

        # --- PANEL INDEPENDIENTE: Análisis de stock ---
        st.header("📊 Panel de análisis de stock")

        df_filtrado = df[df["Mne_Dash8"].isin(mne_valores)] if mne_valores else df.copy()

        # Asegurar numéricos
        for col_num in ["required_part_quantity", "QOH"]:
            if col_num in df_filtrado.columns:
                df_filtrado[col_num] = pd.to_numeric(df_filtrado[col_num], errors="coerce").fillna(0)

        # Agrupar consolidando bins
        resumen = (
            df_filtrado.groupby(
                ["m_e", "description", "manufacturer_part_number", "part_action", "item_type"],
                as_index=False
            ).agg({
                "required_part_quantity": "first",   # único por m_e
                "QOH": "sum",                        # sumar stock
                "bin": lambda x: ", ".join(sorted(str(v) for v in x.dropna().unique()))  # concatenar bins como texto
            })
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

        # KPI global
        total_faltante = float(resumen["faltante"].sum())
        st.metric("📦 Total faltante en selección", f"{total_faltante:,.0f}")

        # Resaltado de filas con faltante
        def highlight_faltante(row):
            if row["faltante"] > 0:
                return ["background-color: #ffcccc"] * len(row)
            return [""] * len(row)

        st.subheader("Resumen de piezas para selección de Mne_Dash8")
        st.dataframe(resumen.style.apply(highlight_faltante, axis=1), use_container_width=True)

        # --- DESCARGAS DE TABLA CONSOLIDADA ---
        csv_resumen = resumen.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Descargar CSV consolidado", csv_resumen, "resumen_stock.csv", "text/csv")

        excel_path = "resumen_stock.xlsx"
        resumen.to_excel(excel_path, index=False)
        st.download_button("📥 Descargar Excel consolidado", open(excel_path, "rb"), "resumen_stock.xlsx")

        # Gráfico con etiquetas de estado y faltante
        fig_resumen = px.bar(
            resumen,
            x="m_e",
            y="faltante",
            color="estado",
            title="Faltante de piezas por m_e en selección de Mne_Dash8",
            text=resumen.apply(lambda r: f"{r['estado']} ({r['faltante']})", axis=1),
            hover_data=["description", "manufacturer_part_number", "bin"]
        )
        fig_resumen.update_traces(textposition="outside")
        st.plotly_chart(fig_resumen, use_container_width=True)

else:
    st.info("👆 Sube un archivo CSV para comenzar")
