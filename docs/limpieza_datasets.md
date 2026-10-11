# Informe de limpieza y preparación de datasets

Se realizó la carga, exploración, limpieza y preparación de tres datasets hospitalarios utilizando Python y la librería Pandas.
El objetivo fue obtener datos organizados y confiables para calcular estadísticas de internación y utilizarlas posteriormente en el agente inteligente y la API.
Los tres datasets se procesaron por separado porque provienen de distintas fuentes y no tienen un identificador común que permita relacionar sus pacientes.

## 2. Datasets utilizados

| Dataset | Registros originales | Registros finales | Duración promedio |
|---|---:|---:|---:|
| HDHI Admission | 15.757 | 15.757 | 6,42 días |
| LengthOfStay | 100.000 | 100.000 | 4 días |
| Healthcare | 55.500 | 54.966 | 15,50 días |

Los archivos originales se encuentran en `backend/data/`.

## 3. Limpieza realizada

### 3.1. HDHI Admission
Este dataset contiene información de admisiones hospitalarias, edades, diagnósticos, fechas de ingreso y egreso, y duración de internación.

**Problemas encontrados:**
- Nombres de columnas con espacios, puntos y caracteres especiales.
- Valores faltantes representados como `EMPTY`.
- Fechas con diferentes formatos.
- Valores clínicos faltantes, especialmente en BNP y EF.

**Soluciones aplicadas:**
- Se estandarizaron los nombres de las columnas utilizando minúsculas y guiones bajos.
- Se reemplazaron los valores `EMPTY` por valores nulos reconocidos por Pandas.
- Se convirtieron las columnas clínicas correspondientes a formato numérico.
- Se revisaron las fechas comparándolas con la duración registrada de cada internación.
- Se conservaron los valores faltantes y las fechas originales para evitar modificar información sin fundamento.

**Resultados:**
- 15.757 registros procesados.
- 0 filas completamente duplicadas.
- 15.478 registros con fechas coherentes.
- 216 registros con fechas ambiguas.
- 63 registros sin coincidencia entre fechas y duración.
- Duración promedio de internación: **6,42 días**.

Las fechas que no pudieron validarse de forma confiable no se utilizaron como fechas confirmadas.

### 3.2. LengthOfStay

Este dataset contiene información sobre duración de internaciones, fechas de ingreso y alta, y establecimientos hospitalarios.

**Revisiones realizadas:**
- Identificación de valores nulos y duplicados.
- Conversión de fechas al formato adecuado.
- Verificación de la duración de internación.
- Conservación de las fechas originales.

**Resultados:**
- 100.000 registros procesados.
- 0 valores nulos.
- 0 filas duplicadas.
- Todas las fechas fueron procesadas correctamente.
- Las duraciones registradas coincidieron con las fechas.
- Duración promedio: **4 días**.

No fue necesario eliminar registros.

### 3.3. Healthcare

Este dataset contiene información sobre pacientes, edad, patologías, hospitales, tipos de admisión y fechas de internación.

**Problemas encontrados:**
- Nombres de columnas que necesitaban estandarización.
- 534 filas exactamente duplicadas.
- Necesidad de calcular la duración de cada internación.

**Soluciones aplicadas:**
- Se estandarizaron los nombres de las columnas.
- Se convirtieron las fechas de ingreso y egreso.
- Se creó la columna `duracion_internacion`.
- Se eliminaron las 534 filas exactamente duplicadas.
- Se conservaron las fechas originales.

**Resultados:**
- Registros originales: 55.500.
- Registros finales: 54.966.
- 0 valores nulos.
- 0 fechas inválidas.
- Duración promedio: **15,50 días**.

## 4. Organización de los scripts

Los archivos de Python se encuentran en `backend/app/data/`.

| Archivo | Función |
|---|---|
| `loader.py` | Carga los tres datasets y permite revisar sus columnas, registros, valores nulos y duplicados. |
| `limpieza_hdhi.py` | Realiza la limpieza de HDHI y la validación de sus fechas. |
| `limpieza_lengthofstay.py` | Procesa LengthOfStay y comprueba las duraciones de internación. |
| `limpieza_healthcare.py` | Limpia Healthcare, elimina duplicados exactos y calcula la duración de internación. |

Se utilizó un script de limpieza independiente para cada dataset porque tienen estructuras y problemas diferentes.

Esto facilita corregir, revisar o ejecutar nuevamente una limpieza sin afectar las demás.

## 5. Archivos generados

Los resultados se guardaron en `backend/data/procesados/`:

- `hdhi_limpio.csv`
- `lengthofstay_limpio.csv`
- `healthcare_limpio.csv`

Los datasets originales se conservaron sin modificaciones.

Los archivos procesados son los que se utilizan para realizar los análisis estadísticos.

## 6. Análisis inicial con Pandas

El archivo `backend/app/services/analisis.py` utiliza los CSV procesados para obtener los primeros indicadores.

**HDHI Admission**
- Total de internaciones: 15.757.
- Duración promedio: 6,42 días.
- Admisiones de emergencia: 10.924.
- Admisiones OPD: 4.833.

**LengthOfStay**
- Total de internaciones: 100.000.
- Duración promedio: 4 días.
- Se identificaron cinco establecimientos hospitalarios: A, B, C, D y E.

**Healthcare**
- Total de internaciones: 54.966.
- Duración promedio: 15,50 días.
- Se identificaron patologías como diabetes, hipertensión, artritis, obesidad, cáncer y asma.

Estos indicadores corresponden a cada dataset por separado y no deben interpretarse como resultados de un único hospital.

## 7. Utilización de los datos en el proyecto

### API – FastAPI

Los endpoints pueden utilizar las funciones de `analisis.py` para consultar y devolver los indicadores estadísticos.

De esta manera, la API trabaja con información ya procesada, sin repetir la limpieza de los datasets.

### Agente inteligente

El agente puede utilizar las fechas de ingreso, egreso y duración de internación para obtener estadísticas históricas que permitan estimar ingresos, altas y demanda de camas durante los próximos siete días.

### Alertas de saturación

Las proyecciones del agente pueden compararse con la capacidad hospitalaria recibida mediante el censo actual.

Si la ocupación proyectada supera el 90 % de esa capacidad, el sistema podrá generar una alerta de saturación.

Los datasets históricos no incluyen una capacidad total de camas confirmada, por lo que este dato deberá recibirse mediante el censo hospitalario o definirse explícitamente para las pruebas.

## 8. Resumen del trabajo realizado

Se completó la primera etapa de limpieza y preparación de los tres datasets con Pandas.

Se revisaron valores nulos, duplicados, formatos de fechas, nombres de columnas y duraciones de internación.

Los resultados se guardaron en archivos independientes, conservando los datos originales.

Esta organización permite que el análisis estadístico, la API y el agente inteligente trabajen sobre datos previamente preparados y consistentes.

