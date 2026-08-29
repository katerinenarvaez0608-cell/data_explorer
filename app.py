"""Aplicación Streamlit para análisis exploratorio automático de datos."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


st.set_page_config(
    page_title="Explorador automático de datos",
    page_icon="📊",
    layout="wide",
)

DATE_NAME_TOKENS = ("fecha", "date")
MISSING_LABEL = "(Faltante)"
MAX_CATEGORIES_CHART = 30


@st.cache_data(show_spinner="Leyendo el archivo...")
def read_dataset(file_bytes: bytes, file_name: str) -> pd.DataFrame:
    """Lee un CSV o un libro de Excel desde memoria y normaliza encabezados."""
    extension = Path(file_name).suffix.lower()
    buffer = BytesIO(file_bytes)

    if extension == ".csv":
        # sep=None permite detectar coma, punto y coma, tabulación u otro separador común.
        try:
            dataframe = pd.read_csv(buffer, sep=None, engine="python")
        except UnicodeDecodeError:
            buffer.seek(0)
            dataframe = pd.read_csv(buffer, sep=None, engine="python", encoding="latin-1")
    elif extension == ".xlsx":
        dataframe = pd.read_excel(buffer, engine="openpyxl")
    elif extension == ".xls":
        dataframe = pd.read_excel(buffer, engine="xlrd")
    else:
        raise ValueError("Formato no admitido. Carga un archivo CSV, XLSX o XLS.")

    dataframe.columns = [str(column).strip() for column in dataframe.columns]
    dataframe = infer_date_columns(dataframe)
    return dataframe


def infer_date_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Interpreta como fecha columnas cuyo nombre lo sugiera, sin forzar conversiones fallidas."""
    result = dataframe.copy()
    for column in result.columns:
        normalized_name = str(column).lower()
        if any(token in normalized_name for token in DATE_NAME_TOKENS):
            original = result[column]
            if pd.api.types.is_datetime64_any_dtype(original):
                continue
            parsed = pd.to_datetime(original, errors="coerce", dayfirst=True)
            non_null_original = int(original.notna().sum())
            successful = int(parsed.notna().sum())
            # Evita convertir columnas cuyo nombre menciona fecha, pero cuyos valores no lo son.
            if non_null_original == 0 or successful / non_null_original >= 0.60:
                result[column] = parsed
    return result


def analytical_type(series: pd.Series) -> str:
    """Clasifica una serie para fines analíticos sin alterar sus valores."""
    if pd.api.types.is_bool_dtype(series):
        return "Booleana"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "Fecha/hora"
    if pd.api.types.is_numeric_dtype(series):
        return "Numérica"
    if isinstance(series.dtype, pd.CategoricalDtype):
        return "Categórica"

    non_null_count = int(series.notna().sum())
    unique_count = int(series.nunique(dropna=True))
    category_limit = min(50, max(10, int(non_null_count * 0.20)))
    return "Categórica" if unique_count <= category_limit else "Texto"


def classified_columns(dataframe: pd.DataFrame, kinds: Iterable[str]) -> list[str]:
    """Devuelve columnas cuya clasificación analítica pertenece a kinds."""
    accepted = set(kinds)
    return [column for column in dataframe.columns if analytical_type(dataframe[column]) in accepted]


def build_type_summary(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Construye el inventario de variables del conjunto de datos."""
    rows = []
    for column in dataframe.columns:
        series = dataframe[column]
        rows.append(
            {
                "Variable": column,
                "Tipo de dato Pandas": str(series.dtype),
                "Tipo analítico": analytical_type(series),
                "Valores no nulos": int(series.notna().sum()),
                "Valores únicos": int(series.nunique(dropna=True)),
            }
        )
    return pd.DataFrame(rows)


def to_csv_bytes(dataframe: pd.DataFrame) -> bytes:
    """Genera un CSV UTF-8 con BOM, compatible con Excel, sin escribir en disco."""
    return dataframe.to_csv(index=False).encode("utf-8-sig")


def apply_sidebar_filters(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Crea filtros en la barra lateral y devuelve una vista filtrada."""
    filtered = dataframe.copy()
    date_columns = classified_columns(dataframe, ["Fecha/hora"])
    categorical_columns = classified_columns(dataframe, ["Categórica", "Booleana"])
    numeric_columns = classified_columns(dataframe, ["Numérica"])

    st.sidebar.divider()
    st.sidebar.header("Filtros interactivos")
    st.sidebar.caption("Los valores faltantes se conservan en los filtros de fecha y numéricos.")

    if date_columns:
        with st.sidebar.expander("Filtros por fecha"):
            selected_dates = st.multiselect(
                "Variables de fecha",
                date_columns,
                key="selected_date_filters",
            )
            for column in selected_dates:
                valid_dates = dataframe[column].dropna()
                if valid_dates.empty:
                    st.caption(f"{column}: no contiene fechas válidas.")
                    continue
                min_date = valid_dates.min().date()
                max_date = valid_dates.max().date()
                start_date = st.date_input(
                    f"Fecha inicial · {column}", min_date, min_value=min_date, max_value=max_date,
                    key=f"date_start_{column}",
                )
                end_date = st.date_input(
                    f"Fecha final · {column}", max_date, min_value=min_date, max_value=max_date,
                    key=f"date_end_{column}",
                )
                if start_date > end_date:
                    st.warning(f"En {column}, la fecha inicial supera la final.")
                    filtered = filtered.iloc[0:0]
                else:
                    values = filtered[column]
                    mask = values.isna() | values.dt.date.between(start_date, end_date)
                    filtered = filtered.loc[mask]

    if categorical_columns:
        with st.sidebar.expander("Filtros categóricos"):
            selected_categories = st.multiselect(
                "Variables categóricas",
                categorical_columns,
                key="selected_categorical_filters",
            )
            for column in selected_categories:
                available = dataframe[column].dropna().unique().tolist()
                available = sorted(available, key=lambda value: str(value))
                options = available + ([MISSING_LABEL] if dataframe[column].isna().any() else [])
                chosen = st.multiselect(
                    f"Categorías · {column}",
                    options,
                    default=options,
                    key=f"category_values_{column}",
                )
                includes_missing = MISSING_LABEL in chosen
                chosen_values = [value for value in chosen if value != MISSING_LABEL]
                mask = filtered[column].isin(chosen_values)
                if includes_missing:
                    mask = mask | filtered[column].isna()
                filtered = filtered.loc[mask]

    if numeric_columns:
        with st.sidebar.expander("Filtros numéricos"):
            selected_numeric = st.multiselect(
                "Variables numéricas",
                numeric_columns,
                key="selected_numeric_filters",
            )
            for column in selected_numeric:
                valid_values = dataframe[column].replace([np.inf, -np.inf], np.nan).dropna()
                if valid_values.empty:
                    st.caption(f"{column}: no contiene valores numéricos finitos.")
                    continue
                minimum = float(valid_values.min())
                maximum = float(valid_values.max())
                if minimum == maximum:
                    st.caption(f"{column}: todos los valores válidos son {minimum:g}.")
                    continue
                selected_range = st.slider(
                    f"Rango · {column}",
                    min_value=minimum,
                    max_value=maximum,
                    value=(minimum, maximum),
                    key=f"numeric_range_{column}",
                )
                values = filtered[column]
                mask = values.isna() | values.between(selected_range[0], selected_range[1])
                filtered = filtered.loc[mask]

    st.sidebar.metric("Registros resultantes", len(filtered))
    return filtered


def numeric_statistics(dataframe: pd.DataFrame) -> pd.DataFrame:
    columns = classified_columns(dataframe, ["Numérica"])
    if not columns:
        raise ValueError("El conjunto filtrado no contiene variables numéricas.")
    return dataframe[columns].describe().rename(
        index={
            "count": "Conteo", "mean": "Media", "std": "Desviación estándar",
            "min": "Mínimo", "25%": "Primer cuartil", "50%": "Mediana",
            "75%": "Tercer cuartil", "max": "Máximo",
        }
    ).T


def categorical_statistics(dataframe: pd.DataFrame) -> pd.DataFrame:
    columns = classified_columns(dataframe, ["Categórica", "Texto", "Booleana"])
    if not columns:
        raise ValueError("El conjunto filtrado no contiene variables categóricas o de texto.")
    rows = []
    for column in columns:
        series = dataframe[column]
        frequencies = series.value_counts(dropna=True)
        rows.append(
            {
                "Variable": column,
                "Conteo": int(series.notna().sum()),
                "Valores únicos": int(series.nunique(dropna=True)),
                "Categoría más frecuente": frequencies.index[0] if not frequencies.empty else None,
                "Frecuencia dominante": int(frequencies.iloc[0]) if not frequencies.empty else 0,
            }
        )
    return pd.DataFrame(rows).set_index("Variable")


def detect_outliers(
    dataframe: pd.DataFrame, columns: list[str], factor: float
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Detecta atípicos por IQR y conserva una fila por variable y detección."""
    result_frames = []
    summary_rows = []
    for column in columns:
        series = dataframe[column].replace([np.inf, -np.inf], np.nan)
        valid = series.dropna()
        if valid.empty:
            lower = upper = np.nan
            mask = pd.Series(False, index=dataframe.index)
        else:
            q1, q3 = valid.quantile([0.25, 0.75])
            iqr = q3 - q1
            lower = q1 - factor * iqr
            upper = q3 + factor * iqr
            mask = series.lt(lower) | series.gt(upper)

        summary_rows.append({"Variable": column, "Cantidad de atípicos": int(mask.sum())})
        if mask.any():
            detected = dataframe.loc[mask].copy()
            detected.insert(0, "Fila original", detected.index)
            detected.insert(1, "Variable atípica", column)
            detected.insert(2, "Valor atípico", series.loc[mask].values)
            detected.insert(3, "Límite inferior", lower)
            detected.insert(4, "Límite superior", upper)
            result_frames.append(detected)

    details = pd.concat(result_frames, ignore_index=True) if result_frames else pd.DataFrame(
        columns=["Fila original", "Variable atípica", "Valor atípico", "Límite inferior", "Límite superior"]
        + list(dataframe.columns)
    )
    return pd.DataFrame(summary_rows), details


st.title("📊 Explorador automático de datos")
st.write(
    "Carga un archivo para obtener un análisis exploratorio automático, aplicar filtros, "
    "revisar la calidad de los datos y descargar resultados sin modificar el archivo original."
)

uploaded_file = st.sidebar.file_uploader(
    "Carga tu conjunto de datos",
    type=["csv", "xlsx", "xls"],
    help="Formatos permitidos: CSV, XLSX y XLS.",
)

if uploaded_file is None:
    st.info("Para comenzar, carga un archivo desde la barra lateral.")
    col1, col2, col3 = st.columns(3)
    col1.subheader("1. Cargar")
    col1.write("Selecciona un archivo CSV, XLSX o XLS desde tu equipo.")
    col2.subheader("2. Explorar")
    col2.write("Aplica filtros y revisa tipos, calidad, estadísticas, gráficos y correlaciones.")
    col3.subheader("3. Descargar")
    col3.write("Exporta los datos filtrados y los valores atípicos en CSV.")
    st.subheader("Análisis disponibles")
    st.markdown(
        "- Dimensiones, tipos de variables y métricas generales.\n"
        "- Duplicados, valores faltantes y estadísticas descriptivas.\n"
        "- Distribuciones, correlaciones y detección de valores atípicos mediante IQR.\n"
        "- Filtros por fecha, categoría y rango numérico.\n"
        "- Tabla interactiva y descargas en formato CSV."
    )
    st.warning("No cargues información personal, confidencial o sensible.")
    st.stop()

try:
    df = read_dataset(uploaded_file.getvalue(), uploaded_file.name)
except Exception as error:
    st.error(
        "No fue posible procesar el archivo. Comprueba que el formato coincida con su extensión, "
        "que el archivo no esté dañado y que la primera hoja contenga una tabla válida."
    )
    st.caption(f"Detalle técnico: {type(error).__name__}: {error}")
    st.stop()

if df.empty or len(df.columns) == 0:
    st.warning("El archivo está vacío o no contiene una tabla con columnas y registros.")
    st.stop()

st.sidebar.success(f"Archivo cargado: {uploaded_file.name}")
filtered_df = apply_sidebar_filters(df)
if filtered_df.empty:
    st.warning("Los filtros no producen registros. Ajusta los filtros en la barra lateral.")
    st.stop()

numeric_cols = classified_columns(filtered_df, ["Numérica"])
categorical_cols = classified_columns(filtered_df, ["Categórica", "Booleana"])
distribution_cols = list(filtered_df.columns)

st.subheader("Indicadores generales")
metric1, metric2, metric3, metric4 = st.columns(4)
metric1.metric("Filas", f"{filtered_df.shape[0]:,}".replace(",", "."))
metric2.metric("Columnas", f"{filtered_df.shape[1]:,}".replace(",", "."))
metric3.metric("Registros duplicados", f"{int(filtered_df.duplicated().sum()):,}".replace(",", "."))
metric4.metric("Celdas faltantes", f"{int(filtered_df.isna().sum().sum()):,}".replace(",", "."))
st.caption(
    f"Archivo: **{uploaded_file.name}** · Dimensiones actuales: "
    f"**{filtered_df.shape[0]} filas × {filtered_df.shape[1]} columnas**"
)
st.download_button(
    "⬇️ Descargar datos filtrados",
    data=to_csv_bytes(filtered_df),
    file_name="datos_filtrados.csv",
    mime="text/csv",
)

(
    tab_summary, tab_quality, tab_stats, tab_distributions,
    tab_correlations, tab_outliers, tab_table,
) = st.tabs(
    [
        "Resumen y tipos", "Calidad de datos", "Estadísticas", "Distribuciones",
        "Correlaciones", "Valores atípicos", "Tabla ordenable",
    ]
)

with tab_summary:
    st.subheader("Dimensiones del conjunto de datos")
    st.write(f"**Archivo cargado:** {uploaded_file.name}")
    st.write(f"**Cantidad de filas:** {filtered_df.shape[0]}")
    st.write(f"**Cantidad de columnas:** {filtered_df.shape[1]}")
    st.subheader("Tipos de variables")
    st.dataframe(build_type_summary(filtered_df), use_container_width=True, hide_index=True)

with tab_quality:
    st.subheader("Registros duplicados")
    duplicated_count = int(filtered_df.duplicated().sum())
    st.metric("Filas duplicadas adicionales", duplicated_count)
    duplicated_rows = filtered_df.loc[filtered_df.duplicated(keep=False)]
    if duplicated_rows.empty:
        st.success("No se encontraron registros completamente duplicados.")
    else:
        st.write("Todos los registros involucrados en grupos duplicados:")
        st.dataframe(duplicated_rows, use_container_width=True)

    st.subheader("Valores faltantes")
    missing = pd.DataFrame(
        {
            "Variable": filtered_df.columns,
            "Valores faltantes": filtered_df.isna().sum().values,
            "Porcentaje faltante": (filtered_df.isna().mean().values * 100),
        }
    ).sort_values("Valores faltantes", ascending=False)
    st.dataframe(
        missing.style.format({"Porcentaje faltante": "{:.2f}%"}),
        use_container_width=True,
        hide_index=True,
    )
    missing_chart = px.bar(
        missing,
        x="Variable",
        y="Porcentaje faltante",
        title="Porcentaje de valores faltantes por variable",
        labels={"Porcentaje faltante": "Porcentaje (%)"},
    )
    missing_chart.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(missing_chart, use_container_width=True)

with tab_stats:
    st.subheader("Estadísticas descriptivas")
    stats_option = st.radio(
        "Variables que deseas analizar",
        ["Todas las variables", "Solo variables numéricas", "Solo variables categóricas"],
        horizontal=True,
    )
    if stats_option in ("Todas las variables", "Solo variables numéricas"):
        st.markdown("#### Variables numéricas")
        try:
            st.dataframe(numeric_statistics(filtered_df), use_container_width=True)
        except (ValueError, TypeError) as error:
            st.info(str(error))
    if stats_option in ("Todas las variables", "Solo variables categóricas"):
        st.markdown("#### Variables categóricas y de texto")
        try:
            st.dataframe(categorical_statistics(filtered_df), use_container_width=True)
        except (ValueError, TypeError) as error:
            st.info(str(error))

with tab_distributions:
    st.subheader("Distribuciones")
    selected_variable = st.selectbox("Selecciona una variable", distribution_cols)
    selected_type = analytical_type(filtered_df[selected_variable])

    if selected_type == "Numérica":
        bins = st.slider("Número de intervalos del histograma", 5, 100, 30)
        histogram = px.histogram(
            filtered_df,
            x=selected_variable,
            nbins=bins,
            title=f"Histograma de {selected_variable}",
        )
        st.plotly_chart(histogram, use_container_width=True)

        grouping_options = ["Sin agrupación"] + categorical_cols
        group_column = st.selectbox("Agrupar diagrama de caja por", grouping_options)
        box = px.box(
            filtered_df,
            x=None if group_column == "Sin agrupación" else group_column,
            y=selected_variable,
            points="outliers",
            title=f"Diagrama de caja de {selected_variable}",
        )
        st.plotly_chart(box, use_container_width=True)
    else:
        display_series = filtered_df[selected_variable].astype("object").where(
            filtered_df[selected_variable].notna(), MISSING_LABEL
        )
        frequencies = display_series.value_counts(dropna=False).rename_axis("Categoría").reset_index(name="Frecuencia")
        truncated = len(frequencies) > MAX_CATEGORIES_CHART
        frequencies = frequencies.head(MAX_CATEGORIES_CHART)
        if truncated:
            st.info("Se muestran las 30 categorías más frecuentes.")
        bar = px.bar(
            frequencies,
            x="Categoría",
            y="Frecuencia",
            title=f"Frecuencia de {selected_variable}",
        )
        bar.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(bar, use_container_width=True)

with tab_correlations:
    st.subheader("Correlaciones")
    if len(numeric_cols) < 2:
        st.info("Se necesitan al menos dos variables numéricas para calcular correlaciones.")
    else:
        selected_correlation_cols = st.multiselect(
            "Variables numéricas",
            numeric_cols,
            default=numeric_cols,
        )
        method_label = st.selectbox("Método de correlación", ["Pearson", "Spearman", "Kendall"])
        if len(selected_correlation_cols) < 2:
            st.warning("Selecciona al menos dos variables numéricas.")
        else:
            matrix = filtered_df[selected_correlation_cols].corr(method=method_label.lower())
            heatmap = go.Figure(
                data=go.Heatmap(
                    z=matrix.values,
                    x=matrix.columns,
                    y=matrix.index,
                    zmin=-1,
                    zmax=1,
                    colorscale="RdBu",
                    reversescale=True,
                    text=np.round(matrix.values, 2),
                    texttemplate="%{text}",
                    hovertemplate="%{y} vs %{x}: %{z:.3f}<extra></extra>",
                )
            )
            heatmap.update_layout(title=f"Matriz de correlación · {method_label}")
            st.plotly_chart(heatmap, use_container_width=True)
            st.dataframe(matrix.style.format("{:.3f}"), use_container_width=True)
            st.caption("Recuerda: una correlación no implica causalidad.")

with tab_outliers:
    st.subheader("Valores atípicos mediante rango intercuartílico")
    if not numeric_cols:
        st.info("El conjunto filtrado no contiene variables numéricas para analizar.")
    else:
        outlier_columns = st.multiselect(
            "Variables numéricas",
            numeric_cols,
            default=numeric_cols,
            key="outlier_columns",
        )
        iqr_factor = st.slider("Factor IQR", 1.0, 3.0, 1.5, 0.1)
        if not outlier_columns:
            st.warning("Selecciona al menos una variable numérica.")
        else:
            outlier_summary, outlier_details = detect_outliers(filtered_df, outlier_columns, iqr_factor)
            st.metric("Detecciones de valores atípicos", len(outlier_details))
            outlier_chart = px.bar(
                outlier_summary,
                x="Variable",
                y="Cantidad de atípicos",
                title="Cantidad de valores atípicos por variable",
            )
            st.plotly_chart(outlier_chart, use_container_width=True)
            if outlier_details.empty:
                st.success("No se detectaron valores atípicos con la selección y el factor actuales.")
            else:
                st.dataframe(outlier_details, use_container_width=True, hide_index=True)
            st.download_button(
                "⬇️ Descargar valores atípicos",
                data=to_csv_bytes(outlier_details),
                file_name="valores_atipicos.csv",
                mime="text/csv",
            )
            st.caption("Un valor atípico no necesariamente representa un error.")

with tab_table:
    st.subheader("Tabla interactiva y ordenable")
    visible_columns = st.multiselect(
        "Selecciona las columnas visibles",
        list(filtered_df.columns),
        default=list(filtered_df.columns),
    )
    if not visible_columns:
        st.warning("Selecciona al menos una columna para visualizar la tabla.")
    else:
        st.dataframe(
            filtered_df[visible_columns],
            use_container_width=True,
            hide_index=True,
            height=520,
        )

st.divider()
st.info(
    "**Uso responsable de los datos:** los datos se procesan durante la sesión de la aplicación. "
    "Evita cargar información personal, confidencial o sensible. Este análisis exploratorio no "
    "reemplaza la interpretación experta. Una correlación no implica causalidad y un valor atípico "
    "no necesariamente representa un error."
)
