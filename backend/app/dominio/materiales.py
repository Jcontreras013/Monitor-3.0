"""
Uso de cajas molex según el comentario de cierre del técnico.

Port de materiales.py. Criterio de MAXCOM:
  - toda casa ya tiene su molex desde la instalación (INSFIBRA), y esa se
    depuró en ese momento. Si en un cambio de acometida el técnico menciona
    "la molex" de la casa ("fibra dañada en la molex, se preparó y se
    fusiona"), NO se vuelve a depurar;
  - la que sí se depura es una molex NUEVA EN MEDIO del tramo, entre la mufa
    y la casa, para empalmar ("se le añadió una molex", "molex en medio").
Reglas sacadas de los cortes de acometida de septiembre 2026.
"""

from __future__ import annotations

import re
import unicodedata

# Soportes de fibra cuyos cierres se revisan para la alerta de molex.
ACTIVIDADES_ALERTA_MOLEX = ("SOPFIBRA", "SOPFIBRACORP")

MOLEX_NUEVA = (
    r"MOLEX (EN MEDIO|A MITAD|INTERMEDIA|EN EL POSTE|EN EL TRAMO)|(EN MEDIO|A MITAD|MITAD DEL)[^.,]{0,30}MOLEX|"
    r"EMPALM[^.,]{0,20}MOLEX|"
    r"(DEJ[OAE]|DEJAR|PUS[OI]|PONER|COLOC|INSTAL|ANADI|AGREG|SE USO|UTILIZ|HACERLE|HACER UNA|"
    r"SE HIZO UNA|CAMBI[OA]R? (LA |DE )?(CAJA )?)[^.,]{0,25}MOLEX\b(?! NUEVAMENTE)|MOLEX (NUEVA\b|TEMPORAL|PROVISIONAL)"
)
# "Hasta una molex que ya estaba" o "se eliminó la molex" no dejan duda,
# aunque la misma frase diga "una molex": se revisan antes que lo nuevo.
MOLEX_EXISTENTE_SEGURO = (
    r"MOLEX (QUE YA|YA EXISTENTE|EXISTENTE|DEL CLIENTE|INTERNA DEL)|(ELIMIN|RETIR|QUIT)[^.,]{0,25}MOLEX"
)
MOLEX_EXISTENTE = (
    r"(TENIA|TIENE|HABIA|ESTA|ENCONTRABA CON)( UNA| DOS)?( CAJA)? MOLEX|"
    r"(SU|LA|EN LA|DE LA|DENTRO DE LA)( CAJA)? MOLEX|MOLEX (DE LA CASA|INTERNA|DENTRO)|"
    r"(DANAD|DAAD|CORTAD|COMID|HILO)[^.,]{0,40}EN UNA( CAJA)? MOLEX|"
    r"MOLEX[^.,]{0,40}(PREPAR|REPAR|REPER|DANAR|DAAR)|PREPAR[^.,]{0,20}MOLEX|MOLEX NUEVAMENTE"
)
# Sin mencionar la molex: cambiar un tramo o dejar una reparación provisional
# obliga a empalmar, así que una molex es posible aunque no se nombre.
TRABAJO_CON_EMPALME = r"TRAMO|PROVISIONAL|TEMPORAL|EMPALM"

COMENTARIO_NUEVA = "Molex nueva en medio del tramo"
COMENTARIO_EXISTENTE = "Molex de la casa (ya depurada en la instalación)"
COMENTARIO_AMBIGUO = "Menciona molex sin decir si es en medio o la de la casa"
COMENTARIO_REEMPLAZO_CASA = "Molex nueva en la casa (reemplazo)"
COMENTARIO_EMPALME = "Cambió un tramo / reparación provisional"
COMENTARIO_NADA = "No menciona molex"
# Los que generan la alerta: debe haber una molex depurada en Odoo.
COMENTARIOS_MOLEX_NUEVA = (COMENTARIO_NUEVA, COMENTARIO_REEMPLAZO_CASA)

VEREDICTO_CUADRA = "✅ Cuadra"
VEREDICTO_PROBABLE = "🟡 Probable"
VEREDICTO_REVISAR = "🔎 Revisar"
VEREDICTO_CONTRADICE = "❌ Contradice"
VEREDICTO_SIN_RESPALDO = "⚠️ Sin respaldo"
VEREDICTO_SIN_DEPURAR = "🔍 Usada sin depurar"


def sin_acentos_mayus(texto: str) -> str:
    """
    Mayúsculas sin acentos, carácter por carácter (mismo largo que el original,
    para poder recortar la frase del texto original). Cepheus a veces entrega
    la ñ dañada como "¿" ("da¿aron"): se lee como N.
    """
    return "".join((unicodedata.normalize("NFKD", ch)[:1] or ch) for ch in str(texto).replace("¿", "n")).upper()


def clasificar_comentario_molex(comentario: str | None) -> tuple[str, str]:
    """Devuelve (qué dice del uso de molex, frase del comentario que lo muestra)."""
    original = comentario or ""
    texto = sin_acentos_mayus(original)

    def frase(inicio: int, fin: int) -> str:
        inicio, fin = max(0, inicio - 70), min(len(original), fin + 70)
        return ("…" if inicio else "") + original[inicio:fin].strip() + ("…" if fin < len(original) else "")

    if "MOLEX" in texto:
        for patron, tipo in ((MOLEX_EXISTENTE_SEGURO, COMENTARIO_EXISTENTE), (MOLEX_NUEVA, COMENTARIO_NUEVA),
                             (MOLEX_EXISTENTE, COMENTARIO_EXISTENTE)):
            m = re.search(patron, texto)
            if m:
                # "Se dejó molex en la casa ya que no se encontró la que tenían":
                # es nueva, pero reemplaza la de la casa, no va en medio.
                if tipo == COMENTARIO_NUEVA and "CASA" in texto[m.end():m.end() + 25]:
                    tipo = COMENTARIO_REEMPLAZO_CASA
                return tipo, frase(m.start(), m.end())
        i = texto.find("MOLEX")
        return COMENTARIO_AMBIGUO, frase(i, i + 5)
    m = re.search(TRABAJO_CON_EMPALME, texto)
    if m:
        return COMENTARIO_EMPALME, frase(m.start(), m.end())
    return COMENTARIO_NADA, frase(0, 150) if original else ""


def veredicto_molex(cajas_depuradas: float, lo_que_dice: str) -> str | None:
    """Veredicto de una orden según si se depuró molex y qué dice el comentario (None = no aplica)."""
    if cajas_depuradas > 0:
        return {
            COMENTARIO_NUEVA: VEREDICTO_CUADRA,
            COMENTARIO_EMPALME: VEREDICTO_PROBABLE,
            COMENTARIO_AMBIGUO: VEREDICTO_REVISAR,
            COMENTARIO_REEMPLAZO_CASA: VEREDICTO_REVISAR,
            COMENTARIO_EXISTENTE: VEREDICTO_CONTRADICE,
        }.get(lo_que_dice, VEREDICTO_SIN_RESPALDO)
    # Sin depuración, mencionar la molex sin aclarar casi siempre es la de la
    # casa, que no se depura: cuadra. Solo falta la depuración si dice en medio.
    return {
        COMENTARIO_NUEVA: VEREDICTO_SIN_DEPURAR,
        COMENTARIO_REEMPLAZO_CASA: VEREDICTO_SIN_DEPURAR,
        COMENTARIO_AMBIGUO: VEREDICTO_CUADRA,
        COMENTARIO_EXISTENTE: VEREDICTO_CUADRA,
    }.get(lo_que_dice)
