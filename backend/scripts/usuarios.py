"""
Alta de usuarios.

    # Crear (o cambiar la contraseña / rol de) un usuario; pide la contraseña:
    python -m scripts.usuarios crear javier --rol admin --nombre "Javier Zúñiga"

    # Pasar de una vez todos los usuarios de [credenciales] del secrets.toml
    # del sistema anterior (con su contraseña y rol actuales):
    python -m scripts.usuarios importar ruta/a/.streamlit/secrets.toml

Las contraseñas cambiadas desde la app anterior (hoja Usuarios_Claves) no se
pueden leer; esos usuarios entran con la de secrets.toml o se les crea una
nueva con `crear`.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
import tomllib
from datetime import UTC, datetime

from sqlalchemy import select

from app.config import get_settings
from app.db import crear_engine, crear_sesiones
from app.models import Usuario
from app.security import LARGO_MINIMO_CLAVE, cifrar_clave


async def _guardar(usuarios: list[tuple[str, str, str, str]]) -> None:
    """usuarios: (usuario, clave, rol, nombre). Crea o actualiza cada uno."""
    engine = crear_engine(get_settings().database_url)
    try:
        async with crear_sesiones(engine)() as sesion:
            for nombre_usuario, clave, rol, nombre in usuarios:
                usuario = await sesion.scalar(select(Usuario).where(Usuario.usuario == nombre_usuario))
                if usuario is None:
                    usuario = Usuario(usuario=nombre_usuario, nombre=nombre, rol=rol, clave_hash=cifrar_clave(clave))
                    sesion.add(usuario)
                    accion = "creado"
                else:
                    usuario.rol = rol
                    usuario.nombre = nombre or usuario.nombre
                    usuario.clave_hash = cifrar_clave(clave)
                    usuario.clave_actualizada_en = datetime.now(UTC)
                    accion = "actualizado"
                print(f"  {nombre_usuario:<20} rol={rol:<12} {accion}")
            await sesion.commit()
    finally:
        await engine.dispose()


def _crear(args) -> None:
    clave = getpass.getpass(f"Contraseña para {args.usuario}: ")
    if len(clave) < LARGO_MINIMO_CLAVE:
        sys.exit(f"La contraseña debe tener al menos {LARGO_MINIMO_CLAVE} caracteres.")
    if clave != getpass.getpass("Repítela: "):
        sys.exit("Las contraseñas no coinciden.")
    asyncio.run(_guardar([(args.usuario.strip().lower(), clave, args.rol, args.nombre)]))


def _importar(args) -> None:
    with open(args.secrets, "rb") as f:
        credenciales = tomllib.load(f).get("credenciales", {})
    usuarios = [
        (str(u).strip().lower(), str(datos["clave"]), str(datos.get("rol", "monitoreo")), str(u))
        for u, datos in credenciales.items()
        if isinstance(datos, dict) and datos.get("clave")
    ]
    if not usuarios:
        sys.exit("No se encontró ningún usuario en [credenciales].")
    asyncio.run(_guardar(usuarios))
    print(f"{len(usuarios)} usuario(s) importados.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Alta de usuarios del Monitor")
    sub = parser.add_subparsers(dest="comando", required=True)
    p_crear = sub.add_parser("crear", help="crea o actualiza un usuario")
    p_crear.add_argument("usuario")
    p_crear.add_argument("--rol", required=True, help="admin | jefe | monitoreo | llamados | ...")
    p_crear.add_argument("--nombre", default="")
    p_crear.set_defaults(func=_crear)
    p_imp = sub.add_parser("importar", help="importa [credenciales] de un secrets.toml")
    p_imp.add_argument("secrets")
    p_imp.set_defaults(func=_importar)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
