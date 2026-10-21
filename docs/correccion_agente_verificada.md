# Corrección integrada del agente

Actualización del 17/10/2026. Rama de trabajo: prueba-sabrina.

## Qué cambia

- HDHI utiliza un modelo Ridge directo de ocupación por horizonte, ajustado solamente con observaciones disponibles al censo. Los ingresos siguen estimándose con el modelo de demanda.
- Las altas previstas se infieren del balance: ocupación anterior + ingresos - ocupación siguiente. No representan una predicción clínica individual de alta.
- Healthcare y Length of Stay conservan el modelo por estancias. Las tres fuentes se analizan por separado, sin fusionar sus pacientes ni sus hospitales.
- Los pacientes con estancias fuera del soporte histórico ya no desaparecen del cálculo por estancias. En censos reconstruidos se conservan con una advertencia; censos manuales sin soporte producen un error explícito.
- El límite superior de HDHI se calcula con errores de hasta 26 orígenes anteriores, por horizonte, con al menos 12 disponibles. Su cobertura futura no está garantizada. La excedencia mostrada es una estimación histórica suavizada, no una probabilidad clínica validada.
- La API conserva la descripción del modelo y su calibración en la respuesta. Salud comprueba cada archivo de datos requerido; los archivos ausentes producen mensajes claros.
- La fecha del pico se determina antes de redondear los porcentajes. Alcanzar exactamente el umbral no emite alerta; superarlo sí.
- Los tres datasets tienen escenarios Normal/Límite/Crítico que varían explícitamente la capacidad supuesta con igual fecha y demanda. Son simulaciones de recursos, no tres eventos históricos de saturación. No modifican config.py ni los CSV.
- Las solapas de proyección, estadísticas y evaluación se conservan; se añade una solapa de simulación UTI/general con su alcance y supuestos documentados en sectores_uti_general.md. Las consultas desactualizadas no pisan la selección más reciente, los datos anteriores se limpian mientras se calcula y una capacidad inválida muestra el error.
- Chart.js 4.4.1 se sirve localmente, con su licencia. No requiere una descarga externa al abrir el programa.

## Evidencia de validación

Datos usados: episodios revisados de HDHI (14.331; ALOS registrado 6,35 días), Healthcare limpio (54.966; 15,50 días) y Length of Stay limpio (100.000; 4,00 días).

Modelo de ocupación: ventana 365 días y regularización 100 elegidas en el período de desarrollo anterior al censo del 29/09/2018. En la validación posterior, con 26 censos entre 29/09/2018 y 23/03/2019:

| Método | Error absoluto medio en camas |
|---|---:|
| Agente anterior | 9,570 |
| Mantener la ocupación del censo | 10,626 |
| Agente corregido | 9,147 |

La mejora media frente al agente anterior es aproximadamente 4,4 %. No mejora todos los horizontes ni elimina los errores de los picos. En particular, el aumento de ocupación de enero de 2019 sigue siendo subestimado.

En 497 predicciones comparables con calibración histórica, el límite superior nominal 90 % cubrió el 93,6 % de las ocupaciones reconstruidas observadas, frente al 81,7 % de la aproximación anterior. Es evidencia exploratoria histórica, no una garantía de cobertura futura.

El error global del período completo incluye fechas usadas en desarrollo: debe distinguirse de la validación posterior. Los escenarios de capacidad no son pruebas de exactitud predictiva ni validan por sí mismos la detección de saturaciones reales. Con capacidad base de 190, las 83 ventanas evaluadas de HDHI no presentan semanas observadas por encima del 90 %; precisión y recall pueden no ser estimables.

Pruebas realizadas con los módulos reales del ZIP: 37 consultas HTTP (incluyendo errores esperados 400/422), proyección a 7/14 días, balance de camas, metadatos, salud, estadísticas, demanda y evaluación; escenarios de los tres datasets; carga del gráfico local; interacción DOM con API real para selección de datasets, solapas, errores y respuestas que llegan fuera de orden. También se comprobó que alterar internaciones posteriores al censo no cambia la predicción ni su calibración. Las pruebas DOM no sustituyen una inspección visual del navegador de Windows.

## Límites de los datos

Las capacidades 190/1280/570 son supuestos de la simulación, no capacidades reales documentadas por los CSV. Healthcare es sintético y reúne múltiples hospitales; Length of Stay reúne establecimientos. HDHI es una cohorte de episodios consolidada bajo supuestos de identidad y con fechas reconstruidas retrospectivamente. Esta selección y la reconstrucción pueden sesgar los resultados; no equivalen a una validación prospectiva hospitalaria.

La actualización no modifica los CSV ni resuelve la identidad real de pacientes. Los diagnósticos desconocidos siguen siendo desconocidos y las comorbilidades pueden superponerse.

## Inicio

Desde la raíz del proyecto con el entorno virtual activo:

```powershell
python -m uvicorn main:app --app-dir backend/app --reload
```

Abrir http://127.0.0.1:8000 y recargar con Ctrl+F5. Documentación en /docs; comprobación en /salud.
