
"""Asigna el rol administrador a una cuenta existente."""

from services import acceso


def main():
    usuario = input("Usuario que sera administrador: ").strip()

    if not usuario:
        print("Debes ingresar un usuario.")
        return

    confirmacion = input(
        f"¿Confirmas asignar el rol administrador a '{usuario}'? (si/no): "
    ).strip().lower()

    if confirmacion != "si":
        print("Operacion cancelada.")
        return

    try:
        acceso.asignar_administrador_local(usuario)
    except ValueError as error:
        print(f"Error: {error}")
        return

    print(f"El usuario '{usuario}' ahora es administrador.")


if __name__ == "__main__":
    main()
