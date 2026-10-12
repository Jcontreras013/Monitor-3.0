import asyncio
from datetime import UTC, datetime, timedelta

from app import repositorio
from app.dominio.fechas import ahora_hn
from app.dominio.normalizacion import normalizar_orden


async def entrar(cliente, usuario="javier", clave="clave-segura-1"):
    return await cliente.post("/api/auth/login", json={"usuario": usuario, "clave": clave})


async def test_login_y_sesion(cliente, crear_usuario):
    await crear_usuario()
    assert (await cliente.get("/api/auth/me")).status_code == 401

    malo = await entrar(cliente, clave="otra")
    assert malo.status_code == 401

    r = await entrar(cliente, usuario="  JAVIER ")
    assert r.status_code == 200
    assert r.json() == {
        "usuario": "javier", "nombre": "Javier", "rol": "admin", "acceso_repositorio": False,
        "modulos": ["monitor", "calidad", "expedientes", "reprogramadas", "reportes", "vehiculos", "configuracion"],
    }
    assert "httponly" in r.headers["set-cookie"].lower()

    assert (await cliente.get("/api/auth/me")).json()["usuario"] == "javier"

    await cliente.post("/api/auth/logout")
    assert (await cliente.get("/api/auth/me")).status_code == 401


async def test_bloqueo_tras_intentos_fallidos(cliente, crear_usuario):
    await crear_usuario(usuario="bloqueable")
    for _ in range(5):
        assert (await entrar(cliente, usuario="bloqueable", clave="mala")).status_code == 401
    assert (await entrar(cliente, usuario="bloqueable")).status_code == 429


async def test_cambiar_clave_invalida_las_otras_sesiones(cliente, crear_usuario):
    await crear_usuario()
    await entrar(cliente)
    cookie_vieja = cliente.cookies.get("monitor_sesion")
    # Los tokens tienen resolución de segundos: el cambio debe caer en un segundo posterior.
    await asyncio.sleep(1.1)

    corta = await cliente.post("/api/auth/cambiar-clave", json={"clave_actual": "clave-segura-1", "clave_nueva": "123"})
    assert corta.status_code == 422
    mala = await cliente.post("/api/auth/cambiar-clave", json={"clave_actual": "otra", "clave_nueva": "nueva-clave-99"})
    assert mala.status_code == 400
    r = await cliente.post("/api/auth/cambiar-clave",
                           json={"clave_actual": "clave-segura-1", "clave_nueva": "nueva-clave-99"})
    assert r.status_code == 204
    # Esta sesión sigue viva (se renovó la cookie)...
    assert (await cliente.get("/api/auth/me")).status_code == 200
    # ...pero una cookie emitida antes del cambio ya no sirve.
    cliente.cookies.clear()
    cliente.cookies.set("monitor_sesion", cookie_vieja)
    assert (await cliente.get("/api/auth/me")).status_code == 401
    cliente.cookies.clear()
    assert (await entrar(cliente, clave="clave-segura-1")).status_code == 401
    assert (await entrar(cliente, clave="nueva-clave-99")).status_code == 200


async def test_rol_llamados_no_ve_el_monitor(cliente, crear_usuario):
    await crear_usuario(usuario="sac2", rol="llamados")
    await entrar(cliente, usuario="sac2")
    assert (await cliente.get("/api/monitor/resumen")).status_code == 403


async def test_monitor_con_datos(cliente, crear_usuario, sesiones):
    ahora = ahora_hn()
    hace = lambda **kw: (ahora - timedelta(**kw)).strftime("%Y-%m-%d %H:%M:%S")  # noqa: E731
    crudas = [
        {"NUM": "1", "ACTIVIDAD": "SOPFIBRA", "ESTADO": "ASIGNADA", "TECNICO": "Ana",
         "COMENTARIO": "ONU OFFLINE", "FECHA_APE": hace(days=8), "GPS": "https://maps/1"},
        {"NUM": "2", "ACTIVIDAD": "SOPFIBRA", "ESTADO": "INICIADA", "TECNICO": "Beto",
         "FECHA_APE": hace(hours=1), "HORA_INI": hace(minutes=30), "GPS": "https://maps/2"},
        {"NUM": "3", "ACTIVIDAD": "INSFIBRA", "ESTADO": "PENDIENTE", "TECNICO": "",
         "FECHA_APE": hace(hours=1)},
        {"NUM": "4", "ACTIVIDAD": "ACTIVARRES", "ESTADO": "PENDIENTE"},  # se descarta
        {"NUM": "5", "ACTIVIDAD": "CEQUI", "ESTADO": "PENDIENTE", "TECNICO": "Ana",
         "FECHA_APE": hace(days=90)},  # vieja, pero viva: sí cuenta
    ]
    async with sesiones() as s:
        ordenes = [o for c in crudas if (o := normalizar_orden(c, ahora))]
        await repositorio.guardar_ordenes(s, ordenes)
        await s.commit()

    await crear_usuario(rol="monitoreo")
    await entrar(cliente)

    r = (await cliente.get("/api/monitor/resumen")).json()
    assert r["kpis"]["total_pendientes"] == 4
    assert r["kpis"]["pendientes_asignadas"] == 3
    assert r["kpis"]["offline"] == 1
    assert r["kpis"]["tecnicos_en_ruta"] == 2

    criticas = (await cliente.get("/api/monitor/resumen", params={"solo_criticas": True})).json()
    assert criticas["mostrando"] == 1

    lista = (await cliente.get("/api/monitor/ordenes", params={"tecnico": "Ana"})).json()
    assert [o["num"] for o in lista] == ["5", "1"]  # más días de retraso primero
    # GPS solo en órdenes ya iniciadas y abiertas.
    todas = {o["num"]: o for o in (await cliente.get("/api/monitor/ordenes")).json()}
    assert todas["1"]["gps"] is None and todas["2"]["gps"] == "https://maps/2"

    filtros = (await cliente.get("/api/monitor/filtros")).json()
    assert filtros["tecnicos"] == ["Ana", "Beto"]
    assert "ACTIVARRES" not in filtros["actividades"]


async def test_estado_del_robot(cliente, crear_usuario, sesiones):
    await crear_usuario()
    await entrar(cliente)
    assert (await cliente.get("/api/robot/estado")).json() is None
    async with sesiones() as s:
        await repositorio.guardar_estado_robot(
            s, ultimo_ciclo=datetime.now(UTC) - timedelta(hours=2), sync_ok=False, motivo="límite",
            ultima_sync_ok=None, ordenes_recibidas=0, duracion_seg=1.0)
        await s.commit()
    estado = (await cliente.get("/api/robot/estado")).json()
    assert estado["atrasado"] is True and estado["motivo"] == "límite"


async def test_salud(cliente):
    assert (await cliente.get("/api/salud")).json() == {"ok": True}
