"""Ejecutar desde la raiz: python backend/app/crear_usuario.py
La clave se solicita con getpass: no aparece en pantalla ni en el historial.
"""
import argparse
from getpass import getpass
from services.acceso import crear_usuario


def main():
    parser = argparse.ArgumentParser(description="Configurar acceso local al agente de camas")
    parser.add_argument("--usuario", help="Nombre de usuario; si se omite, se pregunta")
    parser.add_argument("--cambiar-clave", action="store_true", help="Renovar la clave de un usuario existente e invalidar sus sesiones")
    args = parser.parse_args()
    usuario = args.usuario or input("Usuario que queres crear: ")
    clave = getpass("Contrasena (12 a 128 caracteres; no se muestra al escribir): ")
    if clave != getpass("Repeti la contrasena: "):
        raise ValueError("Las contrasenas no coinciden. No se realizaron cambios.")
    crear_usuario(usuario, clave, reemplazar=args.cambiar_clave)
    print("Acceso configurado. Inicia el servidor y entra con tu usuario y contrasena.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, EOFError, KeyboardInterrupt) as error:
        print("No se configuro el acceso:", str(error) or "operacion cancelada")
        raise SystemExit(1)
