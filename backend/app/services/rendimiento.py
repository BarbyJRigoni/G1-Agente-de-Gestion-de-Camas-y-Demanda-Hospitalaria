"""Cache acotada por proceso: un solo calculo simultaneo por combinacion.

No persiste datos ni errores. Cada reinicio descarta los resultados.
"""
from collections import OrderedDict, namedtuple
from concurrent.futures import Future
from copy import deepcopy
from functools import wraps
from inspect import signature
from threading import RLock


def cache_calculo(maxsize=64, copiar=False):
    def decorar(funcion):
        firma = signature(funcion)
        resultados, pendientes = OrderedDict(), {}
        candado = RLock()
        aciertos = fallos = 0

        @wraps(funcion)
        def consultar(*args, **kwargs):
            nonlocal aciertos, fallos
            parametros = firma.bind(*args, **kwargs)
            parametros.apply_defaults()
            clave = tuple(parametros.arguments.items())
            with candado:
                if clave in resultados:
                    aciertos += 1
                    valor = resultados.pop(clave)
                    resultados[clave] = valor
                    return deepcopy(valor) if copiar else valor
                futuro = pendientes.get(clave)
                creador = futuro is None
                if creador:
                    fallos += 1
                    futuro = pendientes[clave] = Future()
                else:
                    aciertos += 1
            if not creador:
                valor = futuro.result()
                return deepcopy(valor) if copiar else valor
            try:
                valor = funcion(*args, **kwargs)
            except BaseException as error:
                with candado:
                    pendientes.pop(clave, None)
                    futuro.set_exception(error)
                raise
            with candado:
                resultados[clave] = valor
                while len(resultados) > maxsize:
                    resultados.popitem(last=False)
                pendientes.pop(clave, None)
                futuro.set_result(valor)
            return deepcopy(valor) if copiar else valor

        def limpiar():
            nonlocal aciertos, fallos
            with candado:
                resultados.clear()
                aciertos = fallos = 0

        def informacion():
            with candado:
                return namedtuple('CacheInfo', 'hits misses maxsize currsize')(
                    aciertos, fallos, maxsize, len(resultados))
        consultar.cache_clear = limpiar
        consultar.cache_info = informacion
        return consultar
    return decorar
