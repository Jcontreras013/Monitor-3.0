"""
Carga inicial: pasa los datos del sistema anterior (Google Sheets y archivos
de catálogo) a Postgres. Se puede repetir sin duplicar nada.

1. En Google Sheets, abrir la base de datos y descargar cada pestaña como CSV
   (Archivo -> Descargar -> CSV): Sheet1, FTTX, Expedientes.
2. Correr, ANTES de arrancar el robot nuevo (cada opción es independiente):

    python -m scripts.importar_historial Sheet1.csv --fttx FTTX.csv \\
        --expedientes Expedientes.csv \\
        --personal-tecnico personal_tecnico.txt --personal-sac personal_sac.txt
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app import repositorio
from app.config import get_settings
from app.db import crear_engine, crear_sesiones
from app.dominio import expedientes as dom_exp
from app.dominio.fechas import ZONA_HN, parse_fecha
from app.dominio.normalizacion import normalizar_orden, texto_limpio
from app.dominio.personal import leer_personal_administrativo, leer_personal_tecnico
from app.models import DispositivoFttx, Expediente, Personal

csv.field_size_limit(sys.maxsize)


def _leer_csv(ruta: str) -> list[dict]:
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        return [{(k or "").strip().upper(): v for k, v in fila.items()} for fila in csv.DictReader(f)]


def _columna(columnas: list[str], claves: tuple[str, ...]) -> str | None:
    return next((c for c in columnas if any(k in c.upper() for k in claves)), None)


async def importar_fttx(sesiones, ruta: str) -> None:
    filas = _leer_csv(ruta)
    columnas = list(filas[0].keys()) if filas else []
    col_tec = _columna(columnas, ("TECNICO", "USER", "OPERADOR"))
    col_mx = _columna(columnas, ("MX", "VEHICULO", "PLACA"))
    if not col_tec or not col_mx:
        sys.exit(f"No se reconocen las columnas de técnico / vehículo en {ruta}: {columnas}")
    catalogo = {}
    for fila in filas:
        clave = repositorio.clave_tecnico(fila.get(col_tec))
        if clave and clave not in catalogo:
            catalogo[clave] = {"tecnico_clave": clave, "tecnico": fila[col_tec].strip(),
                               "mx": (fila.get(col_mx) or "").strip() or None}
    async with sesiones() as sesion:
        if catalogo:
            stmt = insert(DispositivoFttx).values(list(catalogo.values()))
            stmt = stmt.on_conflict_do_update(index_elements=[DispositivoFttx.tecnico_clave],
                                              set_={"tecnico": stmt.excluded.tecnico, "mx": stmt.excluded.mx})
            await sesion.execute(stmt)
        await sesion.commit()
    print(f"Catálogo FTTX: {len(catalogo)} técnicos.")


async def importar_ordenes(sesiones, ruta: str) -> None:
    filas = _leer_csv(ruta)
    ordenes = [o for fila in filas if (o := normalizar_orden(fila)) is not None]
    async with sesiones() as sesion:
        guardadas = await repositorio.guardar_ordenes(sesion, ordenes)
        await sesion.commit()
    print(f"Órdenes: {len(filas)} filas leídas, {guardadas} nuevas o actualizadas, "
          f"{len(filas) - len(ordenes)} descartadas (sin número, actividad interna u otra empresa).")


async def importar_personal(sesiones, ruta_tecnico: str | None, ruta_sac: str | None) -> None:
    personas = []
    if ruta_tecnico:
        personas += leer_personal_tecnico(Path(ruta_tecnico).read_text(encoding="utf-8"))
    if ruta_sac:
        personas += leer_personal_administrativo(Path(ruta_sac).read_text(encoding="utf-8"))
    if not personas:
        return
    async with sesiones() as sesion:
        stmt = insert(Personal).values(personas)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_personal_nombre_area",
            set_={"cargo": stmt.excluded.cargo, "clasificacion": stmt.excluded.clasificacion,
                  "estatus": stmt.excluded.estatus, "activo": True},
        )
        await sesion.execute(stmt)
        await sesion.commit()
    print(f"Personal: {len(personas)} colaboradores.")


async def importar_expedientes(sesiones, ruta: str) -> None:
    """Pestaña Expedientes: FECHA_REGISTRO, TECNICO, TIPO_FALTA, FECHA_INCIDENCIA, COMENTARIO, URL_FOTO, SUPERVISOR."""
    filas = _leer_csv(ruta)
    async with sesiones() as sesion:
        existentes = {
            (e.colaborador, e.area, e.tipo_falta, e.fecha_incidencia, e.comentario)
            for e in (await sesion.scalars(select(Expediente).where(Expediente.origen == "importado"))).all()
        }
        nuevos, descartados = [], 0
        for fila in filas:
            colaborador, area = dom_exp.separar_colaborador_area(fila.get("TECNICO", ""))
            fecha_inc = parse_fecha(fila.get("FECHA_INCIDENCIA"), permitir_asumir_hoy=False)
            if not colaborador or colaborador in ("NAN", "NONE", "NULL", "NAT", "UNDEFINED") or fecha_inc is None:
                descartados += 1
                continue
            tipo = (texto_limpio(fila.get("TIPO_FALTA")) or "SIN MOTIVO").upper()
            comentario = texto_limpio(fila.get("COMENTARIO")) or ""
            clave = (colaborador, area, tipo, fecha_inc.date(), comentario)
            if clave in existentes:
                continue
            existentes.add(clave)
            fecha_reg = parse_fecha(fila.get("FECHA_REGISTRO"), permitir_asumir_hoy=False) or fecha_inc
            nuevos.append(Expediente(
                fecha_registro=fecha_reg.replace(tzinfo=ZONA_HN), colaborador=colaborador, area=area,
                tipo_falta=tipo, fecha_incidencia=fecha_inc.date(), comentario=comentario,
                supervisor=texto_limpio(fila.get("SUPERVISOR")) or "", origen="importado",
                urls_externas=[u.strip() for u in str(fila.get("URL_FOTO") or "").split(",")
                               if u.strip().startswith("http")],
            ))
        sesion.add_all(nuevos)
        await sesion.commit()
    print(f"Expedientes: {len(filas)} filas leídas, {len(nuevos)} nuevos, {descartados} sin colaborador o fecha.")


async def importar(args) -> None:
    engine = crear_engine(get_settings().database_url)
    sesiones = crear_sesiones(engine)
    try:
        if args.personal_tecnico or args.personal_sac:
            await importar_personal(sesiones, args.personal_tecnico, args.personal_sac)
        if args.fttx:
            await importar_fttx(sesiones, args.fttx)
        if args.ordenes:
            await importar_ordenes(sesiones, args.ordenes)
        if args.expedientes:
            await importar_expedientes(sesiones, args.expedientes)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa los datos del sistema anterior a Postgres")
    parser.add_argument("ordenes", nargs="?", help="CSV de la pestaña Sheet1 (o historial_maestro.csv)")
    parser.add_argument("--fttx", help="CSV de la pestaña FTTX (técnico -> vehículo)")
    parser.add_argument("--expedientes", help="CSV de la pestaña Expedientes")
    parser.add_argument("--personal-tecnico", help="personal_tecnico.txt")
    parser.add_argument("--personal-sac", help="personal_sac.txt")
    args = parser.parse_args()
    if not any((args.ordenes, args.fttx, args.expedientes, args.personal_tecnico, args.personal_sac)):
        parser.error("indica al menos un archivo para importar")
    asyncio.run(importar(args))


if __name__ == "__main__":
    main()
