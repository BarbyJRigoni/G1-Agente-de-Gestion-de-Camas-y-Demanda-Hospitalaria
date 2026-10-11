# Análisis estadístico con Pandas

Analizar los datos históricos de internaciones hospitalarias con Pandas para obtener indicadores que ayuden a desarrollar el agente inteligente de predicción de demanda y disponibilidad de camas.

## 2. Datasets utilizados

Se trabajó con tres datasets previamente limpiados:

| Dataset | Registros | Estancia promedio |
|---|---:|---:|
| HDHI | 15.757 | 6,42 días |
| LengthOfStay | 100.000 | 4,00 días |
| Healthcare | 54.966 | 15,50 días |

Los tres archivos se procesan por separado porque no comparten un identificador que permita relacionar sus pacientes mediante `pd.merge()`.

**Importante:** Los análisis estadísticos más completos se realizaron con Healthcare.

## 3. Análisis realizados

Se desarrollaron los siguientes cálculos:

- **ALOS por patología:** duración promedio de internación según enfermedad.
- **ALOS por grupo etario:** duración promedio según rango de edad.
- **Estadísticas:** promedio, mediana, desviación estándar y percentiles.
- **Ingresos diarios:** cantidad de pacientes que ingresan por fecha.
- **Egresos diarios:** cantidad de pacientes que finalizan su internación por fecha.
- **Balance diario:** diferencia entre ingresos y egresos, incluyendo su acumulado.

### Resultados principales de Healthcare

| Indicador | Resultado |
|---|---:|
| Internaciones analizadas | 54.966 |
| ALOS general | 15,50 días |
| Desviación estándar | 8,66 días |
| Mediana | 15 días |
| Percentil 25 | 8 días |
| Percentil 75 | 23 días |
| Percentil 90 | 28 días |
| Promedio de ingresos diarios | 30,09 |
| Promedio de egresos diarios | 29,62 |

**Validación:** se contabilizaron 54.966 ingresos y 54.966 egresos en 1.857 días. El balance acumulado final fue 0.

## 4. Código y funciones disponibles

Los cálculos están implementados en:

`backend/app/services/analisis.py`

| Función | Utilidad |
|---|---|
| `analizar_hdhi()` | Análisis general de HDHI |
| `analizar_lengthofstay()` | Análisis general de LengthOfStay |
| `analizar_healthcare()` | Análisis general de Healthcare |
| `calcular_alos_por_patologia()` | ALOS según enfermedad |
| `calcular_alos_por_grupo_etario()` | ALOS según edad |
| `calcular_estadisticas_estancia()` | Promedios, desviación y percentiles |
| `calcular_ingresos_diarios()` | Ingresos históricos diarios |
| `calcular_egresos_diarios()` | Egresos históricos diarios |
| `calcular_balance_diario()` | Balance de ingresos y egresos |
| `obtener_indicadores_generales()` | Indicadores principales en un diccionario |

Para ejecutar el análisis desde la carpeta principal del proyecto:

python backend/app/services/analisis.py


## 5. Utilidad para el agente inteligente

**Para Darío (agente y predicción):**

Puede utilizar los indicadores históricos de ingresos, egresos y duración de internación para desarrollar la proyección de demanda de los próximos **7 días**.

La proyección de ocupación requiere además un censo actual y la capacidad hospitalaria.

**Para Bárbara (FastAPI):**

Puede importar las funciones de `analisis.py` para crear los endpoints que permitan consultar los indicadores y conectar el agente con la API.

Uno de los endpoints solicitados es `/proyeccion-camas`, que debe recibir el censo hospitalario y devolver la proyección semanal.

## 6. Limitaciones y aclaraciones

- Los tres datasets se analizaron individualmente; no se unificaron sus registros.
- Los indicadores avanzados corresponden principalmente a Healthcare.
- No se dispone de capacidad real de camas ni de un censo hospitalario actual.
- El balance acumulado no representa la ocupación real de camas.
- Para generar alertas de saturación superiores al **90 %** y diferenciar camas generales y UCI, se necesitan datos adicionales o una simulación autorizada por el profesor.

## 7. Conclusión

Se completó el procesamiento y análisis de los tres datasets, obteniendo indicadores históricos de internación.

Estos resultados quedan disponibles para que el equipo continúe con la predicción de demanda, la lógica del agente inteligente y su integración con FastAPI.
