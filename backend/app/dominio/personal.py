"""
Lectura de los catálogos de personal del sistema anterior.

personal_tecnico.txt: una persona por línea, "Nombre<TAB>Apellidos, Cargo, Estatus".
personal_sac.txt: bloques "ÁREA, Persona1; Persona2; ... ." separados por punto.
"""

from __future__ import annotations

import unicodedata

from app.dominio.expedientes import AREA_OPERACIONES

CARGOS_PRINCIPAL = {"PLEX", "HFC", "FTTH", "TECNICO PRINCIPAL", "TECNICO", "TECNICO_PRINCIPAL"}


def _limpiar(texto: str) -> str:
    return " ".join(str(texto).replace("\t", " ").split()).upper()


def _sin_acentos(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")


def clasificar_cargo(cargo: str) -> str:
    """Igual que cargar_catalogo_tecnicos(): define quién es técnico principal."""
    cargo = _sin_acentos(cargo.upper())
    if cargo in CARGOS_PRINCIPAL:
        return "TÉCNICO PRINCIPAL"
    if "AYUDANTE" in cargo:
        return "AYUDANTE"
    if "SUPERVISOR" in cargo:
        return "SUPERVISOR"
    return "OTRAS ÁREAS / SOPORTE"


def leer_personal_tecnico(texto: str) -> list[dict]:
    personas: dict[str, dict] = {}
    for linea in texto.splitlines():
        if not linea.strip():
            continue
        partes = [p.strip() for p in linea.split(",")]
        nombre = _limpiar(partes[0])
        if not nombre:
            continue
        cargo = partes[1].upper() if len(partes) > 1 and partes[1] else "N/D"
        estatus = "VACACIONES" if len(partes) > 2 and "VACACIONES" in partes[2].upper() else "ACTIVO"
        personas.setdefault(nombre, {
            "nombre": nombre, "area": AREA_OPERACIONES, "cargo": cargo,
            "clasificacion": clasificar_cargo(cargo), "estatus": estatus,
        })
    return list(personas.values())


def leer_personal_administrativo(texto: str) -> list[dict]:
    personas: dict[tuple[str, str], dict] = {}
    for bloque in texto.replace("\n", " ").split("."):
        partes = bloque.strip().split(",", 1)
        area = _limpiar(_sin_acentos(partes[0])) if partes[0].strip() else ""
        if not area or len(partes) < 2:
            continue
        for nombre in (_limpiar(n) for n in partes[1].split(";")):
            if nombre:
                personas.setdefault((nombre, area), {
                    "nombre": nombre, "area": area, "cargo": "", "clasificacion": "ADMINISTRATIVO",
                    "estatus": "ACTIVO",
                })
    return list(personas.values())
