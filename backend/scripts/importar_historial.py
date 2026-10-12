"""
Carga inicial: pasa el historial de Google Sheets a Postgres.

1. En Google Sheets, abrir la base de datos, pestaña Sheet1 ->
   Archivo -> Descargar -> CSV  (o bajar historial_maestro.csv de GCS).
2. Igual con la pestaña FTTX (catálogo técnico -> vehículo), opcional.
3. Correr, ANTES de arrancar el robot nuevo:

    python -m scripts.importar_historial Sheet1.csv --fttx FTTX.csv

Se puede repetir sin duplicar nada: es upsert por número de orden.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys

from sqlalchemy.dialects.postgresql import insert

from app import repositorio
from app.config import get_settings
from app.db import crear_engine, crear_sesiones
from app.dominio.normalizacion import normalizar_orden
from app.models import DispositivoFttx

csv.field_size_limit(sys.maxsize)


def _leer_csv(ruta: str) -> list[dict]:
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _columna(columnas: list[str], claves: tuple[str, ...]) -> str | None:
    return next((c for c in columnas if any(k in c.upper() for k in claves)), None)


async def importar(ruta_ordenes: str | None, ruta_fttx: str | None) -> None:
    engine = crear_engine(get_settings().database_url)
    sesiones = crear_sesiones(engine)
    try:
        if ruta_fttx:
            filas = _leer_csv(ruta_fttx)
            columnas = list(filas[0].keys()) if filas else []
            col_tec = _columna(columnas, ("TECNICO", "USER", "OPERADOR"))
            col_mx = _columna(columnas, ("MX", "VEHICULO", "PLACA"))
            if not col_tec or not col_mx:
                sys.exit(f"No se reconocen las columnas de técnico / vehículo en {ruta_fttx}: {columnas}")
            catalogo = {}
            for fila in filas:
                clave = repositorio.clave_tecnico(fila.get(col_tec))
                if clave and clave not in catalogo:
                    catalogo[clave] = {"tecnico_clave": clave, "tecnico": fila[col_tec].strip(),
                                       "mx": (fila.get(col_mx) or "").strip() or None}
            async with sesiones() as sesion:
                if catalogo:
                    stmt = insert(DispositivoFttx).values(list(catalogo.values()))
                    stmt = stmt.on_conflict_do_update(
                        index_elements=[DispositivoFttx.tecnico_clave],
                        set_={"tecnico": stmt.excluded.tecnico, "mx": stmt.excluded.mx},
                    )
                    await sesion.execute(stmt)
                await sesion.commit()
            print(f"Catálogo FTTX: {len(catalogo)} técnicos.")

        if ruta_ordenes:
            filas = _leer_csv(ruta_ordenes)
            ordenes = [o for fila in filas if (o := normalizar_orden(fila)) is not None]
            async with sesiones() as sesion:
                guardadas = await repositorio.guardar_ordenes(sesion, ordenes)
                await sesion.commit()
            print(f"Órdenes: {len(filas)} filas leídas, {guardadas} nuevas o actualizadas, "
                  f"{len(filas) - len(ordenes)} descartadas (sin número, actividad interna u otra empresa).")
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa el historial de Google Sheets a Postgres")
    parser.add_argument("ordenes", nargs="?", help="CSV de la pestaña Sheet1 (o historial_maestro.csv)")
    parser.add_argument("--fttx", help="CSV de la pestaña FTTX (técnico -> vehículo)")
    args = parser.parse_args()
    if not args.ordenes and not args.fttx:
        parser.error("indica el CSV de órdenes y/o --fttx")
    asyncio.run(importar(args.ordenes, args.fttx))


if __name__ == "__main__":
    main()
