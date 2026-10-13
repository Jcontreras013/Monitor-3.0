"""
Carga inicial: pasa los datos del sistema anterior (Google Sheets y archivos
de catálogo) a Postgres. Se puede repetir sin duplicar nada.

1. En Google Sheets, abrir la base de datos y descargar cada pestaña como CSV
   (Archivo -> Descargar -> CSV): Sheet1, FTTX, Expedientes, Calidad,
   Operaciones, Instalaciones, Auditoria_Fibra, VIP.
2. Correr, ANTES de arrancar el robot nuevo (cada opción es independiente):

    python -m scripts.importar_historial Sheet1.csv --fttx FTTX.csv \\
        --expedientes Expedientes.csv \\
        --personal-tecnico personal_tecnico.txt --personal-sac personal_sac.txt \\
        --calidad Calidad.csv --auditoria-operaciones Operaciones.csv \\
        --auditoria-instalaciones Instalaciones.csv --auditoria-fibra Auditoria_Fibra.csv \\
        --vip VIP.csv
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app import repositorio
from app.config import get_settings
from app.db import crear_engine, crear_sesiones
from app.dominio import calidad as dom_cal
from app.dominio import expedientes as dom_exp
from app.dominio.fechas import ZONA_HN, parse_fecha
from app.dominio.normalizacion import normalizar_orden, texto_limpio
from app.dominio.personal import leer_personal_administrativo, leer_personal_tecnico
from app.dominio.vip import leer_archivo_vip
from app.models import AuditoriaCampo, ClienteVip, DispositivoFttx, Expediente, GestionCalidad, Personal

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


VACIOS = ("", "N/A", "N/D", "NAN", "NONE", "NULL", "NAT", "NINGUNA", "SIN DETALLE", "PENDIENTE")


def _texto(fila: dict, *claves: str) -> str:
    """Primer valor no vacío entre las columnas dadas ("N/A", "Ninguna"... cuentan como vacío)."""
    for clave in claves:
        valor = texto_limpio(fila.get(clave)) or ""
        if valor.upper() not in VACIOS:
            return valor
    return ""


def _nota(valor) -> int | None:
    try:
        n = int(float(str(valor).strip()))
    except ValueError:
        return None
    return n if 1 <= n <= 5 else None


def _ajustar(modelo, datos: dict) -> dict:
    """Recorta los textos al largo de su columna: las hojas no tenían límites."""
    for campo, valor in datos.items():
        largo = getattr(modelo.__table__.c[campo].type, "length", None)
        if largo and isinstance(valor, str):
            datos[campo] = valor[:largo]
    return datos


def _fecha_hn(valor):
    fecha = parse_fecha(valor, permitir_asumir_hoy=False)
    return fecha.replace(tzinfo=ZONA_HN) if fecha else None


async def importar_calidad(sesiones, ruta: str) -> None:
    """Pestaña Calidad: llamadas (con y sin encuesta) y envíos por WhatsApp."""
    filas = _leer_csv(ruta)
    async with sesiones() as sesion:
        existentes = {(g.fecha_gestion, g.num_orden) for g in (await sesion.scalars(select(GestionCalidad))).all()}
        nuevas, descartadas = [], 0
        for fila in filas:
            fecha = _fecha_hn(fila.get("FECHA_GESTION"))
            num = _texto(fila, "TICKET").upper().removeprefix("ORD-").strip()
            if fecha is None or not num:
                descartadas += 1
                continue
            if (fecha, num) in existentes:
                continue
            existentes.add((fecha, num))
            metodo = _texto(fila, "METODO_AUDITORIA", "TIPO_AUDITORIA")
            tipo_nota = _texto(fila, "TIPO_NOTA") or "Ninguna"
            nuevas.append(GestionCalidad(**_ajustar(GestionCalidad, {
                "fecha_gestion": fecha, "num_orden": num, "cliente": _texto(fila, "CLIENTE_ID"),
                "nombre_cliente": _texto(fila, "NOMBRE_CLIENTE"), "tecnico": _texto(fila, "TECNICO"),
                "actividad": _texto(fila, "ACTIVIDAD"), "fecha_visita": _texto(fila, "FECHA_VISITA"),
                "contesto": metodo == dom_cal.METODO_COMPLETADA,
                **{clave: _nota(fila.get(columna)) for clave, columna in (
                    ("p1", "P1_PUNTUALIDAD"), ("p2", "P2_PRESENTACION_TRATO"), ("p3", "P3_CLARIDAD_EXPLICACION"),
                    ("p4", "P4_EXPLICACION_TV_CCVEO"), ("p5", "P5_CALIDAD_SERVICIO"), ("p6", "P6_LIMPIEZA_TRABAJO"),
                    ("p7", "P7_SATISFACCION_GENERAL"))},
                "mejoras": _texto(fila, "MEJORAS_OPCIONAL", "COMENTARIOS"),
                "aceptacion_digital": _texto(fila, "ACEPTACION_DIGITAL"),
                "hora_cierre_servicio": _texto(fila, "HORA_CIERRE_SERVICIO"),
                "aprobacion_interna": _texto(fila, "APROBACION_INTERNA"), "metodo_auditoria": metodo,
                "resultado_gestion": _texto(fila, "RESULTADO_GESTION"),
                "ticket_seguimiento": _texto(fila, "TICKET_SEGUIMIENTO"),
                "responsable_seguimiento": _texto(fila, "RESPONSABLE_SEGUIMIENTO"),
                "fecha_limite_seguimiento": (f := parse_fecha(fila.get("FECHA_LIMITE_SEGUIMIENTO"),
                                                              permitir_asumir_hoy=False)) and f.date(),
                "tipo_nota": tipo_nota if tipo_nota in dom_cal.TIPOS_NOTA else "Ninguna",
                "detalle_nota": _texto(fila, "DETALLE_NOTA"), "registrado_por": "importado",
            })))
        sesion.add_all(nuevas)
        await sesion.commit()
    print(f"Calidad: {len(filas)} filas leídas, {len(nuevas)} gestiones nuevas, {descartadas} sin fecha u orden.")


async def importar_auditorias(sesiones, ruta: str, tipo: str) -> None:
    """Pestañas Operaciones, Instalaciones y Auditoria_Fibra."""
    filas = _leer_csv(ruta)
    async with sesiones() as sesion:
        existentes = {
            (a.fecha_auditoria, a.num_orden)
            for a in (await sesion.scalars(select(AuditoriaCampo).where(AuditoriaCampo.tipo == tipo))).all()
        }
        nuevas, descartadas = [], 0
        for fila in filas:
            fecha = _fecha_hn(fila.get("FECHA_AUDITORIA"))
            num = _texto(fila, "ORDEN_NUM").upper().removeprefix("ORD-").strip()
            if fecha is None or not num:
                descartadas += 1
                continue
            if (fecha, num) in existentes:
                continue
            existentes.add((fecha, num))
            nuevas.append(AuditoriaCampo(**_ajustar(AuditoriaCampo, {
                "tipo": tipo, "fecha_auditoria": fecha, "num_orden": num, "cliente": _texto(fila, "CODIGO_CLIENTE"),
                "nombre_cliente": _texto(fila, "NOMBRE_CLIENTE"), "tecnico": _texto(fila, "TECNICO"),
                "actividad": _texto(fila, "CODIGO_SERVICIO"), "vineta": _texto(fila, "VINETA"),
                "mufa": _texto(fila, "MUFA"), "metraje": _texto(fila, "METRAJE", "METROS_FO"),
                "estetica": _texto(fila, "ESTETICA"), "ruta_acometida": _texto(fila, "RUTA_ACOMETIDA"),
                "tiempo_invertido": _texto(fila, "TIEMPO_INVERTIDO"), "tipo_fo": _texto(fila, "TIPO_FO"),
                "comentario": _texto(fila, "COMENTARIO_AUDITOR", "COMENTARIOS"),
                "evaluacion": _texto(fila, "EVALUACION_TRABAJO"), "supervisor": _texto(fila, "SUPERVISOR"),
                "convertido_a_falta": _texto(fila, "CONVERTIDO_A_FALTA").upper() == "SI",
                "urls_externas": [u.strip() for u in str(fila.get("IMAGENES_URLS") or "").split(",")
                                  if u.strip().startswith("http")],
            })))
        sesion.add_all(nuevas)
        await sesion.commit()
    print(f"Auditorías {tipo}: {len(filas)} filas leídas, {len(nuevas)} nuevas, {descartadas} sin fecha u orden.")


async def importar_vip(sesiones, ruta: str) -> None:
    """Pestaña VIP: reemplaza la lista de clientes VIP."""
    clientes = leer_archivo_vip(Path(ruta).read_bytes(), ruta)
    async with sesiones() as sesion:
        await sesion.execute(delete(ClienteVip))
        sesion.add_all(ClienteVip(cliente=c.cliente, nombre=c.nombre, clase=c.clase[:60]) for c in clientes)
        await sesion.commit()
    print(f"Clientes VIP: {len(clientes)} cargados.")


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
        if args.calidad:
            await importar_calidad(sesiones, args.calidad)
        for tipo in dom_cal.TIPOS_AUDITORIA:
            if ruta := getattr(args, f"auditoria_{tipo}"):
                await importar_auditorias(sesiones, ruta, tipo)
        if args.vip:
            await importar_vip(sesiones, args.vip)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa los datos del sistema anterior a Postgres")
    parser.add_argument("ordenes", nargs="?", help="CSV de la pestaña Sheet1 (o historial_maestro.csv)")
    parser.add_argument("--fttx", help="CSV de la pestaña FTTX (técnico -> vehículo)")
    parser.add_argument("--expedientes", help="CSV de la pestaña Expedientes")
    parser.add_argument("--personal-tecnico", help="personal_tecnico.txt")
    parser.add_argument("--personal-sac", help="personal_sac.txt")
    parser.add_argument("--calidad", help="CSV de la pestaña Calidad (llamadas)")
    parser.add_argument("--auditoria-operaciones", help="CSV de la pestaña Operaciones")
    parser.add_argument("--auditoria-instalaciones", help="CSV de la pestaña Instalaciones")
    parser.add_argument("--auditoria-fibra", help="CSV de la pestaña Auditoria_Fibra")
    parser.add_argument("--vip", help="CSV de la pestaña VIP (o el Excel de clientes VIP)")
    args = parser.parse_args()
    archivos = (args.ordenes, args.fttx, args.expedientes, args.personal_tecnico, args.personal_sac, args.calidad,
                args.auditoria_operaciones, args.auditoria_instalaciones, args.auditoria_fibra, args.vip)
    if not any(archivos):
        parser.error("indica al menos un archivo para importar")
    asyncio.run(importar(args))


if __name__ == "__main__":
    main()
