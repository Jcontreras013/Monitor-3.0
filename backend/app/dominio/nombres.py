"""
Cruce de nombres de personal (técnicos y SAC).

Port de normalizar_nombre_cruce() y resolver_tecnico_por_similitud() de
monitor-operativo/tools.py. Lo usan el catálogo de técnicos del Monitor y,
en fases siguientes, Expedientes y el bot de Telegram (para resolver el
nombre que un jefe teclea contra el catálogo real, tolerando typos).
"""

from __future__ import annotations

import difflib
import unicodedata

# Variantes conocidas del nombre de un mismo técnico entre fuentes de datos.
ALIAS_TECNICOS_CONOCIDOS = {
    "JOSUE MIGUEL SAUCEDA": "JOSE MIGUEL SAUCEDA",
    "JERMY MODESTO PADILLA": "JERMI MODESTO PADILLA",
    "JEREMY MODESTO PADILLA": "JERMI MODESTO PADILLA",
    "JERMY MODESTO PADILLA CARDONA": "JERMI MODESTO PADILLA CARDONA",
    "JEREMY MODESTO PADILLA CARDONA": "JERMI MODESTO PADILLA CARDONA",
    "JERNY MODESTO PADILLA CARDONA": "JERMI MODESTO PADILLA CARDONA",
    "JERNY MODESTO PADILLA": "JERMI MODESTO PADILLA",
    "ELIAS MIZAEL SABILLON": "ELIAS MISAEL ALONZO SABILLON",
    "ELIAS MISAEL SABILLON": "ELIAS MISAEL ALONZO SABILLON",
    "ELIAS MISAEL ALONZO": "ELIAS MISAEL ALONZO SABILLON",
    "DANIEL EZEQUIEL PONCE GUZMAN": "DANIEL EZEQUIEL GUZMAN PONCE",
    "NELAON RAMON FERRUFINO LEON": "NELSON RAMON FERRUFINO LEON",
}


def normalizar_nombre_cruce(texto) -> str:
    """Mayúsculas, sin acentos ni caracteres invisibles, espacios simples y alias resueltos."""
    if texto is None:
        return ""
    t = str(texto).upper().strip()
    if t == "NAN":
        return ""
    t = t.replace("‌", "").replace("​", "")
    t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    t = " ".join(t.split())
    return ALIAS_TECNICOS_CONOCIDOS.get(t, t)


def _tokens_en_orden(corta, larga) -> bool:
    """True si cada palabra de `corta` aparece en `larga`, en el mismo orden."""
    it = iter(larga)
    return all(tok in it for tok in corta)


def resolver_tecnico_por_similitud(nombre_tecleado, nombres_existentes):
    """
    Busca entre los nombres conocidos uno igual o muy parecido al tecleado.

    Devuelve (nombre_a_guardar, nombre_detectado_o_None): el segundo valor es
    distinto de None solo cuando hubo una sustitución. Si el nombre es ambiguo
    (calza con más de una persona) NO se adivina: se devuelve el original.
    """
    if not nombre_tecleado or not nombres_existentes:
        return nombre_tecleado, None

    norm_tecleado = normalizar_nombre_cruce(nombre_tecleado)
    if not norm_tecleado:
        return nombre_tecleado, None

    mapa_norm: dict[str, str] = {}
    for n in nombres_existentes:
        norm_n = normalizar_nombre_cruce(n)
        if norm_n and norm_n not in mapa_norm:
            mapa_norm[norm_n] = n

    # 1) Coincidencia exacta tras normalizar.
    if norm_tecleado in mapa_norm:
        nombre_real = mapa_norm[norm_tecleado]
        return nombre_real, (nombre_real if nombre_real != nombre_tecleado else None)

    # 2) Nombre incompleto (mínimo 2 palabras) contenido en orden dentro del otro.
    tokens_tecleado = norm_tecleado.split()
    candidatos = []
    for norm_n, nombre_real in mapa_norm.items():
        tokens_n = norm_n.split()
        if len(tokens_tecleado) <= len(tokens_n):
            mas_corto, mas_largo = tokens_tecleado, tokens_n
        else:
            mas_corto, mas_largo = tokens_n, tokens_tecleado
        if len(mas_corto) >= 2 and _tokens_en_orden(mas_corto, mas_largo):
            candidatos.append(nombre_real)
    if len(candidatos) == 1:
        return candidatos[0], candidatos[0]

    # 2.5) Una sola palabra: se compara solo contra el PRIMER nombre de cada
    # persona; exacto primero y, si no hay ninguno, tolerando typos.
    if len(tokens_tecleado) == 1:
        tok = tokens_tecleado[0]
        exactos = {real for norm_n, real in mapa_norm.items() if norm_n.split()[0] == tok}
        if len(exactos) == 1:
            unico = next(iter(exactos))
            return unico, unico
        if not exactos:
            parecidos = {
                real for norm_n, real in mapa_norm.items()
                if difflib.SequenceMatcher(None, tok, norm_n.split()[0]).ratio() >= 0.8
            }
            if len(parecidos) == 1:
                unico = next(iter(parecidos))
                return unico, unico

    # 3) Similitud aproximada con umbral alto.
    coincidencias = difflib.get_close_matches(norm_tecleado, list(mapa_norm.keys()), n=1, cutoff=0.88)
    if coincidencias:
        nombre_real = mapa_norm[coincidencias[0]]
        return nombre_real, nombre_real

    return nombre_tecleado, None
