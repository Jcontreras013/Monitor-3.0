"""
Qué módulos ve cada rol (igual que el menú del sistema anterior):

- admin y jefe: todo.
- llamados: solo Expedientes.
- cualquier otro rol (monitoreo, sac...): Monitor en vivo y Control de Calidad.

Dentro de Control de Calidad, el NOMBRE DE USUARIO (no el rol) decide la
vista, también como antes: `sac` ve llamadas y cierres INSFIBRA de los
últimos 15 días; `miguel` ve las auditorías de campo; el resto, todo.
"""

from __future__ import annotations

MODULOS = (
    "monitor", "calidad", "expedientes", "reprogramadas", "reportes", "vehiculos", "configuracion",
)
ROLES_COMPLETOS = frozenset({"admin", "jefe"})
ROLES_SOLO_EXPEDIENTES = frozenset({"llamados"})
MODULOS_BASICOS = ("monitor", "calidad")

USUARIOS_CALIDAD_SOLO_LLAMADAS = frozenset({"sac"})
USUARIOS_CALIDAD_SOLO_CAMPO = frozenset({"miguel"})


def modulos_de(rol: str) -> list[str]:
    rol = (rol or "").strip().lower()
    if rol in ROLES_COMPLETOS:
        return list(MODULOS)
    if rol in ROLES_SOLO_EXPEDIENTES:
        return ["expedientes"]
    return list(MODULOS_BASICOS)


def puede(rol: str, modulo: str) -> bool:
    return modulo in modulos_de(rol)


def es_admin(rol: str) -> bool:
    return (rol or "").strip().lower() == "admin"
