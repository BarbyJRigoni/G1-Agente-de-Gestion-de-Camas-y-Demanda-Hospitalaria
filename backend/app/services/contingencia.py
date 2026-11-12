"""
Modo contingencia: escenario de demanda excepcional (por ejemplo, una pandemia).

El agente aprende de la historia (HDHI 2017-2019), que no tiene eventos como el
COVID. Ante una crisis subestimaria la demanda, como cualquier modelo entrenado
con el pasado. Por eso la crisis no se predice: se SIMULA con tres supuestos que
ingresa el usuario.

  1. aumento_ingresos_pct : cuantos pacientes mas llegan (ej. +50 %).
  2. estancia_extra_dias  : cuantos dias mas se queda cada paciente (ej. +4).
  3. camas_contingencia   : camas extra que se habilitan (ej. +40).

Se parte de la proyeccion normal del agente y se rehace el balance diario:

  camas de hoy = camas de ayer + ingresos - altas

  - ingresos  = ingresos previstos x (1 + aumento / 100)
  - altas     = camas de ayer x tasa de alta del dia x ALOS / (ALOS + dias extra)
                (la tasa de alta del dia sale de la proyeccion normal; si los
                pacientes se quedan mas dias, sale una fraccion menor por dia)

Con los tres supuestos en 0 el resultado es identico a la proyeccion normal.

Los pacientes que no entran no se descartan: se informan como "demanda sin cama",
para saber cuantas camas faltarian.
"""
import math

from core import config


def aplicar_contingencia(resultado, aumento_ingresos_pct=0.0, estancia_extra_dias=0.0,
                         camas_contingencia=0):
    """Recalcula la proyeccion del agente con los supuestos de la contingencia."""
    capacidad_base = resultado["capacidad"]
    capacidad = capacidad_base + camas_contingencia
    umbral_camas = capacidad * config.UMBRAL_SATURACION
    alos = max(float(resultado["alos_historico"]), 1.0)

    factor_ingresos = 1 + aumento_ingresos_pct / 100
    factor_altas = alos / (alos + estancia_extra_dias)

    ocupadas_ayer_normal = float(resultado["camas_ocupadas_hoy"])
    necesarias_ayer = ocupadas_ayer_normal
    dias = []

    for dia in resultado["proyeccion"]:
        # Tasa de alta del dia en la proyeccion normal: que fraccion de los internados se va
        tasa_alta = dia["altas_previstas"] / ocupadas_ayer_normal if ocupadas_ayer_normal > 0 else 0.0
        tasa_alta = min(max(tasa_alta, 0.0), 1.0)

        ingresos = dia["ingresos_previstos"] * factor_ingresos
        altas = necesarias_ayer * tasa_alta * factor_altas
        necesarias = max(necesarias_ayer + ingresos - altas, 0.0)

        tasa = necesarias / capacidad * 100
        dias.append({
            "fecha": dia["fecha"],
            "ingresos": round(ingresos, 1),
            "altas": round(altas, 1),
            "camas_necesarias": round(necesarias, 1),
            "camas_ocupadas_normal": dia["camas_ocupadas"],
            "camas_libres": max(int(capacidad - math.ceil(necesarias - 1e-9)), 0),
            "demanda_sin_cama": round(max(necesarias - capacidad, 0.0), 1),
            "tasa_ocupacion_pct": round(tasa, 1),
            "alerta_saturacion": necesarias / capacidad > config.UMBRAL_SATURACION,
        })
        ocupadas_ayer_normal = float(dia["camas_ocupadas"])
        necesarias_ayer = necesarias

    pico = max(dias, key=lambda d: d["camas_necesarias"])
    supera_90 = next((d["fecha"] for d in dias if d["alerta_saturacion"]), None)
    supera_100 = next((d["fecha"] for d in dias if d["demanda_sin_cama"] > 0), None)
    # Camas que habria que agregar para que el pico no pase del 90 %
    camas_faltantes_90 = max(math.ceil(pico["camas_necesarias"] / config.UMBRAL_SATURACION - capacidad), 0)

    if supera_100:
        mensaje = (f"COLAPSO: el {supera_100} la demanda supera las {capacidad} camas. "
                   f"Pico: {pico['camas_necesarias']:.0f} camas necesarias ({pico['tasa_ocupacion_pct']:.0f} %), "
                   f"{pico['demanda_sin_cama']:.0f} pacientes sin cama. "
                   f"Para no pasar el 90 % harian falta {camas_faltantes_90} camas mas.")
    elif supera_90:
        mensaje = (f"ALERTA DE SATURACION: desde el {supera_90} se supera el 90 % "
                   f"({umbral_camas:.0f} camas). Pico: {pico['tasa_ocupacion_pct']:.0f} %. "
                   f"Para no pasar el 90 % harian falta {camas_faltantes_90} camas mas.")
    else:
        mensaje = (f"El hospital absorbe la contingencia: el pico es {pico['tasa_ocupacion_pct']:.0f} % "
                   f"de {capacidad} camas, por debajo del 90 %.")

    return {
        "parametros": {
            "aumento_ingresos_pct": aumento_ingresos_pct,
            "estancia_extra_dias": estancia_extra_dias,
            "camas_contingencia": camas_contingencia,
        },
        "capacidad_base": capacidad_base,
        "capacidad_total": capacidad,
        "umbral_camas": round(umbral_camas, 1),
        "alos_base": round(alos, 2),
        "alos_contingencia": round(alos + estancia_extra_dias, 2),
        "alerta_saturacion": supera_90 is not None,
        "colapso": supera_100 is not None,
        "dia_supera_90": supera_90,
        "dia_supera_100": supera_100,
        "tasa_ocupacion_maxima_pct": pico["tasa_ocupacion_pct"],
        "dia_pico": pico["fecha"],
        "demanda_sin_cama_maxima": pico["demanda_sin_cama"],
        "camas_faltantes_para_90": camas_faltantes_90,
        "mensaje": mensaje,
        "dias": dias,
        "aclaracion": ("Escenario simulado con supuestos del usuario: no es un pronostico. "
                       "Los ingresos y altas normales salen del agente; el aumento, la estancia "
                       "extra y las camas de contingencia son supuestos."),
    }
