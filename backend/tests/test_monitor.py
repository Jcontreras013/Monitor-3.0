from dataclasses import dataclass
from datetime import datetime, timedelta

from app.dominio import monitor as m
from app.dominio.normalizacion import normalizar_orden

AHORA = datetime(2026, 10, 12, 10, 0)
HOY = AHORA.date()


@dataclass
class Ord:
    num: str
    actividad: str = "SOPFIBRA"
    estado: str = "ASIGNADA"
    tecnico: str | None = "Ana"
    fecha_ape: datetime | None = AHORA - timedelta(hours=2)
    hora_ini: datetime | None = None
    hora_liq: datetime | None = None
    es_viva: bool = True
    es_offline: bool = False
    motivo: str = "🔧 Mantenimiento General"
    segmento: str = "RESIDENCIAL"
    grupo_tablero: str = "SOP"
    subtipo_tablero: str = "FTTH / FIBRA"


def cerrada(num, **kw):
    datos = dict(estado="CERRADA", es_viva=False, hora_ini=AHORA - timedelta(hours=3),
                 hora_liq=AHORA - timedelta(hours=1))
    datos.update(kw)
    return Ord(num, **datos)


def test_dias_retraso_y_cubetas():
    assert m.dias_retraso(Ord("1", fecha_ape=AHORA - timedelta(days=8)), HOY) == 8
    assert m.dias_retraso(Ord("1", fecha_ape=AHORA + timedelta(days=2)), HOY) == 0
    assert m.dias_retraso(Ord("1", fecha_ape=None), HOY) == 0
    assert m.dias_retraso(Ord("1", tecnico="JOSUE MIGUEL SAUCEDA", fecha_ape=AHORA - timedelta(days=9)), HOY) == 0
    assert [m.cubeta_retraso(d) for d in (0, 1, 3, 4, 6, 7, 30)] == [
        "= 0 Dia", "= 1 a 3 Dias", "= 1 a 3 Dias", "= 4 a 6 Dias", "= 4 a 6 Dias", ">= 7 Dia", ">= 7 Dia"]


def test_alerta_tiempo_solo_sopfibra_iniciada_hace_mas_de_2h():
    assert m.alerta_tiempo(Ord("1", hora_ini=AHORA - timedelta(minutes=121)), AHORA)
    assert not m.alerta_tiempo(Ord("1", hora_ini=AHORA - timedelta(minutes=90)), AHORA)
    assert not m.alerta_tiempo(Ord("1", hora_ini=None), AHORA)
    assert not m.alerta_tiempo(Ord("1", actividad="INSFIBRA", hora_ini=AHORA - timedelta(hours=5)), AHORA)


def test_cerradas_hoy_usa_el_corte_de_6am():
    ordenes = [
        cerrada("hoy"),
        cerrada("madrugada", hora_liq=datetime(2026, 10, 12, 4, 0)),  # cuenta para ayer
        cerrada("sin_tecnico", tecnico=None),
        cerrada("anulada", estado="ANULADA"),
    ]
    assert [o.num for o in m.cerradas_hoy(ordenes, HOY)] == ["hoy"]


def test_resumen_completo():
    ordenes = [
        Ord("1", fecha_ape=AHORA - timedelta(days=8)),
        Ord("2", es_offline=True, subtipo_tablero="ONT/ONU Offline", tecnico="Beto"),
        Ord("3", tecnico=None),
        Ord("4", actividad="INSFIBRA", grupo_tablero="INS", subtipo_tablero="Adición"),
        Ord("5", actividad="PEXTERNO", grupo_tablero="OTROS", subtipo_tablero="PEXTERNO", segmento="PLEX"),
        Ord("6", hora_ini=AHORA - timedelta(hours=3)),  # SOP con más de 2 h
        Ord("7", actividad="ACTIVARRES"),  # fuera de la lista blanca
        cerrada("8"),
        cerrada("9", fecha_ape=AHORA - timedelta(days=3)),
        Ord("10", estado="EN ESPERA", es_viva=False),  # estado desconocido
    ]
    r = m.calcular_resumen(ordenes, m.Filtros(), AHORA)

    assert r["total_base"] == 9
    assert r["kpis"] == {
        "pendientes_asignadas": 5,
        "cerradas_hoy": 2,
        "tecnicos_en_ruta": 2,
        "offline": 1,
        "total_pendientes": 6,
    }
    retraso = {x["cubeta"]: x["cantidad"] for x in r["retraso"]}
    assert retraso == {">= 7 Dia": 1, "= 4 a 6 Dias": 0, "= 1 a 3 Dias": 0, "= 0 Dia": 5}

    tablero = r["tablero"]
    assert tablero["sop"]["total"] == 4
    assert tablero["sop"]["exceden_2h"] == 1
    assert {"nombre": "Adición", "cantidad": 1} in tablero["instalaciones"]["subtipos"]
    assert [s["nombre"] for s in tablero["instalaciones"]["subtipos"]] == [
        "Nueva", "Adición", "Cambio / Migración", "Recuperado"]
    assert tablero["plex"] == {"subtipos": [{"nombre": "PEXTERNO", "cantidad": 1}], "total": 1}

    glob = next(x for x in r["consolidado"] if x["segmento"] == "GLOBAL")
    # 5 asignadas pendientes (1 en mora) + 2 cerradas hoy (1 abierta hoy, 1 en mora)
    assert (glob["total"], glob["cerradas"]) == (7, 2)
    assert (glob["mora_total"], glob["mora_cerradas"]) == (2, 1)
    assert (glob["hoy_total"], glob["hoy_cerradas"]) == (5, 1)
    plex = next(x for x in r["consolidado"] if x["segmento"] == "PLEX")
    assert plex["total"] == 1

    assert r["estados_no_reconocidos"] == [{"nombre": "EN ESPERA", "cantidad": 1}]


def test_filtros():
    ordenes = [
        Ord("1"),
        Ord("2", es_offline=True),
        Ord("3", hora_ini=AHORA - timedelta(hours=3)),
        Ord("4", tecnico=None),
        Ord("5", actividad="INSFIBRA", es_offline=True),
    ]
    criticas = m.aplicar_filtros(ordenes, m.Filtros(solo_criticas=True), AHORA)
    assert [o.num for o in criticas] == ["2", "3"]
    no_asig = m.calcular_resumen(ordenes, m.Filtros(no_asignadas=True), AHORA)
    assert no_asig["mostrando"] == 1 and no_asig["kpis"]["tecnicos_en_ruta"] == 0
    # Los conteos de los botones rápidos no dependen del botón activo...
    assert no_asig["rapidos"] == {"todas": 5, "criticas": 2, "no_asignadas": 1}
    # ...pero sí de los demás filtros.
    solo_ins = m.calcular_resumen(ordenes, m.Filtros(actividades=["INSFIBRA"], solo_criticas=True), AHORA)
    assert solo_ins["rapidos"] == {"todas": 1, "criticas": 0, "no_asignadas": 0}
    por_tecnico = m.aplicar_filtros(ordenes, m.Filtros(tecnico="Ana", actividades=["SOPFIBRA"]), AHORA)
    assert [o.num for o in por_tecnico] == ["1", "2", "3"]


def test_de_punta_a_punta_con_ordenes_normalizadas():
    crudas = [
        {"IDORDEN": "1", "NOMACTIVIDAD": "SOPFIBRA", "ESTADO": "Asignada", "TECNICO": "Ana",
         "COMENTARIO": "ONU OFFLINE", "FECHAAPERTURA": "05/10/2026 08:00"},
        {"IDORDEN": "2", "NOMACTIVIDAD": "INSFIBRA", "ESTADO": "Cerrada", "TECNICO": "Ana",
         "FECHAAPERTURA": "12/10/2026 07:00", "HORAINICIOORDEN": "12/10/2026 07:30",
         "HORACIERREORDEN": "12/10/2026 09:00"},
    ]
    ordenes = [normalizar_orden(c, AHORA) for c in crudas]
    r = m.calcular_resumen(ordenes, m.Filtros(), AHORA)
    assert r["kpis"]["offline"] == 1
    assert r["kpis"]["cerradas_hoy"] == 1
    assert r["retraso"][0] == {"cubeta": ">= 7 Dia", "cantidad": 1, "porcentaje": 100.0}
