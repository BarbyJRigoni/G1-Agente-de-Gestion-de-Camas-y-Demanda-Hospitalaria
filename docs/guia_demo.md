# Guía de la demo en vivo – API del Agente de Gestión de Camas

**Grupo 1** · Desarrollo de Sistemas de I.A. · Instituto Terciario Malvinas Argentinas

La consigna pide mostrar el sistema funcionando en `http://localhost:8000/docs`, probar al menos 2 o 3 endpoints con un **ejemplo normal**, un **ejemplo límite** y un **ejemplo crítico**, y explicar qué datos se envían, qué responde el agente y cómo se interpreta el resultado.

Duración estimada: **7 minutos**.

---

## 0. Antes de la exposición

Desde la raíz del repositorio:

```powershell
.venv\Scripts\activate
cd backend\app
uvicorn main:app --reload
```

Tiene que aparecer `Application startup complete.`

Dejar abiertas en el navegador:
- `http://localhost:8000/salud`
- `http://localhost:8000/docs`

> Si algo falla, revisar la sección **Problemas frecuentes** al final.

---

## 1. El sistema está funcionando (30 segundos)

**Abrir:** `http://localhost:8000/salud`

**Respuesta esperada:**
```json
{"estado": "ok", "version": "1.0.0", "datasets": ["hdhi", "lengthofstay", "healthcare"], "datos_disponibles": true}
```

**Qué decir:**
> "La API está levantada y encontró los datos limpios. Trabaja con tres datasets; el principal es HDHI, un hospital real con estacionalidad."

---

## 2. La documentación automática (30 segundos)

**Abrir:** `http://localhost:8000/docs`

**Qué mostrar:** los 5 endpoints agrupados en **Agente**, **Datos** y **Sistema**.

| Método | Endpoint | Qué hace |
|---|---|---|
| GET | `/datasets` | Datasets disponibles y su capacidad |
| GET | `/estadisticas` | Indicadores históricos (ALOS) |
| GET | `/censo` | Camas ocupadas en una fecha |
| POST | `/proyeccion-camas` | Proyección de 7 días y **Alerta de Saturación** |
| GET | `/salud` | Estado del servidor |

**Qué decir:**
> "FastAPI genera esta documentación sola a partir de los modelos Pydantic. Tenemos cuatro GET para consultar datos y un POST, que es el endpoint central de la consigna."

---

## 3. KPI: tiempo medio de estancia (1 minuto)

**Endpoint:** `GET /estadisticas` → **Try it out** → `dataset = hdhi` → **Execute**

**Respuesta esperada (resumen):**
| Campo | Valor |
|---|---:|
| `internaciones` | 15.478 |
| `alos_dias` | **6,47** |
| `mediana_dias` | 5 |
| `percentil_90_dias` | 12 |
| `ingresos_promedio_dia` | 21,2 |

**Qué decir:**
> "Este es el primer KPI de la consigna: el ALOS. En HDHI, un paciente queda internado 6,5 días en promedio, y entran unos 21 pacientes por día."

---

## 4. Caso NORMAL (1 minuto)

**Endpoint:** `POST /proyeccion-camas` → **Try it out** → en **Examples** elegir **"Caso normal"** → **Execute**

**Datos que se envían:**
```json
{"dataset": "hdhi", "fecha": "2019-01-01"}
```

**Respuesta esperada:**
| Campo | Valor |
|---|---|
| `camas_ocupadas_hoy` | 125 de 190 (65,8 %) |
| `tasa_ocupacion_maxima_pct` | **68,3 %** |
| `alerta_saturacion` | **false** |
| `mensaje` | Sin alerta: la ocupación se mantiene por debajo del 90 % |

**Qué decir:**
> "Enviamos el censo del 1 de enero de 2019. El agente reconstruye qué pacientes estaban internados, estima cuántos se van a ir y cuántos van a entrar cada día, y proyecta la ocupación. En la semana no pasa del 68 %: no hay alerta."

**Cómo leer un día de la proyección:**
```json
{"fecha": "2019-01-02", "ingresos_previstos": 24.9, "altas_previstas": 23.1,
 "camas_ocupadas": 126.7, "camas_libres": 63, "tasa_ocupacion_pct": 66.7, "alerta_saturacion": false}
```
> "Para el 2 de enero se esperan 25 ingresos y 23 altas; quedarían unas 127 camas ocupadas y 63 libres."

---

## 5. Caso LÍMITE (1 minuto)

**Examples** → **"Caso limite"** → **Execute**

**Datos que se envían:**
```json
{"dataset": "hdhi", "fecha": "2019-03-05"}
```

**Respuesta esperada:**
| Campo | Valor |
|---|---|
| `camas_ocupadas_hoy` | 169 de 190 (88,9 %) |
| `tasa_ocupacion_maxima_pct` | **89,1 %** |
| `alerta_saturacion` | **false** |

**Qué decir:**
> "Acá el hospital está muy cerca del límite: la proyección llega a 89,1 %. La consigna dice que la alerta se emite cuando la ocupación **supera** el 90 %, así que todavía no corresponde. Es el caso límite."

---

## 6. Caso CRÍTICO (1 minuto)

**Examples** → **"Caso critico"** → **Execute**

**Datos que se envían:**
```json
{"dataset": "hdhi", "fecha": "2018-01-09"}
```

**Respuesta esperada:**
| Campo | Valor |
|---|---|
| `camas_ocupadas_hoy` | 190 de 190 (**100 %**) |
| `tasa_ocupacion_maxima_pct` | **94,1 %** |
| `dia_pico` | 2018-01-10 |
| `alerta_saturacion` | **true** |
| `mensaje` | **ALERTA DE SATURACION**: la ocupación proyectada supera el 90 % en 2 de 7 días. Pico: 94,1 % el 2018-01-10 |

**Qué decir:**
> "9 de enero de 2018, pleno invierno: el hospital está completo. El agente proyecta que va a seguir por encima del 90 % durante dos días, con un pico de 94 % al día siguiente, y emite la **Alerta de Saturación**. Después la ocupación baja porque las altas superan a los ingresos."

---

## 7. Extra: ¿qué pasa si el hospital pierde camas? (30 segundos)

**Examples** → **"Menos camas"** → **Execute**

**Datos que se envían:**
```json
{"dataset": "hdhi", "fecha": "2019-01-01", "capacidad": 140}
```

**Respuesta esperada:** `alerta_saturacion: true`, pico de **92,7 %**.

**Qué decir:**
> "Es el mismo día que el caso normal, pero con 140 camas en lugar de 190, por ejemplo si se cierra un sector. La misma demanda ahora genera alerta. El censo puede traer la capacidad real del hospital."

---

## 8. Extra: otro hospital (30 segundos)

Borrar el cuerpo (`Ctrl + A`), pegar y ejecutar:

```json
{"dataset": "lengthofstay", "fecha": "2012-12-01"}
```

**Respuesta esperada:** capacidad **1.280**, ocupación de hoy 82,2 %, máximo 85,2 %, sin alerta.

**Qué decir:**
> "Con el mismo código, solo cambiando el dataset, el agente proyecta otro hospital mucho más grande. La solución es general."

---

## 9. Validación de datos (30 segundos)

Pegar y ejecutar:

```json
{"dataset": "hdhi", "capacidad": 0}
```

**Respuesta esperada:** **422** – `Input should be greater than 0`

**Qué decir:**
> "Pydantic valida los datos antes de que lleguen al agente. Una capacidad de cero se rechaza y el mensaje indica qué campo falló."

Otros ejemplos, si hay tiempo:

| Cuerpo | Respuesta |
|---|---|
| `{"dataset": "otro"}` | 422 – dataset no permitido |
| `{"dias": 20}` | 422 – máximo 14 días |
| `{"fecha": "2030-01-01"}` | 400 – fecha fuera de rango, con el rango válido |

---

## Resumen de resultados esperados

| # | Prueba | Resultado |
|---|---|---|
| 1 | `/salud` | `"estado": "ok"` |
| 2 | `/estadisticas` (HDHI) | ALOS 6,47 días |
| 3 | Caso normal | Máx. 68,3 % – sin alerta |
| 4 | Caso límite | Máx. 89,1 % – sin alerta |
| 5 | Caso crítico | Máx. 94,1 % – **alerta** |
| 6 | Menos camas (140) | Máx. 92,7 % – **alerta** |
| 7 | LengthOfStay | Máx. 85,2 % – sin alerta |
| 8 | Capacidad 0 | Error 422 |

---

## Problemas frecuentes

| Problema | Causa | Solución |
|---|---|---|
| `ModuleNotFoundError: No module named 'fastapi'` (o `numpy`, `pandas`) | Entorno virtual sin activar | Desde la raíz: `.venv\Scripts\activate` |
| `No module named 'core'` | Uvicorn se ejecutó desde otra carpeta | Ejecutar desde `backend\app` |
| `"datos_disponibles": false` | Faltan los CSV procesados | Verificar `backend/data/procesados/` |
| Error 422 "JSON decode error" | JSON mal escrito (por ejemplo, un campo repetido) | `Ctrl + A`, borrar y pegar el cuerpo de nuevo |
| La página no carga | El servidor no está corriendo | Revisar la terminal y volver a ejecutar `uvicorn main:app --reload` |
| "La ejecución de scripts está deshabilitada" al activar `.venv` | Política de PowerShell | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` |
