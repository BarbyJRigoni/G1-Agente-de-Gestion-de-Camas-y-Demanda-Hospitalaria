# Mejoras de claridad y selección temporal

Esta actualización conserva las predicciones numéricas, los CSV, las capacidades base y los escenarios de recursos. Mejora la interpretación y la trazabilidad de lo que muestra el programa.

- El mensaje separa CENSO (ocupación reconstruida en la fecha elegida) y PRÓXIMOS DÍAS (pronóstico). Si el censo ya supera el 90 %, se muestra en rojo aunque el pronóstico futuro baje del umbral.
- La capacidad dispone de espacio para números de cuatro cifras y mayores.
- «ALOS de egresos anteriores al censo» identifica el promedio utilizado por el agente. Incluye internaciones con egreso anterior a esa fecha; no es necesariamente igual al promedio de toda la cohorte.
- La tabla de métodos de ingresos se presenta como comparación retrospectiva del historial completo. No se identifica su ganador como el método usado en todas las consultas históricas.
- La proyección informa fecha_corte_modelo y alerta_ocupacion_censo; alerta_saturacion conserva su significado de saturación proyectada.
- /modelo/demanda y /modelo/backtest aceptan fecha=AAAA-MM-DD para comparar exclusivamente con historia hasta esa fecha. Sin fecha, conservan la evaluación general del historial completo. Fechas fuera de rango o sin 148 días de historia producen error 400.
- Se retiraron calcular_tasa_ingresos y SEMANAS_HISTORIA, que ya no se utilizaban.
- La interfaz usa fuentes del sistema. Chart.js continúa sirviéndose desde frontend/vendor. Abrir la aplicación no requiere Google Fonts ni un CDN de gráficos.

## Ejemplo para verificar la selección en la demo

Abrir:

http://127.0.0.1:8000/modelo/demanda?dataset=hdhi&fecha=2019-01-01

Comprobar que alcance_evaluacion sea hasta_el_censo, que fecha_corte sea 2019-01-01 y que el período evaluado no termine después de esa fecha. En la cohorte revisada, para este ejemplo se elige regresion. Los métodos pueden diferir en otros censos.

## Lectura de un escenario

En Healthcare con 505 camas simuladas, el censo de referencia ocupa 455 camas (90,1 %). Puede existir ocupación sobre el umbral en el censo y, al mismo tiempo, una proyección futura máxima de 89,9 %. Los dos estados describen fechas diferentes y se muestran por separado.

Normal/Límite/Crítico conservan fecha y demanda y modifican la capacidad supuesta. No son tres eventos históricos distintos. El censo y la curva observada son reconstrucciones del dataset, no un sistema conectado a un hospital en tiempo real.

## Alcance

Esta actualización no cambia la exactitud del modelo ni constituye una validación prospectiva nueva. Se mantienen las métricas, supuestos y limitaciones documentados en correccion_agente_verificada.md.
