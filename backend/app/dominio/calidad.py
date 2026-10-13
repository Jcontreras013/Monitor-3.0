"""
Reglas de Control de Calidad, portadas de monitor-operativo/ccalidad.py y
tools.py (_clasificar_gestion_calidad, CSAT y diagnóstico).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import Protocol

from app.dominio.nombres import normalizar_nombre_cruce

PREGUNTAS = (
    ("p1", "Puntualidad del técnico"),
    ("p2", "Presentación y trato del técnico"),
    ("p3", "Claridad en la explicación del trabajo realizado"),
    ("p4", "Explicación sobre el servicio de TV Cable y CCVEO"),
    ("p5", "Calidad del servicio (instalación/mantenimiento)"),
    ("p6", "Estado en que dejó el área de trabajo"),
    ("p7", "Nivel de satisfacción general con la visita"),
)
# La P4 admite "No aplica" (cliente sin TV Cable / CCVEO).
PREGUNTAS_OPCIONALES = frozenset({"p4"})
# Las seis primeras sirven de diagnóstico; la 7 define el CSAT.
DIAGNOSTICO = PREGUNTAS[:6]

APROBACIONES = (
    "Servicio aprobado",
    "Servicio con observaciones",
    "Servicio no aprobado – requiere seguimiento",
)
ESTADOS_SIN_CONTESTAR = ("No contestó / Buzón de voz", "Número apagado o fuera de servicio")
RESULTADOS_GESTION = (
    "Cliente no desea participar",
    "Responsable no disponible",
    "Llamada reprogramada",
    "Número equivocado",
    "Sin respuesta después de dos intentos",
    "Requiere seguimiento",
)
TIPOS_NOTA = ("Ninguna", "Seguimiento", "Promesa")
METODO_COMPLETADA = "Llamada Telefónica Completada"

TIPOS_AUDITORIA = ("operaciones", "instalaciones", "fibra")
ESTETICAS = ("Excelente", "Aceptable", "Deficiente")
EVALUACIONES_FIBRA = ("Correcto", "Con observaciones", "Deficiente / Mal trabajo")
EVALUACION_DEFICIENTE = "Deficiente / Mal trabajo"

RESULTADOS = ("Aprobado", "Con Obs.", "Rechazado", "Sin Gestión")
# SAC solo encuesta INSFIBRA cerradas de los últimos días.
DIAS_INSFIBRA_SAC = 15


class GestionLike(Protocol):
    tecnico: str
    metodo_auditoria: str
    aprobacion_interna: str
    p1: int | None
    p7: int | None


def resultado(metodo_auditoria: str, aprobacion_interna: str) -> str:
    """
    'Aprobado' / 'Con Obs.' / 'Rechazado' / 'Sin Gestión'. Se mira primero el
    método: una llamada que ni se contestó no es un servicio "rechazado".
    """
    metodo = (metodo_auditoria or "").strip()
    if metodo and "Completada" not in metodo:
        return "Sin Gestión"
    aprobacion = (aprobacion_interna or "").strip()
    if aprobacion == "Servicio aprobado":
        return "Aprobado"
    if aprobacion == "Servicio con observaciones":
        return "Con Obs."
    if aprobacion.startswith("Servicio no aprobado"):
        return "Rechazado"
    return "Sin Gestión"


def promedio_encuesta(calificaciones: dict[str, int | None]) -> float | None:
    """Promedio 1-5 de una encuesta (6 preguntas si la P4 quedó en "No aplica")."""
    valores = [v for v in calificaciones.values() if v is not None]
    return round(sum(valores) / len(valores), 2) if valores else None


def csat(gestiones: Iterable[GestionLike]) -> dict:
    """% de respuestas válidas que calificaron 4 o 5 la satisfacción general (P7)."""
    p7 = [g.p7 for g in gestiones if g.p7 is not None]
    top = sum(1 for v in p7 if v >= 4)
    return {"csat": round(top / len(p7) * 100, 1) if p7 else None, "validas": len(p7), "top": top}


def diagnostico(gestiones: list) -> list[dict]:
    filas = []
    for clave, texto in DIAGNOSTICO:
        valores = [getattr(g, clave) for g in gestiones if getattr(g, clave) is not None]
        if valores:
            filas.append({"pregunta": f"{clave[1]}. {texto}", "promedio": round(sum(valores) / len(valores), 2),
                          "respuestas": len(valores)})
    return filas


def resumen_por_tecnico(gestiones: Iterable[GestionLike]) -> list[dict]:
    por_tecnico: dict[str, Counter] = {}
    for g in gestiones:
        por_tecnico.setdefault(g.tecnico or "N/D", Counter())[resultado(g.metodo_auditoria, g.aprobacion_interna)] += 1
    return [
        {"tecnico": t, "total": sum(c.values()), "aprobado": c["Aprobado"], "con_obs": c["Con Obs."],
         "rechazado": c["Rechazado"], "sin_gestion": c["Sin Gestión"]}
        for t, c in sorted(por_tecnico.items(), key=lambda x: -sum(x[1].values()))
    ]


def conteo(valores: Iterable[str]) -> list[dict]:
    return [{"nombre": k or "N/D", "cantidad": v} for k, v in Counter(valores).most_common()]


def coincide_busqueda(texto: str, num: str, cliente: str | None, nombre: str | None) -> bool:
    """
    Busca por número de orden, número de cliente o nombre. En el nombre basta
    con que estén TODAS las palabras escritas, en cualquier orden (así "JUAN
    PEREZ" encuentra a "JUAN CARLOS PEREZ LOPEZ").
    """
    q = texto.strip().upper()
    if not q:
        return False
    if q in (num or "").upper() or q in (cliente or "").upper():
        return True
    palabras = normalizar_nombre_cruce(q).split()
    nombre_norm = normalizar_nombre_cruce(nombre or "")
    return bool(palabras) and all(p in nombre_norm for p in palabras)
