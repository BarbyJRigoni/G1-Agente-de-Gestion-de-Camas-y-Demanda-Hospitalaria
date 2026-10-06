# Agente de Gestión de Camas y Demanda Hospitalaria

Trabajo Práctico Final – Agentes Inteligentes 3.0 – Desarrollo de Sistemas de I.A. 2026 (Grupo 1, Salud)

Agente que prevé la ocupación de camas de una red hospitalaria de 5 sedes para los próximos 7 días a partir del censo actual, y emite una **Alerta de Saturación** cuando la proyección supera el 90 % de la capacidad.

## Cómo correrlo

Requiere Python 3.10 o superior.

```bash
cd backend
python -m venv venv
venv\Scripts\activate            # Windows
source venv/bin/activate         # Linux / Mac
pip install -r requirements.txt  # o: pip install pandas fastapi uvicorn
uvicorn main:app --reload
```

- Documentación interactiva: http://localhost:8000/docs
- Dashboard: http://localhost:8000/
- Pruebas: `pytest -q` (desde `backend/`)
- Docker (desde la raíz): `docker build -t agente-camas . && docker run -p 8000:8000 agente-camas`

## Dataset

**Hospital Length of Stay** (Kaggle), archivo `LengthOfStay.csv`: 100.000 internaciones de 2012 en 5 sedes (`facid` A-E), con 28 columnas:

- **Fechas:** ingreso (`vdate`) y alta (`discharged`).
- **Estancia:** días internado (`lengthofstay`, de 1 a 17).
- **Paciente:** sexo y reingresos en los últimos 180 días (`rcount`, de 0 a "5+").
- **Comorbilidades:** 11 banderas 0/1 (neumonía, asma, diálisis, desnutrición, etc.).
- **Diagnósticos:** cantidad de diagnósticos secundarios.
- **Laboratorio y signos vitales:** hematocrito, neutrófilos, sodio, glucosa, urea, creatinina, IMC, pulso y respiración.

Lo publicó originalmente Microsoft como dataset de ejemplo. Conviene chequear en su ficha de Kaggle si figura como real o simulado, por si lo preguntan.

### Diferencias con la consigna y cómo se resolvieron

| La consigna pide | El dataset trae | Decisión |
|---|---|---|
| ALOS por patología | 11 banderas de comorbilidad, sin diagnóstico principal | Se deriva una **patología principal** tomando la comorbilidad más grave presente según un orden clínico fijo, más "Sin comorbilidad registrada" (57 %). También se guarda la cantidad de comorbilidades. |
| ALOS por grupo etario | **No hay edad** | Se reemplaza por **perfil de reingresos** (0, 1, 2-3, 4+). Es la variable que más diferencia la estancia: 2,7, 3,7, 5,7 y 7,7 días. Conviene avisarle al profe y explicarlo en la exposición. |
| Terapia intensiva e internación general | 5 sedes, sin distinguir tipo de cama | El agente proyecta **por sede y para toda la red**. Esto permite una recomendación extra: derivar entre sedes. |
| Capacidad del hospital | No informa camas | Se fijó por sede (A 330, B 330, C 85, D 78, E 520) para que la ocupación media histórica quede en ~80 % y los picos pasen el 90 %, como en un hospital real con cuellos de botella. Es configurable en `config.py` y en cada pedido. |

## Capa de datos (Pandas)

Cada paso queda registrado y se ve en `GET /datos/calidad`:

| Paso | Registros | Decisión |
|---|---|---|
| Nulos y duplicados | 0 | Verificados |
| Reingresos como texto "5+" | 4.987 | Convertidos a 5 (numérico) |
| Fechas en formato m/d/aaaa | 100.000 | Convertidas a fecha |
| Estancia vs. (alta − ingreso) | 0 | Verificado: coherente |
| Glucosa ≤ 0 (imposible) | 1 | Pasada a nulo e imputada con la mediana |
| Laboratorio extremo (fuera de p0,5-p99,5) | 7.840 | Recortado al percentil (winsorización): se corrige el valor sin perder al paciente |

El dataset viene limpio y se conserva el 100 %, pero cada problema se chequea igual porque el sistema tiene que resistir datos nuevos más sucios.

Columnas nuevas:
- `patologia` y `n_comorbilidades`.
- `perfil_reingreso`.
- `score_complejidad` (0-100): 40 % comorbilidades, 40 % reingresos y 20 % diagnósticos secundarios.
- Laboratorio normalizado con z-score (`*_z`).
- `los_zscore`: estancia estandarizada dentro de sede y patología.
- `los_outlier`: regla IQR; se marcan, no se borran.
- `mes`, `dia_semana` y `estacion`.

Métricas en `GET /estadisticas/alos`, por patología y perfil de reingreso (o por sede): casos, ALOS, mediana, desvío estándar, percentil 90, coeficiente de variación, comorbilidades promedio, score de complejidad e índice de estancia (ALOS del grupo / ALOS global).

## KPIs clave

`/proyeccion-camas` devuelve un bloque `kpis`, por sede y para la red:

- **Tasa de Ocupación Proyectada (%)**: promedio esperado de la semana, más el pico y las camas disponibles el último día (negativo = déficit).
- **Tiempo Medio de Estancia (ALOS)**: red 4,0 días; A 3,3, B 3,3, C 4,9, D 4,8 y E 5,2.

## Lógica del agente

El agente sigue cuatro pasos: percibir, estimar, decidir y recomendar.

1. **Percibe** el censo: capacidad por sede y cada paciente con su sede, patología principal, reingresos y días internado.
2. **Estima** día por día y sede por sede:
   - Para cada paciente, la probabilidad de seguir internado en el día *k* sale de la curva de permanencia de su estrato: `P = S(d + k) / S(d)`, donde `S(d)` es la proporción histórica que estuvo más de *d* días. Si el estrato (sede + patología + perfil de reingreso) tiene menos de 30 casos, usa sede + patología, y si no, la sede.
   - Los ingresos esperados por día salen del modelo de demanda, escalados al tamaño de la sede y por `factor_demanda`.
   - Los que ingresan durante la semana también pueden irse antes del día 7.
   - Ocupación esperada = Σ probabilidades de los internados + ingresos que siguen. Con la varianza (Bernoulli + Poisson) calcula un escenario pesimista (P90) y la probabilidad de superar el umbral.
   - Altas del día = ocupadas el día anterior + ingresos − ocupadas hoy.
3. **Decide** un nivel por día: Normal (≤75 %), Precaución (≤85 %), Riesgo alto (≤90 %) y Saturación (>90 %), y emite la **Alerta de Saturación**. Además calcula un índice de presión de 0 a 100.
4. **Recomienda:** postergar internaciones programables y adelantar altas en las sedes saturadas, **redistribuir ingresos hacia las sedes con margen** y revisar pacientes cuya estancia supera el percentil 90 de su grupo.

### Modelos

**Ingresos por día.** Se comparan tres métodos con validación temporal (los últimos 90 días no se usan para entrenar):

| Sede | Regresión (MAE) | Estacional (MAE) | Media (MAE) | Elegido |
|---|---|---|---|---|
| A | 7,84 | 7,31 | 6,80 | Media |
| B | 22,40 | 8,59 | 7,20 | Media |
| C | 3,71 | 3,62 | 3,07 | Media |
| D | 3,17 | 3,09 | 2,98 | Media |
| E | 9,97 | 8,18 | 7,17 | Media |

En este dataset los ingresos no tienen estacionalidad: son unos 82 por día en A, B y E y unos 12 en C y D, todo el año. Los modelos más complejos sobreajustan y la media gana. El agente lo detecta solo y usa la media. Vale la pena mostrarlo en la exposición: elegir el modelo con validación, en vez de asumir que el más sofisticado es el mejor.

**Estancia por paciente (bonus ML).** Una regresión lineal con sede, sexo, reingresos, comorbilidades, diagnósticos secundarios y laboratorio (`POST /estimar-estancia`). Con 80/20 de validación da **R² 0,77 y error medio de 0,87 días**, contra 1,9 días si se usa siempre el promedio. Además devuelve qué variables pesan más; los reingresos son las que más suman.

## Endpoints

| Método | Ruta | Para qué |
|---|---|---|
| POST | `/proyeccion-camas` | Recibe el censo y devuelve la proyección semanal por sede y KPIs |
| POST | `/estimar-estancia` | Estancia esperada de un paciente nuevo (modelo ML) |
| GET | `/censo-ejemplo/{normal\|limite\|critico}` | Censo real reconstruido del dataset, listo para el POST |
| GET | `/proyeccion-camas/escenario/{escenario}` | Atajo: arma el censo y lo proyecta |
| GET | `/estadisticas/alos` | ALOS con filtros (`agrupar_por`, `patologia`, `perfil_reingreso`, `ordenar_por`) |
| GET | `/estadisticas/estacionalidad` | Ingresos promedio por mes y día de semana |
| GET | `/estadisticas/ocupacion-historica` | Ocupación mensual por sede |
| GET | `/datos/calidad` | Reporte de limpieza |
| GET | `/modelo/metricas` | Validación de ambos modelos |
| GET | `/salud` | Estado del servicio |

**Validaciones (Pydantic):**
- Sede A-E (acepta "sede c").
- Patología del catálogo (acepta mayúsculas y sin tildes).
- Reingresos numéricos (acepta "5+").
- Días internado entre 0 y 365.
- Ids sin repetir.
- Cada paciente de una sede presente en `capacidad`, sin superarla.
- Horizonte entre 1 y 14 días, umbral entre 0,5 y 1, `factor_demanda` entre 0,5 y 3.
- Laboratorio en rangos fisiológicos.

Errores: 422 indicando el campo, 503 si no se cargó el dataset y 500 controlado.

## Guion de demo (7 min)

1. En `/docs`, ejecutar `GET /datos/calidad` y después `GET /estadisticas/alos?agrupar_por=perfil_reingreso` para mostrar que los reingresos casi triplican la estancia.
2. **Normal:** `GET /censo-ejemplo/normal`, copiar y pegar en `POST /proyeccion-camas`. Resultado: 2/4/2012, 1.016 internados, red al 80 % y sin alerta.
3. **Límite:** igual con `limite`. Resultado: 24/10/2012, sedes A, B y E arrancan por encima del 85 %, nivel RIESGO_ALTO sin alerta, y el agente recomienda monitorear.
4. **Crítico:** igual con `critico`. Resultado: 17/6/2012, red al 90 % y `factor_demanda` 1,1. **ALERTA DE SATURACIÓN** en B, C y E, índice de presión 82,5, y recomienda **derivar hacia la sede D**, que tiene ~15 camas libres.
5. **ML:** `POST /estimar-estancia` con un paciente con 5+ reingresos y neumonía. Resultado: ~9 días y los factores que más pesan.
6. **Validación:** poner sede "Z" o un paciente de una sede que no está en `capacidad` para mostrar el 422.
7. Abrir el dashboard en `/`, cambiar de escenario y mover el control de días.

## Estructura

```
proyecto/
├── Dockerfile
├── backend/
│   ├── main.py                    → atajo para `uvicorn main:app`
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py                → FastAPI: app, lifespan, errores, dashboard
│   │   ├── core/config.py         → rutas, sedes, capacidad, catálogos, umbrales
│   │   ├── core/normalizacion.py  → unificación de textos (sede, patología, reingresos)
│   │   ├── data/loader.py         → carga + limpieza con pandas + reporte de calidad
│   │   ├── services/
│   │   │   ├── estancia.py        → ALOS y curvas de permanencia por estrato
│   │   │   ├── demanda.py         → modelos de ingresos y validación temporal
│   │   │   ├── modelo_estancia.py → regresión de estancia por paciente (ML)
│   │   │   ├── ocupacion.py       → ocupación histórica y censos reconstruidos
│   │   │   └── alertas.py         → semáforo, índice de presión, recomendaciones
│   │   ├── agents/camas_agent.py  → orquestador: percibe, estima, decide, recomienda
│   │   ├── schemas/camas.py       → modelos Pydantic de entrada y salida
│   │   └── routers/               → camas.py y estadisticas.py
│   ├── data/LengthOfStay.csv      → dataset de Kaggle
│   └── tests/test_api.py
└── frontend/index.html            → dashboard (Chart.js)
```


## Limitaciones y mejoras

- No tiene edad ni tipo de cama (UTI / sala). Con un dataset que los traiga se vuelve al análisis por grupo etario y área sin cambiar el agente.
- Hay un solo año de datos, así que no se puede medir estacionalidad interanual.
- La capacidad es supuesta: en producción vendría del sistema de camas del hospital.
- En los escenarios demo, los modelos se entrenaron con todo 2012, incluido lo posterior a la fecha del censo. En producción se reentrenarían solo con el pasado.
- Mejoras posibles: usar el modelo de estancia individual dentro de la proyección (hoy usa curvas por estrato), gradient boosting, integración con la HCE y despliegue en Render o Railway con el Dockerfile incluido.
