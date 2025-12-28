import streamlit as st
import pandas as pd
import plotly.express as px
import os

# --- LOGO UNITED AIRLINES (local + fallback remoto PNG) ---
# Coloca un archivo en: assets/united_logo.png
logo_local_path = "assets/united_logo.png"
logo_fallback_url = "https://www.freepnglogos.com/uploads/united-airlines-logo-png/united-airlines-logo-png-0.png"

def show_logo(sidebar=False, width=200):
    try:
        if os.path.exists(logo_local_path):
            (st.sidebar if sidebar else st).image(logo_local_path, width=width)
        else:
            (st.sidebar if sidebar else st).image(logo_fallback_url, width=width)
    except Exception:
        # En caso de error con la imagen remota, no rompe la app
        pass

# Muestra el logo arriba (puedes cambiar sidebar=True para colocarlo en la barra lateral)
show_logo(sidebar=False, width=200)

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
            # Asegura comparación numérica
            qoh = float(row["QOH"])
            req = float(row["required_part_quantity"])
            if qoh < req:
                return ["background-color: #ffcccc"] * len(row)  # rojo claro
        except Exception:
            pass
        return [""] * len(row)

    # --- SELECTORES PRINCIPALES (multiselect) ---
    if "Mne_Dash8" in df.columns:
        mne_valores = st.multiselect("Selecciona uno o varios valores de Mne_Dash8", sorted(df["Mne_Dash8"].unique()))
        search_text = st.text_input("Buscar dentro de la tabla dinámica")

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

        # --- DESCARGAS ---
        csv = filtered.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Descargar CSV", csv, "tabla_filtrada.csv", "text/csv")

        excel_path = "tabla_filtrada.xlsx"
        filtered.to_excel(excel_path, index=False)
        st.download_button("📥 Descargar Excel", open(excel_path, "rb"), "tabla_filtrada.xlsx")

        # --- GRÁFICOS ---
        columna = st.selectbox("Selecciona la columna para graficar", [c for c in filtered.columns if c != "Mne_Dash8"])
        tipo = st.selectbox("Selecciona el tipo de gráfico", ["Barras", "Pie Chart", "Línea"])

        conteo = filtered[columna].value_counts().reset_index()
        conteo.columns = [columna, "Cantidad"]

        if tipo == "Barras":
            fig = px.bar(conteo, x=columna, y="Cantidad", title=f"Distribución de '{columna}'")
        elif tipo == "Pie Chart":
            fig = px.pie(conteo, names=columna, values="Cantidad", title=f"Distribución de '{columna}'")
        else:
            fig = px.line(conteo, x=columna, y="Cantidad", title=f"Distribución de '{columna}'")

        st.plotly_chart(fig, use_container_width=True)

        # --- PANEL INDEPENDIENTE: Análisis de stock con multiselect ---
        st.header("📊 Panel de análisis de stock")

        mne_dash8_valores = st.multiselect("Selecciona uno o varios valores de Mne_Dash8 para análisis de stock",
                                           sorted(df["Mne_Dash8"].unique()))

        df_filtrado = df[df["Mne_Dash8"].isin(mne_dash8_valores)] if mne_dash8_valores else df.copy()

        # Asegura que las columnas numéricas estén como números
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

        # Reordenar columnas en el orden solicitado
        resumen = resumen[
            ["m_e", "description", "manufacturer_part_number", "bin",
             "QOH", "required_part_quantity", "faltante",
             "part_action", "item_type", "estado"]
        ]

        # KPI global: total faltante
        total_faltante = float(resumen["faltante"].sum())
        st.metric("📦 Total faltante en selección", f"{total_faltante:,.0f}")

        # Mostrar tabla resumen
        st.subheader("Resumen de piezas para selección de Mne_Dash8")
        st.dataframe(resumen, use_container_width=True)

        # Gráfico de barras para visualizar faltantes
        fig_resumen = px.bar(
            resumen,
            x="m_e",
            y="faltante",
            color="estado",
            title="Faltante de piezas por m_e en selección de Mne_Dash8",
            text="faltante",
            hover_data=["description", "manufacturer_part_number", "bin"]
        )
        st.plotly_chart(fig_resumen, use_container_width=True)

else:
    st.info("👆 Sube un archivo CSV para comenzar")
