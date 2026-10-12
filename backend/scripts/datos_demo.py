"""
Datos de demostración para probar la app sin acceso a Cepheus.

    ENTORNO=desarrollo python -m scripts.datos_demo

Crea el usuario `demo` (contraseña `demo-monitor`, rol admin), unas 400
órdenes, un catálogo de personal y faltas de ejemplo, todo inventado.
Se niega a correr fuera de ENTORNO=desarrollo.
"""

from __future__ import annotations

import asyncio
import random
import sys
from datetime import timedelta

from sqlalchemy import select

from app import repositorio
from app.config import get_settings
from app.db import crear_engine, crear_sesiones
from app.dominio.expedientes import AREA_OPERACIONES
from app.dominio.fechas import ahora_hn
from app.dominio.normalizacion import normalizar_orden
from app.models import Expediente, Personal, Usuario
from app.security import cifrar_clave

TECNICOS = ["Carlos Mejía", "Ana Rodríguez", "Luis Hernández", "María López", "José Martínez",
            "Pedro Sánchez", "Karla Flores", "Marvin Reyes"]
COLONIAS = ["Centro", "Barrio Abajo", "Col. Kennedy", "Res. Las Uvas", "Col. Palmira", "Barrio La Granja"]
SOPORTE = ["cliente sin internet", "ONU OFFLINE desde ayer", "niveles altos -29 dB", "navegacion lenta",
           "sin señal de TV", "LOS en rojo", "revisar router"]
INSTALACION = ["instalacion nueva", "ADICION de tv", "cambio de plan", "recuperado"]
ACTIVIDADES = [("SOPFIBRA", SOPORTE, 45), ("INSFIBRA", INSTALACION, 25), ("SOPFIBRACORP", SOPORTE, 8),
               ("PEXTERNO", ["revision de tramo"], 6), ("SPLITTEROPT", ["caja splitter"], 4),
               ("INSFIBRACORP", INSTALACION, 5), ("TRASLADOEXTFIBRA", ["traslado"], 4), ("CEQUI", ["cambio equipo"], 3)]


ADMINISTRATIVOS = {"SAC": ["SAYRA ESCOBAR", "AMY JEREZANO", "DENZEL BODDEN"], "BODEGA": ["CARLOS GARCIA"]}
FALTAS = [
    ("LLEGADA TARDE", "Llegó a las 8:25 am"), ("LLEGADA TARDE", "Llegó 8:40, tráfico"),
    ("EXCESO DE VELOCIDAD", "GPS marcó 92 km/h en zona urbana"), ("MALA DOCUMENTACIÓN", "Orden sin fotos de cierre"),
    ("ABANDONO DE RUTA", "Se retiró de la zona asignada sin avisar"), ("INCIDENCIA MÉDICA", "Cita en el IHSS"),
]


def generar_expedientes() -> list[Expediente]:
    random.seed(11)
    hoy = ahora_hn().date()
    registros = []
    for _ in range(26):
        tipo, comentario = random.choice(FALTAS)
        registros.append(Expediente(
            colaborador=random.choice(TECNICOS).upper(), area=AREA_OPERACIONES, tipo_falta=tipo, comentario=comentario,
            fecha_incidencia=hoy - timedelta(days=random.randint(0, 45)), supervisor="Usuario Demo", origen="app",
            urls_externas=[]))
    for area, nombres in ADMINISTRATIVOS.items():
        for nombre in nombres:
            registros.append(Expediente(
                colaborador=nombre, area=area, tipo_falta=random.choice(["LLEGADA TARDÍA", "AMONESTACIÓN ESCRITA"]),
                comentario="Registro de demostración", fecha_incidencia=hoy - timedelta(days=random.randint(0, 20)),
                supervisor="Usuario Demo", origen="app", urls_externas=[]))
    return registros


def generar(n: int = 400) -> list[dict]:
    random.seed(7)
    ahora = ahora_hn()
    pesos = [a[2] for a in ACTIVIDADES]
    crudas = []
    for i in range(n):
        actividad, comentarios, _ = random.choices(ACTIVIDADES, weights=pesos)[0]
        apertura = ahora - timedelta(days=random.choice([0, 0, 0, 1, 1, 2, 3, 5, 8]), hours=random.randint(0, 10))
        estado = random.choices(["Asignada", "Iniciada", "Pendiente", "Cerrada"], weights=[30, 12, 8, 50])[0]
        tecnico = "" if estado == "Pendiente" and random.random() < 0.6 else random.choice(TECNICOS)
        orden = {
            "IDORDEN": str(95_700_000 + i), "NOMACTIVIDAD": actividad, "ESTADO": estado, "TECNICO": tecnico,
            "CLIENTE": str(200_000 + random.randint(0, 99_999)), "NOMBRECLIENTE": f"Cliente {i}",
            "COLONIA": random.choice(COLONIAS), "COMENTARIO": random.choice(comentarios),
            "FECHAAPERTURA": apertura.strftime("%d/%m/%Y %H:%M"),
        }
        if estado in ("Iniciada", "Cerrada"):
            inicio = min(ahora - timedelta(minutes=20), apertura + timedelta(hours=random.randint(1, 5)))
            orden["HORAINICIOORDEN"] = inicio.strftime("%d/%m/%Y %H:%M")
            if estado == "Iniciada":
                orden["GPS"] = "https://maps.google.com/?q=15.77,-86.79"
        if estado == "Cerrada":
            cierre = min(ahora, inicio + timedelta(minutes=random.randint(40, 200)))
            orden["HORACIERREORDEN"] = cierre.strftime("%d/%m/%Y %H:%M")
            orden["RAZON CIERRE"] = random.choice(["Solucionado", "Cambio de conector", "Instalado"])
        crudas.append(orden)
    return crudas


async def principal() -> None:
    settings = get_settings()
    if settings.entorno != "desarrollo":
        sys.exit("Solo para desarrollo: define ENTORNO=desarrollo.")
    engine = crear_engine(settings.database_url)
    try:
        async with crear_sesiones(engine)() as sesion:
            if not await sesion.scalar(select(Usuario).where(Usuario.usuario == "demo")):
                sesion.add(Usuario(usuario="demo", nombre="Usuario Demo", rol="admin", acceso_repositorio=True,
                                   clave_hash=cifrar_clave("demo-monitor")))
            if not await sesion.scalar(select(Personal).limit(1)):
                sesion.add_all([Personal(nombre=t.upper(), area=AREA_OPERACIONES, cargo="TECNICO PRINCIPAL",
                                         clasificacion="TÉCNICO PRINCIPAL") for t in TECNICOS])
                sesion.add_all([Personal(nombre=n, area=a, clasificacion="ADMINISTRATIVO")
                                for a, nombres in ADMINISTRATIVOS.items() for n in nombres])
            if not await sesion.scalar(select(Expediente).limit(1)):
                sesion.add_all(generar_expedientes())
            ordenes = [o for c in generar() if (o := normalizar_orden(c))]
            cambiadas = await repositorio.guardar_ordenes(sesion, ordenes)
            await sesion.commit()
        print(f"Usuario demo / demo-monitor listo; {cambiadas} órdenes de prueba guardadas.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(principal())
