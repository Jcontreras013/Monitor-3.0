from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.dominio import reportes as r

FECHA = date(2026, 10, 12)
DIA = datetime(2026, 10, 12, 8, 0)


@dataclass
class Ord:
    num: str
    actividad: str = "SOPFIBRA"
    estado: str = "CERRADA"
    tecnico: str | None = "Ana"
    fecha_ape: datetime | None = DIA - timedelta(days=2)
    hora_ini: datetime | None = DIA
    hora_liq: datetime | None = DIA + timedelta(hours=1)
    es_viva: bool = False
    es_offline: bool = False
    motivo: str = ""
    segmento: str = "RESIDENCIAL"
    grupo_tablero: str = "SOP"
    subtipo_tablero: str = ""
    cliente: str | None = "1"
    nombre: str | None = "Cliente"
    colonia: str | None = "Centro"
    sector: str | None = "TELA"
    comentario: str | None = ""


def test_cerradas_del_dia_usa_el_dia_operativo():
    ordenes = [
        Ord("1", hora_liq=datetime(2026, 10, 12, 23, 0)),
        Ord("2", hora_liq=datetime(2026, 10, 13, 5, 59)),   # madrugada: sigue siendo la jornada del 12
        Ord("3", hora_liq=datetime(2026, 10, 12, 5, 0)),    # jornada del 11
        Ord("4", hora_liq=datetime(2026, 10, 12, 9, 0), tecnico=None),
        Ord("5", hora_liq=datetime(2026, 10, 12, 9, 0), actividad="NOINSTALADO"),
    ]
    assert [o.num for o in r.cerradas_del_dia(ordenes, FECHA)] == ["1", "2"]


def test_eficiencia_con_bono_por_ruta_mixta():
    cerradas = [
        Ord("1", actividad="INSFIBRA"),                       # 25
        Ord("2", actividad="SOPFIBRA"),                       # 12.5
        Ord("3", actividad="INSFIBRA", comentario="ADICION de TV"),  # 12.5
        Ord("4", actividad="PEXTERNO", tecnico="Beto"),       # 100
    ]
    ana, beto = sorted(r.eficiencia_por_tecnico(cerradas), key=lambda t: t["tecnico"])
    assert (ana["ins"], ana["sop"], ana["puntos_base"]) == (2, 1, 50.0)
    assert (ana["bono_mixto"], ana["logro_final"]) == (10.0, 60.0)
    assert (beto["otr"], beto["logro_final"]) == (1, 100.0)  # PEXTERNO no dice "PLEX": cae en Otros, como antes
    assert r.eficiencia_por_tecnico(cerradas)[0]["tecnico"] == "Beto"


def test_tiempos_por_rango_y_por_ciudad():
    cerradas = [
        Ord("1", fecha_ape=DIA, sector="TELA"),
        Ord("2", fecha_ape=DIA - timedelta(days=2), sector="TELA"),
        Ord("3", fecha_ape=DIA - timedelta(days=9), sector="LA CEIBA", hora_ini=None),
        Ord("4", fecha_ape=DIA - timedelta(days=5), sector=None, actividad="INSFIBRA"),
    ]
    t = r.tiempos_por_rango(cerradas)
    assert t["ciudades"][0] == "TELA" and t["totales"][0] == 2
    menos_de_1 = t["filas"][0]["celdas"][0]
    assert (menos_de_1["cantidad"], menos_de_1["porcentaje"]) == (1, 50)
    assert t["filas"][3]["celdas"][t["ciudades"].index("LA CEIBA")]["cantidad"] == 1

    por_ciudad = {c["ciudad"]: c for c in r.cerradas_por_ciudad(cerradas)}
    assert por_ciudad["TELA"]["cantidad"] == 2 and por_ciudad["TELA"]["minutos"] == 60
    assert por_ciudad["LA CEIBA"]["minutos"] == 0  # sin hora de inicio no hay tiempo
    assert por_ciudad["SIN CIUDAD"]["filas"][0]["tipo"] == "INSTALACION"


def test_desglose_de_produccion():
    cerradas = [Ord("1"), Ord("2", actividad="INSFIBRA", comentario="adicion"), Ord("3", actividad="PEXTERNO"),
                Ord("4", actividad="CEQUI")]
    d = r.desglose_produccion(cerradas)
    assert d["sop"] == [{"nombre": "SOPFIBRA", "cantidad": 1}]
    assert d["instalaciones"] == [{"nombre": "Adición", "cantidad": 1}]
    assert d["plex"] == [{"nombre": "PEXTERNO", "cantidad": 1}]
    assert d["otros"] == [{"nombre": "CEQUI", "cantidad": 1}]


def test_primera_orden_y_promedio_de_arranque():
    ordenes = [
        Ord("1", hora_ini=datetime(2026, 10, 12, 8, 30)),
        Ord("2", hora_ini=datetime(2026, 10, 12, 7, 10)),
        Ord("3", tecnico="Beto", hora_ini=datetime(2026, 10, 12, 7, 50), estado="ASIGNADA", es_viva=True),
        Ord("4", tecnico="Beto", hora_ini=datetime(2026, 10, 12, 6, 0), estado="ANULADA"),
        Ord("5", hora_ini=datetime(2026, 10, 11, 7, 30)),
    ]
    assert [(p["tecnico"], p["num"]) for p in r.primera_orden(ordenes, FECHA)] == [("Ana", "2"), ("Beto", "3")]
    prom = r.promedio_arranque(ordenes, date(2026, 10, 11), FECHA)
    # Ana: 7:10 y 7:30 -> 7:20; Beto: la anulada de las 6:00 también cuenta como arranque
    assert [(p["tecnico"], p["dias"], p["hora_promedio"]) for p in prom] == [
        ("Beto", 1, "06:00:00"), ("Ana", 2, "07:20:00")]


def test_pendientes_para_dispatch():
    hoy = FECHA
    pend = [
        Ord("1", actividad="INSFIBRA", estado="ASIGNADA", es_viva=True, fecha_ape=DIA - timedelta(days=8)),
        Ord("2", actividad="INSFIBRA", comentario="cambio de medio", estado="PENDIENTE", es_viva=True, tecnico=None),
        Ord("3", actividad="SOPFIBRA", estado="ASIGNADA", es_viva=True, es_offline=True, fecha_ape=DIA),
        Ord("4", actividad="SOPFIBRA", comentario="sin señal de TV digital", estado="ASIGNADA", es_viva=True),
        Ord("5", actividad="PEXTERNO", estado="ASIGNADA", es_viva=True, fecha_ape=DIA - timedelta(days=5)),
    ]
    d = r.pendientes_dispatch(pend, hoy)
    resumen = {x["categoria"]: (x["asignadas"], x["sin_asignar"]) for x in d["resumen"]}
    assert resumen == {"INSTALACIONES": (1, 1), "MANTENIMIENTOS": (2, 0), "PLEX": (1, 0), "OTRAS": (0, 0)}
    assert d["totales"] == {"asignadas": 4, "sin_asignar": 1, "total": 5}
    assert [c["cantidad"] for c in d["cubetas"]] == [1, 1, 2, 1]
    assert {x["nombre"] for x in d["instalaciones"]} == {"Instalación Nueva", "Instalación Cambio de Medio"}
    assert {x["nombre"] for x in d["soporte"]} == {"ONT/ONU Offline", "Problemas de TV (Analógica o Digital)"}
    assert d["resto"] == [{"nombre": "PEXTERNO", "cantidad": 1}]
