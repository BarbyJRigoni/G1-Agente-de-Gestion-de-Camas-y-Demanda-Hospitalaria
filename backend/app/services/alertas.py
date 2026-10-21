"""
Logica de alertas de ocupacion de camas.

Compara la ocupacion proyectada con la capacidad del hospital y emite la
"Alerta de Saturacion" cuando se supera el umbral definido en config.py (90 %).
Solo trabaja con numeros: no lee archivos ni depende de otros modulos del equipo.
"""
from core import config


# Calcula la Tasa de Ocupacion (KPI de la consigna), en porcentaje.
def calcular_tasa_ocupacion(camas_ocupadas, capacidad):
    if capacidad <= 0:
        raise ValueError("La capacidad debe ser mayor a cero.")
    return round(camas_ocupadas / capacidad * 100, 1)


# Evalua un dia: tasa de ocupacion, camas libres y si corresponde la alerta.
def evaluar_dia(fecha, camas_ocupadas, capacidad):
    tasa = calcular_tasa_ocupacion(camas_ocupadas, capacidad)

    # Se compara con el valor exacto (sin redondear) para no perder casos
    # como 90,04 %, que redondeado mostraria 90,0 %.
    supera_umbral = camas_ocupadas / capacidad > config.UMBRAL_SATURACION

    return {
        "fecha": str(fecha),
        "camas_ocupadas": int(round(camas_ocupadas)),
        "capacidad": capacidad,
        "camas_libres": max(capacidad - int(round(camas_ocupadas)), 0),
        "tasa_ocupacion_pct": tasa,
        "alerta_saturacion": supera_umbral,
    }


# Evalua la proyeccion completa (una lista de dias) y arma el resumen.
# Cada dia de la lista debe tener las claves "fecha" y "camas_ocupadas".
def evaluar_proyeccion(proyeccion, capacidad):
    if not proyeccion:
        raise ValueError("La proyeccion no tiene dias para evaluar.")

    dias = [
        evaluar_dia(dia["fecha"], dia["camas_ocupadas"], capacidad)
        for dia in proyeccion
    ]

    indice_pico = max(range(len(proyeccion)), key=lambda i: proyeccion[i]["camas_ocupadas"])
    dia_pico = dias[indice_pico]
    dias_saturados = [d["fecha"] for d in dias if d["alerta_saturacion"]]
    hay_alerta = len(dias_saturados) > 0
    umbral_pct = config.UMBRAL_SATURACION * 100

    if hay_alerta:
        mensaje = (
            f"ALERTA DE SATURACION: la ocupacion proyectada supera el {umbral_pct:.0f} % "
            f"en {len(dias_saturados)} de {len(dias)} dias. "
            f"Pico: {dia_pico['tasa_ocupacion_pct']} % el {dia_pico['fecha']}."
        )
    else:
        mensaje = (
            f"Sin alerta: la ocupacion proyectada no supera el {umbral_pct:.0f} %. "
            f"Maximo: {dia_pico['tasa_ocupacion_pct']} % el {dia_pico['fecha']}."
        )

    return {
        "alerta_saturacion": hay_alerta,
        "mensaje": mensaje,
        "umbral_pct": umbral_pct,
        "tasa_ocupacion_maxima_pct": dia_pico["tasa_ocupacion_pct"],
        "dia_pico": dia_pico["fecha"],
        "dias_en_saturacion": dias_saturados,
        "dias": dias,
    }


# Prueba rapida con los tres casos de la demo: normal, limite y critico.
if __name__ == "__main__":
    capacidad = 220
    casos = {
        "Normal": [130, 135, 128, 140, 138, 132, 129],
        "Limite": [190, 195, 197, 198, 196, 194, 190],
        "Critico": [185, 192, 199, 205, 210, 208, 200],
    }

    for nombre, ocupacion in casos.items():
        proyeccion = [
            {"fecha": f"2019-03-0{i + 2}", "camas_ocupadas": camas}
            for i, camas in enumerate(ocupacion)
        ]
        resultado = evaluar_proyeccion(proyeccion, capacidad)
        print(f"\n=== Caso {nombre} ===")
        print(resultado["mensaje"])