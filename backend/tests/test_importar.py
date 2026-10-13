"""Importación del histórico de Google Sheets (CSV) a Postgres."""

from __future__ import annotations

import csv

from sqlalchemy import select

from app.models import AuditoriaCampo, GestionCalidad
from scripts.importar_historial import importar_auditorias, importar_calidad


def _csv(ruta, filas: list[dict]) -> str:
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=list({k: None for fila in filas for k in fila}))
        escritor.writeheader()
        escritor.writerows(filas)
    return str(ruta)


async def test_importa_gestiones_de_calidad_sin_duplicar(sesiones, tmp_path):
    ruta = _csv(tmp_path / "Calidad.csv", [
        {"FECHA_GESTION": "2026-03-02 09:15:00", "TICKET": "ORD-95100001", "CLIENTE_ID": "200100",
         "NOMBRE_CLIENTE": "Juan Pérez", "TECNICO": "Carlos Mejía", "ACTIVIDAD": "INSFIBRA",
         "FECHA_VISITA": "2026-03-01", "P1_PUNTUALIDAD": "5", "P2_PRESENTACION_TRATO": "4",
         "P3_CLARIDAD_EXPLICACION": "5", "P4_EXPLICACION_TV_CCVEO": "N/A", "P5_CALIDAD_SERVICIO": "5",
         "P6_LIMPIEZA_TRABAJO": "4", "P7_SATISFACCION_GENERAL": "5", "MEJORAS_OPCIONAL": "Ninguna",
         "ACEPTACION_DIGITAL": "Juan Pérez", "HORA_CIERRE_SERVICIO": "08:40 AM",
         "APROBACION_INTERNA": "Servicio aprobado", "METODO_AUDITORIA": "Llamada Telefónica Completada",
         "TIPO_NOTA": "Ninguna", "DETALLE_NOTA": "N/A"},
        {"FECHA_GESTION": "2026-03-02 10:00:00", "TICKET": "ORD-95100002", "TECNICO": "Ana Rodríguez",
         "P1_PUNTUALIDAD": "N/A", "P7_SATISFACCION_GENERAL": "N/A", "MEJORAS_OPCIONAL": "Buzón de voz",
         "RESULTADO_GESTION": "No contestó", "FECHA_LIMITE_SEGUIMIENTO": "2026-03-05",
         "APROBACION_INTERNA": "Sin encuesta completada",
         "METODO_AUDITORIA": "Gestión sin encuesta - No contestó", "TIPO_NOTA": "Seguimiento",
         "DETALLE_NOTA": "Llamar por la tarde"},
        {"FECHA_GESTION": "", "TICKET": "ORD-1"},
    ])
    await importar_calidad(sesiones, ruta)
    await importar_calidad(sesiones, ruta)  # repetirla no duplica

    async with sesiones() as s:
        gestiones = (await s.scalars(select(GestionCalidad).order_by(GestionCalidad.fecha_gestion))).all()
    assert len(gestiones) == 2
    llamada, sin_encuesta = gestiones
    assert llamada.num_orden == "95100001" and llamada.contesto
    assert (llamada.p1, llamada.p4, llamada.p7) == (5, None, 5)
    assert llamada.mejoras == ""
    assert not sin_encuesta.contesto and sin_encuesta.p7 is None
    assert sin_encuesta.mejoras == "Buzón de voz"
    assert sin_encuesta.fecha_limite_seguimiento.isoformat() == "2026-03-05"
    assert (sin_encuesta.tipo_nota, sin_encuesta.detalle_nota) == ("Seguimiento", "Llamar por la tarde")


async def test_importa_auditorias_de_fibra_con_fotos_y_conversion(sesiones, tmp_path):
    ruta = _csv(tmp_path / "Auditoria_Fibra.csv", [
        {"FECHA_AUDITORIA": "2026-04-10 14:00:00", "ORDEN_NUM": "95200001", "CODIGO_CLIENTE": "200200",
         "NOMBRE_CLIENTE": "María", "TECNICO": "Luis Hernández", "RUTA_ACOMETIDA": "Poste 3 a NAP",
         "METRAJE": "45M", "VINETA": "V-1", "COMENTARIOS": "Sin grapas",
         "EVALUACION_TRABAJO": "Deficiente / Mal trabajo",
         "IMAGENES_URLS": "https://files.catbox.moe/a.jpg, https://files.catbox.moe/b.jpg",
         "SUPERVISOR": "miguel", "CONVERTIDO_A_FALTA": "SI"},
        {"FECHA_AUDITORIA": "2026-04-11 09:00:00", "ORDEN_NUM": "95200002", "TECNICO": "Karla Flores",
         "EVALUACION_TRABAJO": "Deficiente / Mal trabajo", "SUPERVISOR": "miguel", "CONVERTIDO_A_FALTA": ""},
    ])
    await importar_auditorias(sesiones, ruta, "fibra")
    await importar_auditorias(sesiones, ruta, "fibra")

    async with sesiones() as s:
        auditorias = (await s.scalars(select(AuditoriaCampo).order_by(AuditoriaCampo.fecha_auditoria))).all()
    assert len(auditorias) == 2
    convertida, pendiente = auditorias
    assert convertida.tipo == "fibra" and convertida.convertido_a_falta
    assert convertida.comentario == "Sin grapas" and convertida.metraje == "45M"
    assert convertida.urls_externas == ["https://files.catbox.moe/a.jpg", "https://files.catbox.moe/b.jpg"]
    assert not pendiente.convertido_a_falta


async def test_importa_auditorias_de_instalaciones(sesiones, tmp_path):
    ruta = _csv(tmp_path / "Instalaciones.csv", [
        {"FECHA_AUDITORIA": "2026-05-01 11:30:00", "TECNICO": "Pedro Sánchez", "ORDEN_NUM": "95300001",
         "CODIGO_CLIENTE": "200300", "CODIGO_SERVICIO": "INSFIBRA", "TIEMPO_INVERTIDO": "45 minutos",
         "TIPO_FO": "Drop Flat", "METROS_FO": "60", "VINETA": "V-9", "RUTA_ACOMETIDA": "Fachada",
         "MUFA": "M-2", "COMENTARIO_AUDITOR": "Bien", "SUPERVISOR": "oscar"},
    ])
    await importar_auditorias(sesiones, ruta, "instalaciones")
    async with sesiones() as s:
        a = await s.scalar(select(AuditoriaCampo))
    assert (a.tipo, a.metraje, a.actividad, a.comentario) == ("instalaciones", "60", "INSFIBRA", "Bien")
