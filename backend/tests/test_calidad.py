from dataclasses import dataclass
from datetime import timedelta

from app import repositorio
from app.dominio import calidad as dom
from app.dominio.fechas import ahora_hn
from app.dominio.normalizacion import normalizar_orden
from tests.utiles import entrar, png


# --- Dominio --------------------------------------------------------------------
@dataclass
class G:
    tecnico: str = "ANA"
    metodo_auditoria: str = dom.METODO_COMPLETADA
    aprobacion_interna: str = "Servicio aprobado"
    p1: int | None = 5
    p2: int | None = 5
    p3: int | None = 4
    p4: int | None = None
    p5: int | None = 5
    p6: int | None = 3
    p7: int | None = 5


def test_resultado_de_la_gestion():
    assert dom.resultado(dom.METODO_COMPLETADA, "Servicio aprobado") == "Aprobado"
    assert dom.resultado(dom.METODO_COMPLETADA, "Servicio con observaciones") == "Con Obs."
    assert dom.resultado(dom.METODO_COMPLETADA, "Servicio no aprobado – requiere seguimiento") == "Rechazado"
    # Una llamada que no se contestó no es un servicio "rechazado".
    assert dom.resultado("Gestión sin encuesta - Requiere seguimiento",
                         "Servicio no aprobado – requiere seguimiento") == "Sin Gestión"


def test_csat_diagnostico_y_resumen():
    gestiones = [G(p7=5), G(p7=4, tecnico="BETO"), G(p7=2, aprobacion_interna="Servicio con observaciones"),
                 G(p7=None, metodo_auditoria="Gestión sin encuesta - Número equivocado", p1=None, p2=None,
                   p3=None, p5=None, p6=None)]
    assert dom.csat(gestiones) == {"csat": 66.7, "validas": 3, "top": 2}
    diag = {d["pregunta"]: d for d in dom.diagnostico(gestiones)}
    assert diag["1. Puntualidad del técnico"] == {"pregunta": "1. Puntualidad del técnico", "promedio": 5.0,
                                                   "respuestas": 3}
    assert "4. Explicación sobre el servicio de TV Cable y CCVEO" not in diag  # todas "No aplica"
    ana = next(r for r in dom.resumen_por_tecnico(gestiones) if r["tecnico"] == "ANA")
    assert (ana["total"], ana["aprobado"], ana["con_obs"], ana["sin_gestion"]) == (3, 1, 1, 1)
    assert dom.promedio_encuesta({"p1": 5, "p4": None, "p7": 4}) == 4.5


def test_busqueda_por_orden_cliente_o_nombre():
    assert dom.coincide_busqueda("9570", "95700125", "215431", "Juan")
    assert dom.coincide_busqueda("2154", "95700125", "215431", "Juan")
    assert dom.coincide_busqueda("juan pérez", "1", "2", "JUAN CARLOS PEREZ LOPEZ")
    assert not dom.coincide_busqueda("juan gomez", "1", "2", "JUAN CARLOS PEREZ LOPEZ")
    assert not dom.coincide_busqueda(" ", "1", "2", "JUAN")


# --- API -----------------------------------------------------------------------
async def _ordenes(sesiones):
    ahora = ahora_hn()
    crudas = [
        {"NUM": "1001", "ACTIVIDAD": "INSFIBRA", "ESTADO": "CERRADA", "TECNICO": "Ana López", "CLIENTE": "500",
         "NOMBRE": "Juan Carlos Pérez López", "HORA_INI": (ahora - timedelta(days=1, hours=3)).isoformat(),
         "HORA_LIQ": (ahora - timedelta(days=1, hours=2)).isoformat()},
        {"NUM": "1002", "ACTIVIDAD": "INSFIBRA", "ESTADO": "CERRADA", "TECNICO": "Beto Ruiz", "CLIENTE": "501",
         "NOMBRE": "María Gómez", "HORA_LIQ": (ahora - timedelta(days=2)).isoformat()},
        {"NUM": "1003", "ACTIVIDAD": "SOPFIBRA", "ESTADO": "ASIGNADA", "TECNICO": "Ana López", "CLIENTE": "502",
         "NOMBRE": "Pedro Juárez"},
        {"NUM": "1004", "ACTIVIDAD": "INSFIBRA", "ESTADO": "CERRADA", "TECNICO": "Ana López", "CLIENTE": "503",
         "NOMBRE": "Lucía Vieja", "HORA_LIQ": (ahora - timedelta(days=40)).isoformat()},
        {"NUM": "1005", "ACTIVIDAD": "SOPFIBRA", "ESTADO": "ANULADA", "NOMBRE": "Juan Anulado"},
    ]
    async with sesiones() as s:
        await repositorio.guardar_ordenes(s, [normalizar_orden(c, ahora) for c in crudas])
        await s.commit()


ENCUESTA = {"num_orden": "1001", "contesto": True, "p1": 5, "p2": 5, "p3": 4, "p4": None, "p5": 5, "p6": 4,
            "p7": 5, "aprobacion_interna": "Servicio aprobado", "tipo_nota": "Promesa",
            "detalle_nota": "Volver a llamar el lunes"}


async def test_vistas_por_usuario(cliente, crear_usuario):
    await entrar(cliente, crear_usuario, usuario="miguel", rol="monitoreo")
    assert (await cliente.get("/api/calidad/configuracion")).json()["pestanas"] == ["campo", "historico"]
    assert (await cliente.post("/api/calidad/gestiones", json=ENCUESTA)).status_code == 403
    await cliente.post("/api/auth/logout")
    await entrar(cliente, crear_usuario, usuario="sac", rol="monitoreo")
    config = (await cliente.get("/api/calidad/configuracion")).json()
    assert config["pestanas"] == ["llamadas", "insfibra", "historico"] and not config["puede_borrar"]


async def test_busqueda_de_ordenes(cliente, crear_usuario, sesiones):
    await _ordenes(sesiones)
    await entrar(cliente, crear_usuario, usuario="calidad", rol="monitoreo")
    nums = lambda r: [o["num"] for o in r.json()]  # noqa: E731
    assert nums(await cliente.get("/api/calidad/ordenes", params={"q": "juan perez"})) == ["1001"]
    assert set(nums(await cliente.get("/api/calidad/ordenes", params={"q": "100"}))) == {"1001", "1002", "1003", "1004"}
    assert nums(await cliente.get("/api/calidad/ordenes", params={"q": "502"})) == ["1003"]
    await cliente.post("/api/auth/logout")
    # SAC solo ve INSFIBRA cerradas de los últimos 15 días.
    await entrar(cliente, crear_usuario, usuario="sac", rol="monitoreo")
    assert set(nums(await cliente.get("/api/calidad/ordenes", params={"q": "100"}))) == {"1001", "1002"}


async def test_gestiones_de_llamada(cliente, crear_usuario, sesiones):
    await _ordenes(sesiones)
    await entrar(cliente, crear_usuario)
    r = await cliente.post("/api/calidad/gestiones", json=ENCUESTA)
    assert r.status_code == 201, r.text
    g = r.json()
    assert g["tecnico"] == "Ana López" and g["nombre_cliente"] == "Juan Carlos Pérez López"
    assert g["resultado"] == "Aprobado" and g["promedio"] == 4.67
    assert g["aceptacion_digital"] == "Juan Carlos Pérez López"

    incompleta = {**ENCUESTA, "p7": None}
    assert (await cliente.post("/api/calidad/gestiones", json=incompleta)).status_code == 400
    fuera_de_rango = {**ENCUESTA, "p1": 6}
    assert (await cliente.post("/api/calidad/gestiones", json=fuera_de_rango)).status_code == 422

    sin_contestar = {"num_orden": "1002", "contesto": False, "estado_llamada": "No contestó / Buzón de voz",
                     "resultado_gestion": "Requiere seguimiento"}
    falla = (await cliente.post("/api/calidad/gestiones", json=sin_contestar)).json()
    assert falla["resultado"] == "Sin Gestión" and falla["p7"] is None
    assert falla["aprobacion_interna"].startswith("Servicio no aprobado")
    invalida = {**sin_contestar, "resultado_gestion": "x"}
    assert (await cliente.post("/api/calidad/gestiones", json=invalida)).status_code == 400
    assert (await cliente.post("/api/calidad/gestiones", json={**ENCUESTA, "num_orden": "999"})).status_code == 404

    notas = (await cliente.get("/api/calidad/ordenes/1001/notas")).json()
    assert [n["detalle_nota"] for n in notas] == ["Volver a llamar el lunes"]

    cierres = (await cliente.get("/api/calidad/insfibra")).json()
    assert (cierres["total"], cierres["llamadas"], cierres["pendientes"]) == (2, 2, 0)
    pdf = await cliente.get("/api/calidad/insfibra.pdf")
    assert pdf.content.startswith(b"%PDF")

    hist = (await cliente.get("/api/calidad/historico")).json()
    assert len(hist["gestiones"]) == 2 and hist["csat"] == {"csat": 100.0, "validas": 1, "top": 1}
    assert (await cliente.get("/api/calidad/historico.pdf")).content.startswith(b"%PDF")

    assert (await cliente.delete(f"/api/calidad/gestiones/{g['id']}")).status_code == 204


async def test_cierres_insfibra_pendientes(cliente, crear_usuario, sesiones):
    await _ordenes(sesiones)
    await entrar(cliente, crear_usuario)
    await cliente.post("/api/calidad/gestiones", json=ENCUESTA)
    hoy = ahora_hn().date()
    r = (await cliente.get("/api/calidad/insfibra", params={"solo_pendientes": True})).json()
    assert [f["num"] for f in r["filas"]] == ["1002"] and r["pendientes"] == 1
    viejo = (await cliente.get("/api/calidad/insfibra", params={
        "desde": (hoy - timedelta(days=45)).isoformat(), "hasta": hoy.isoformat()})).json()
    assert viejo["total"] == 3  # sin el límite de 7 días de la sesión del sistema anterior


async def test_auditorias_de_campo_y_falta_desde_fibra(cliente, crear_usuario, sesiones):
    await _ordenes(sesiones)
    await entrar(cliente, crear_usuario)
    r = await cliente.post("/api/calidad/auditorias", data={
        "tipo": "fibra", "num_orden": "1003", "ruta_acometida": "Poste 3 a NAP", "metraje": "45M",
        "evaluacion": "Deficiente / Mal trabajo", "comentario": "Acometida floja"},
        files=[("fotos", ("f.png", png(), "image/png"))])
    assert r.status_code == 201, r.text
    auditoria = r.json()
    assert auditoria["tecnico"] == "Ana López" and len(auditoria["archivos"]) == 1
    assert (await cliente.post("/api/calidad/auditorias", data={"tipo": "operaciones", "num_orden": "1003",
                                                                 "estetica": "Fea"})).status_code == 400
    ok = await cliente.post("/api/calidad/auditorias", data={"tipo": "operaciones", "num_orden": "1003",
                                                              "estetica": "Excelente", "vineta": "V-1"})
    assert ok.status_code == 201

    hist = (await cliente.get("/api/calidad/historico", params={"base": "fibra"})).json()
    assert len(hist["auditorias"]) == 1 and hist["resumen"][1]["filas"] == [{"nombre": "Deficiente / Mal trabajo",
                                                                              "cantidad": 1}]
    assert (await cliente.get("/api/calidad/historico.pdf", params={"base": "operaciones"})).content.startswith(b"%PDF")

    # Expedientes: aparece pendiente y se convierte en falta vinculada.
    pendientes = (await cliente.get("/api/expedientes/auditorias-fibra")).json()
    assert [p["id"] for p in pendientes] == [auditoria["id"]]
    falta = await cliente.post("/api/expedientes", data={
        "seccion": "operaciones", "colaborador": "Ana López", "motivo": "Trabajo Deficiente (Auditoría de Fibra)",
        "comentario": "[Auditoría de fibra ORD-1003] Acometida floja", "auditoria_id": str(auditoria["id"])})
    assert falta.status_code == 201, falta.text
    assert (await cliente.get("/api/expedientes/auditorias-fibra")).json() == []
    listado = (await cliente.get("/api/expedientes", params={"colaborador": "ANA LÓPEZ"})).json()
    assert listado["auditorias_fibra"][0]["expediente_id"] == falta.json()["id"]

    assert (await cliente.delete(f"/api/calidad/auditorias/{auditoria['id']}")).status_code == 204
    assert (await cliente.get(f"/api/archivos/{auditoria['archivos'][0]['id']}")).status_code == 404


async def test_solo_gerencia_borra(cliente, crear_usuario, sesiones):
    await _ordenes(sesiones)
    await entrar(cliente, crear_usuario, usuario="calidad", rol="monitoreo")
    g = (await cliente.post("/api/calidad/gestiones", json=ENCUESTA)).json()
    assert (await cliente.delete(f"/api/calidad/gestiones/{g['id']}")).status_code == 403
