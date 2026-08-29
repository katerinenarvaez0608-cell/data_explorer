# Explorador automático de datos

Aplicación web desarrollada con Streamlit para cargar conjuntos de datos y ejecutar un análisis exploratorio automático, sin depender de un archivo predeterminado ni guardar permanentemente los datos cargados.

## Funcionalidades

- Carga de archivos desde el navegador.
- Filtros interactivos por fechas, categorías y rangos numéricos.
- Indicadores de filas, columnas, duplicados y valores faltantes.
- Inventario de variables con tipo Pandas y tipo analítico.
- Revisión de registros duplicados y valores faltantes.
- Estadísticas descriptivas numéricas y categóricas.
- Histogramas, diagramas de caja y gráficos de frecuencia con Plotly.
- Matrices de correlación Pearson, Spearman y Kendall.
- Detección de valores atípicos mediante el método IQR.
- Tabla interactiva con selección de columnas.
- Descarga en CSV de los datos filtrados y los valores atípicos.

## Formatos admitidos

- CSV (`.csv`)
- Excel moderno (`.xlsx`), leído con `openpyxl`
- Excel 97-2003 (`.xls`), leído con `xlrd`

Para libros de Excel, la aplicación analiza la primera hoja. Los CSV se leen intentando detectar automáticamente el separador. Si un CSV no puede leerse como UTF-8, se intenta la codificación Latin-1.

## Estructura del repositorio

```text
explorador-automatico-datos/
├── app.py
├── README.md
└── requirements.txt
```

No se incluye ningún conjunto de datos.

## Instalación

Se recomienda Python 3.10 o superior.

1. Clona el repositorio y entra en su carpeta:

   ```bash
   git clone URL_DE_TU_REPOSITORIO
   cd explorador-automatico-datos
   ```

2. Crea y activa un entorno virtual:

   En Windows PowerShell:

   ```powershell
   py -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

   En macOS o Linux:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Instala las dependencias:

   ```bash
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

## Ejecución local

```bash
streamlit run app.py
```

Streamlit abrirá la aplicación en el navegador. Si no se abre automáticamente, usa la dirección local que se muestre en la terminal.

## Despliegue en Streamlit Community Cloud

1. Publica estos tres archivos en un repositorio de GitHub.
2. Accede a Streamlit Community Cloud e inicia sesión con GitHub.
3. Selecciona la opción para crear una aplicación nueva.
4. Elige el repositorio, la rama y `app.py` como archivo principal.
5. Inicia el despliegue. La plataforma instalará las dependencias de `requirements.txt`.

La aplicación no necesita secretos, claves ni variables de entorno.

## Privacidad y uso responsable

Los datos cargados se procesan durante la sesión de la aplicación. No cargues información personal, confidencial, sensible o sujeta a restricciones de uso. Revisa también la política aplicable a la infraestructura donde despliegues la aplicación.

El resultado es exploratorio y no reemplaza el criterio de una persona experta. Una correlación no implica causalidad. Un valor atípico no necesariamente representa un error.

## Limitaciones conocidas

- En los libros de Excel se lee únicamente la primera hoja.
- El procesamiento está limitado por la memoria y los recursos disponibles en el equipo o en Streamlit Community Cloud.
- La detección automática de fechas se aplica a columnas cuyo nombre contiene `fecha` o `date` y exige que una proporción suficiente de los valores no nulos pueda convertirse.
- Las columnas de texto se distinguen de las categóricas mediante una regla basada en cardinalidad; esta clasificación es orientativa.
- Para variables categóricas con alta cardinalidad, el gráfico muestra las 30 categorías más frecuentes.
- El método IQR es un criterio estadístico general y puede no ser apropiado para todos los dominios.
- Los cálculos de correlación usan pares de valores disponibles; los faltantes pueden hacer que algunas celdas de la matriz no tengan resultado.
