from dataclasses import dataclass
from datetime import date

from app.dominio import expedientes as dom
from app.dominio.personal import leer_personal_administrativo, leer_personal_tecnico


@dataclass
class R:
    colaborador: str
    tipo_falta: str
    comentario: str = ""
    fecha_incidencia: date = date(2026, 10, 5)


def test_motivo_combinado_antiguo_se_separa():
    assert dom.normalizar_motivo("LLEGADA TARDÍA / AUSENCIA", "llegó 8:30") == dom.MOTIVO_LLEGADA_TARDE
    assert dom.normalizar_motivo("LLEGADA TARDÍA / AUSENCIA", "AUSENCIA sin aviso") == dom.MOTIVO_AUSENCIA
    assert dom.normalizar_motivo("Exceso de Velocidad", "") == "EXCESO DE VELOCIDAD"


def test_llegada_tarde_y_exclusiones():
    assert dom.es_llegada_tarde("Llegada Tarde", "")
    assert dom.es_llegada_tarde("OTRO", "llegó con RETRASO")
    assert not dom.es_llegada_tarde("ORDEN CERRADA TARDE", "")  # es de órdenes, no de llegada
    assert not dom.es_llegada_tarde("ALMUERZO EXCEDIDO", "regresó tarde del almuerzo")
    assert not dom.es_llegada_tarde("AUSENCIA LABORAL", "")


def test_clasificacion_grave():
    assert dom.clasificar_grave_o_leve("Exceso de Velocidad", "") == "GRAVE"  # motivo de vehículo
    assert dom.clasificar_grave_o_leve("Otro", "MAL CUIDADO DEL VEHÍCULO") == "GRAVE"
    assert dom.clasificar_grave_o_leve("Otro", "vehiculo sucio con basura") == "GRAVE"
    assert dom.clasificar_grave_o_leve("Otro", "orden aperturada con retraso") == "GRAVE"
    assert dom.clasificar_grave_o_leve("Llamado de Atención Verbal", "falta de respeto al supervisor") == "GRAVE"
    assert dom.clasificar_grave_o_leve("Otro", "inventó datos de metraje") == "GRAVE"
    assert dom.clasificar_grave_o_leve("AUSENCIA LABORAL", "sin aviso") == "GRAVE"


def test_clasificacion_leve_y_reincidencia():
    assert dom.clasificar_grave_o_leve("Llegada Tarde", "", n_tardes=2) == "LEVE"
    assert dom.clasificar_grave_o_leve("Llegada Tarde", "", n_tardes=3) == "GRAVE"
    assert dom.clasificar_grave_o_leve("AUSENCIA LABORAL", "cita personal") == "LEVE"
    assert dom.clasificar_grave_o_leve("Otro", "excedió almuerzo") == "LEVE"
    assert dom.clasificar_grave_o_leve("Mala Documentación", "") == "LEVE"
    # Ojo: "uniforme sucio" sin vehículo de por medio es LEVE, no GRAVE.
    assert dom.clasificar_grave_o_leve("Otro", "uniforme sucio") == "LEVE"
    assert dom.clasificar_grave_o_leve("Incidencia Médica", "cita en el IHSS") == "OTRO"
    assert dom.rubro("Llegada Tarde", "", 3) == "[GRAVE] LLEGADA TARDE"


def test_cumple_tipo():
    medica, tarde = R("A", "INCIDENCIA MÉDICA"), R("A", "LLEGADA TARDE")
    assert dom.cumple_tipo(medica, "medica") and not dom.cumple_tipo(medica, "llamado")
    assert dom.cumple_tipo(tarde, "tarde") and dom.cumple_tipo(tarde, "llamado")
    assert not dom.cumple_tipo(tarde, "ausencia")


def test_separar_colaborador_area():
    assert dom.separar_colaborador_area("Ana López (Administración)") == ("ANA LÓPEZ", "ADMINISTRACION")
    assert dom.separar_colaborador_area("  JUAN  PEREZ ") == ("JUAN PEREZ", "OPERACIONES")


def test_extraer_hora_falta():
    assert dom.extraer_hora_falta("llegó a las 8:30 am") == "08:30"
    assert dom.extraer_hora_falta("entró 2.15 p.m.") == "14:15"
    assert dom.extraer_hora_falta("sin hora", "07:05") == "07:05"
    assert dom.extraer_hora_falta("orden 12345", None) == "N/D"


def test_panel_y_resumenes():
    hoy = date(2026, 10, 12)
    registros = [
        R("ANA", "LLEGADA TARDE", fecha_incidencia=date(2026, 10, 1)),
        R("ANA", "LLEGADA TARDE", fecha_incidencia=date(2026, 10, 2)),
        R("ANA", "LLEGADA TARDE", fecha_incidencia=date(2026, 10, 5)),
        R("BETO", "EXCESO DE VELOCIDAD", fecha_incidencia=date(2026, 10, 5)),
        R("BETO", "INCIDENCIA MÉDICA", fecha_incidencia=date(2026, 9, 30)),
    ]
    panel = dom.panel(registros)
    assert panel["total"] == 5 and panel["personas"] == 2
    # 3 llegadas tarde de ANA -> las tres pasan a GRAVE.
    assert panel["clasificacion"] == {"GRAVE": 4, "LEVE": 0, "OTRO": 1}
    assert panel["rubro_dominante"] == "[GRAVE] LLEGADA TARDE"
    assert panel["reincidentes"] == [{"colaborador": "ANA", "motivo": "LLEGADA TARDE", "veces": 3}]
    assert dict((d["nombre"], d["cantidad"]) for d in panel["por_dia"])["Lunes"] == 2

    assert dom.resumen_mes_por_persona(registros, ["ANA", "BETO"], hoy) == [
        {"colaborador": "ANA", "tardes": 3, "otras": 0, "total": 3},
        {"colaborador": "BETO", "tardes": 0, "otras": 1, "total": 1},
    ]
    assert dom.consolidado_mes(registros, hoy) == [
        {"colaborador": "ANA", "faltas": 3}, {"colaborador": "BETO", "faltas": 1}]


def test_leer_catalogos_del_sistema_anterior():
    tecnicos = leer_personal_tecnico(
        "Harin Joel\tSevilla Pérez, Jefe de operaciones \n"
        "Jose Rafael\tCampos Pérez,Tecnico principal, ACTIVO\n"
        "Elias Mizael Alonzo Sabillon, FTTH, Tecnico principal, ACTIVO\n"
        "Luis Ayala, Ayudante-FTTH\n"
        "Marco Diaz, Tecnico principal, VACACIONES\n\n"
    )
    por_nombre = {t["nombre"]: t for t in tecnicos}
    assert por_nombre["JOSE RAFAEL CAMPOS PÉREZ"]["clasificacion"] == "TÉCNICO PRINCIPAL"
    assert por_nombre["ELIAS MIZAEL ALONZO SABILLON"]["clasificacion"] == "TÉCNICO PRINCIPAL"
    assert por_nombre["LUIS AYALA"]["clasificacion"] == "AYUDANTE"
    assert por_nombre["HARIN JOEL SEVILLA PÉREZ"]["clasificacion"] == "OTRAS ÁREAS / SOPORTE"
    assert por_nombre["MARCO DIAZ"]["estatus"] == "VACACIONES"
    assert all(t["area"] == "OPERACIONES" for t in tecnicos)

    admin = leer_personal_administrativo(
        "SAC ,\nAlejandra Fuentes Alcántara;\nSayra Michelle Escobar Garcia;\nDiana Watler.\n"
        "Administración,\nCarlos Garcia Ortega.\n"
    )
    assert ("SAYRA MICHELLE ESCOBAR GARCIA", "SAC") in {(a["nombre"], a["area"]) for a in admin}
    assert {"nombre": "CARLOS GARCIA ORTEGA", "area": "ADMINISTRACION"}.items() <= admin[-1].items()
    assert len(admin) == 4
