# Modo contingencia: demanda excepcional (pandemia)

**Responsable:** Darío · **Rama:** `dario`

## 1. Por qué existe

El profe preguntó qué pasa si el hospital se satura por un evento excepcional, como el COVID, y pidió que **el sistema lo contemple**.

El agente aprende de la historia de HDHI (2017-2019), que **no tiene pandemias**. Ante una crisis subestimaría la demanda, como cualquier modelo entrenado con el pasado: no puede predecir algo que nunca vio.

Por eso la crisis **no se predice: se simula**. El usuario carga tres supuestos y el agente calcula qué pasaría con las camas.

## 2. Dónde está y cómo se usa

En la solapa **01 Proyección**, al final: **"Modo contingencia: simular una crisis"**. Los campos arrancan vacíos: se completan a mano o con un botón de ejemplo.

| Campo | Qué significa | Rango |
|---|---|---|
| **Aumento de ingresos (%)** | Cuántos pacientes más llegan por día | 0 a 300 % |
| **Días extra de estancia** | Pacientes más graves, que tardan más en irse | 0 a 30 días |
| **Camas de contingencia** | Camas de emergencia que se habilitan | 0 a 5.000 |

Usa la **misma fuente, fecha, capacidad y horizonte** del menú lateral.

Botones de ejemplo:
- **Ola moderada:** +30 % de ingresos, +2 días.
- **Pandemia:** +50 % de ingresos, +4 días.
- **Pandemia + 60 camas de emergencia.**

## 3. Cómo calcula

Parte de la **proyección normal del agente** y rehace el balance de cada día:

```
camas de hoy = camas de ayer + ingresos − altas
```

| Parte | Cálculo |
|---|---|
| **Ingresos** | ingresos previstos × (1 + aumento ÷ 100) |
| **Altas** | camas de ayer × tasa de alta del día × ALOS ÷ (ALOS + días extra) |
| **Capacidad** | capacidad + camas de contingencia |

La **tasa de alta del día** es la fracción de internados que se va ese día en la proyección normal (altas ÷ camas de ayer). Si los pacientes se quedan más días, sale una fracción menor.

**Con los tres valores en 0, el resultado es idéntico a la proyección normal** (verificado: diferencia 0,0).

### Ejemplo: primer día de la "Pandemia" (HDHI, 01/03/2019, 190 camas)

| Paso | Normal | Contingencia (+50 %, +4 días) |
|---|---|---|
| Camas de ayer | 117 | 117 |
| Ingresos | 21,1 | 21,1 × 1,5 = **31,7** |
| Tasa de alta | 22,8 ÷ 117 = 0,195 | 0,195 |
| Ajuste por estancia | — | 6,31 ÷ 10,31 = **0,61** |
| Altas | 22,8 | 117 × 0,195 × 0,61 = **14,0** |
| **Camas del día** | **115,3** | 117 + 31,7 − 14,0 = **134,7** |

Entran más pacientes y salen menos: la ocupación crece día tras día.

### Pacientes sin cama

Lo que supera la capacidad **no se descarta**: se informa como **demanda sin cama**, es decir, pacientes que el hospital no podría internar. Así se sabe cuántas camas faltarían.

## 4. Qué muestra

- **Mensaje con el estado**, en tres niveles:
  - verde: el hospital absorbe la crisis;
  - amarillo: alerta, se supera el 90 %;
  - rojo: colapso, se supera el 100 %.
- **5 indicadores:** pico normal → pico en la contingencia, día en que se supera el 90 %, día en que se llenan todas las camas, pacientes sin cama en el peor día y camas extra para no pasar el 90 %.
- **Gráfico:** proyección normal (verde), contingencia (rojo), camas disponibles (gris) y umbral del 90 % (punteado).
- **Tabla diaria** con ingresos, altas, camas necesarias, ocupación, pacientes sin cama y estado.

## 5. Resultados (HDHI, 01/03/2019, 190 camas)

| Escenario | Pico | Resultado |
|---|---|---|
| Normal | 62 % | Sin alerta |
| Ola moderada (+30 %, +2 días) | 92 % | Alerta desde el vie 8/3; faltan 5 camas |
| Pandemia (+50 %, +4 días) | **117 %** | Pasa el 90 % el mar 5/3, **colapsa el mié 6/3**, **31 pacientes sin cama**; faltan 56 camas |
| Pandemia + 60 camas | 89 % de 250 | El hospital absorbe la crisis |

## 6. En la API

`POST /proyeccion-camas` acepta un campo **opcional** `contingencia`:

```json
{
  "dataset": "hdhi",
  "fecha": "2019-03-01",
  "contingencia": {"aumento_ingresos_pct": 50, "estancia_extra_dias": 4, "camas_contingencia": 0}
}
```

- La respuesta trae la proyección normal **y además** un bloque `contingencia`, con el resumen y los días.
- Sin ese campo, el endpoint responde igual que antes.
- **Validaciones (422):** aumento fuera de 0-300, días fuera de 0-30, camas con decimales, campos desconocidos, o contingencia combinada con la simulación por sectores.
- En `/docs` hay un ejemplo: **"Modo contingencia (pandemia)"**.

## 7. Archivos

| Archivo | Cambio |
|---|---|
| `backend/app/services/contingencia.py` | **Nuevo:** el cálculo |
| `frontend/js/contingencia.js` | **Nuevo:** la pantalla |
| `backend/app/routers/inventario.py` | Campo `contingencia` en el modelo, respuesta y ejemplo |
| `backend/app/main.py` | Ruta para servir `contingencia.js` |
| `frontend/index.html` | Sección nueva al final de Proyección (solo se agregaron líneas) |

**No se modificó** el agente, los modelos de predicción, los datos ni las demás solapas.

## 8. Limitaciones

- Son **supuestos del usuario**, no un pronóstico: el sistema no sabe cuánto aumentaría la demanda en una pandemia real.
- El aumento se aplica parejo todos los días; una ola real crece de a poco.
- Las camas de contingencia se suponen disponibles desde el primer día.
- No distingue UTI de general. Para eso está la solapa **03 UTI y general**.

## 9. Para el oral

> "El agente aprende de 2017-2019, sin pandemias, así que no puede anticipar una crisis. Lo que hace es **simularla con supuestos**: si los ingresos suben 50 % y cada paciente se queda 4 días más, el hospital pasa el 90 % el martes, colapsa el miércoles y quedan 31 pacientes sin cama. Para no pasar el 90 % harían falta 56 camas más. Con 60 camas de emergencia, el hospital lo absorbe."
