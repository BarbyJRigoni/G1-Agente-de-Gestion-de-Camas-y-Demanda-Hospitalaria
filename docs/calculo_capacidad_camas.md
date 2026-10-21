# Cálculo de la capacidad de camas

**Archivo relacionado:** `backend/app/core/config.py` (valores `capacidad_total`)

---

## 1. El problema

Para decir *"el hospital está al 90 %"* hace falta saber **cuántas camas tiene**.
Los datasets no traen ese dato: solo informan qué pacientes ingresaron y cuándo se fueron.
Por eso la capacidad se **estima** a partir de lo que pasó en el hospital.

---

## 2. Paso 1 – Contar las camas ocupadas cada día

Para cada día del historial se cuenta cuántos pacientes estaban internados esa noche: los que ya habían ingresado y todavía no se habían ido.

Ejemplo con HDHI:

| Día | Camas ocupadas |
|---|---:|
| 1 de mayo | 110 |
| 2 de mayo | 118 |
| 3 de mayo | 105 |
| … (610 días en total) | … |
| 9 de enero | 190 |

En HDHI hubo, en promedio, **116 camas ocupadas**, y el día más lleno llegó a **190**.

Se descartan los primeros y los últimos 60 días del registro. Al inicio el hospital "arranca vacío", porque no figuran los pacientes que ya estaban internados antes. Al final faltan los ingresos posteriores. En los dos casos la ocupación saldría falsamente baja.

---

## 3. Paso 2 – El percentil 95

Si se **ordenan los 610 días de menos ocupado a más ocupado**, como una fila de personas de la más baja a la más alta, el **percentil 95** es el valor que queda en la posición 95 de cada 100. Es decir:

- el **95 % de los días** tuvo esa ocupación **o menos**;
- solo el **5 % de los días** (unos 30 de 610) estuvo más lleno.

En HDHI, el percentil 95 es **163 camas**:

> *"Casi todos los días hubo 163 camas ocupadas o menos; solo unos 30 días hubo más."*

Esos días son los **picos de demanda**, justo los que la alerta tiene que detectar.

---

## 4. Paso 3 – De ahí sale la capacidad

La consigna dice que la alerta se emite cuando la ocupación **supera el 90 %**.
Queremos que ese 90 % coincida con los picos, es decir, con las 163 camas:

> **163 camas = 90 % de la capacidad**

Entonces:

> **capacidad = 163 ÷ 0,90 = 181 camas** → redondeado hacia arriba a la decena: **190 camas**

---

## 5. Comprobación

Con 190 camas, el 90 % equivale a **171 camas**:

| Situación | Camas ocupadas | Ocupación | ¿Alerta? |
|---|---:|---:|---|
| Día normal | 116 | 61 % | No |
| Día cargado | 160 | 84 % | No |
| Día de pico | 180 | 95 % | **Sí** |

La alerta se activa solo en los peores días, que es lo que se busca.

Por el redondeo hacia arriba, el umbral real (171 camas) queda un poco por encima del percentil 95 (163). Por eso la alerta salta en **menos del 5 %** de los días: solo en los picos más altos.

---

## 6. ¿Por qué este método y no otro?

| Opción | Resultado |
|---|---|
| Capacidad = promedio (116) | El hospital estaría "lleno" la mitad de los días: la alerta saltaría todo el tiempo |
| Capacidad = un número grande (300) | Nunca llegaría al 90 %: la alerta no saltaría nunca |
| Capacidad = máximo histórico | Depende de un solo día excepcional |
| **Capacidad según el percentil 95** | **La alerta salta solo en los picos reales de demanda** ✅ |

---

## 7. Resultados de los tres datasets

Se aplicó la misma cuenta a cada dataset:

| Dataset | Días analizados | Ocupación promedio | Máximo | Percentil 95 | ÷ 0,90 | Capacidad |
|---|---:|---:|---:|---:|---:|---:|
| HDHI | 610 | 115,7 | 190 | 163 | 181,1 | **190** |
| LengthOfStay | 247 | 1.090,9 | 1.187 | 1.144 | 1.271,3 | **1.280** |
| Healthcare | 1.707 | 466,4 | 552 | 508 | 564,4 | **570** |

---

## 8. Código utilizado para el cálculo

El cálculo se hizo una sola vez, para obtener los valores que figuran en `config.py`.
El código queda registrado acá como referencia; **no forma parte del proyecto**.
Usa las funciones `cargar_internaciones()` y `censo_en_fecha()` del agente.

```python
import math
import pandas as pd

from core import config
from agents.inventario_agent import cargar_internaciones, censo_en_fecha

for dataset in config.DATASETS:
    internaciones = cargar_internaciones(dataset)

    # 1. Dias a analizar: se descartan los primeros y ultimos 60 dias,
    #    porque al inicio el hospital "arranca vacio" y al final faltan ingresos.
    inicio = internaciones["ingreso"].min() + pd.Timedelta(days=60)
    fin = internaciones["ingreso"].max() - pd.Timedelta(days=60)
    dias = pd.date_range(inicio, fin)

    # 2. Ocupacion de cada noche: pacientes que ingresaron ese dia o antes
    #    y todavia no se fueron.
    ocupacion = pd.Series([len(censo_en_fecha(internaciones, d)) for d in dias], index=dias)

    # 3. Percentil 95: nivel que solo se supera el 5 % de los dias.
    p95 = ocupacion.quantile(0.95)

    # 4. Capacidad: el p95 tiene que quedar en el 90 % -> p95 / 0,90,
    #    redondeado hacia arriba a la decena.
    capacidad = math.ceil(p95 / 0.90 / 10) * 10

    print(f"{dataset:13s} | dias: {len(dias):4d} | promedio: {ocupacion.mean():7.1f} | "
          f"maximo: {ocupacion.max():5d} | p95: {p95:7.1f} | capacidad: {capacidad}")
```

Resultado obtenido:

```
hdhi          | dias:  610 | promedio:   115.7 | maximo:   190 | p95:   163.0 | capacidad: 190
lengthofstay  | dias:  247 | promedio:  1090.9 | maximo:  1187 | p95:  1144.2 | capacidad: 1280
healthcare    | dias: 1707 | promedio:   466.4 | maximo:   552 | p95:   508.0 | capacidad: 570
```

---

## 9. En una frase (para la exposición)

> *"Como el dataset no informa cuántas camas tiene el hospital, la estimamos a partir de su historia: elegimos una capacidad tal que la alerta del 90 % se active solo en el 5 % de los días más ocupados."*
