import asyncio
from datetime import UTC, datetime, timedelta

from app import repositorio
from app.dominio.fechas import ahora_hn
from app.dominio.normalizacion import normalizar_orden
from app.models import EstadoAlerta


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


async def test_reprogramadas_y_no_instalados(cliente, crear_usuario, sesiones):
    ahora = ahora_hn()
    fmt = "%Y-%m-%d %H:%M:%S"
    crudas = [
        {"NUM": "10", "ACTIVIDAD": "INSFIBRA", "ESTADO": "ASIGNADA", "TECNICO": "Ana",
         "FECHA_APE": (ahora + timedelta(days=3)).strftime(fmt)},
        {"NUM": "11", "ACTIVIDAD": "SOPFIBRA", "ESTADO": "ASIGNADA", "TECNICO": "Ana",
         "FECHA_APE": (ahora - timedelta(days=1)).strftime(fmt)},
        {"NUM": "12", "ACTIVIDAD": "NOINSTALADO", "ESTADO": "CERRADA", "TECNICO": "Beto",
         "FECHA_APE": (ahora - timedelta(days=1)).strftime(fmt),
         "HORA_LIQ": (ahora + timedelta(hours=6)).strftime(fmt)},  # HORA_LIQ viene 6 h adelantada
    ]
    async with sesiones() as s:
        await repositorio.guardar_ordenes(s, [o for c in crudas if (o := normalizar_orden(c, ahora))])
        await s.commit()

    await crear_usuario(usuario="mon", rol="monitoreo")
    await entrar(cliente, usuario="mon")
    assert (await cliente.get("/api/reprogramadas")).status_code == 403

    cliente.cookies.clear()
    await crear_usuario(usuario="jefa", rol="jefe")
    await entrar(cliente, usuario="jefa")
    r = (await cliente.get("/api/reprogramadas")).json()
    assert [(o["num"], o["dias_para_cita"]) for o in r["reprogramadas"]] == [("10", 3)]
    assert [o["num"] for o in r["no_instalados"]] == ["12"]


async def test_configuracion_vip_y_panel_del_monitor(cliente, crear_usuario, sesiones):
    ahora = ahora_hn()
    async with sesiones() as s:
        await repositorio.guardar_ordenes(s, [normalizar_orden(
            {"NUM": "20", "ACTIVIDAD": "SOPFIBRA", "ESTADO": "ASIGNADA", "TECNICO": "Ana", "CLIENTE": "200100",
             "FECHA_APE": (ahora - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")}, ahora)])
        await s.commit()

    await crear_usuario(usuario="mon", rol="monitoreo")
    await entrar(cliente, usuario="mon")
    assert (await cliente.get("/api/configuracion/vip")).status_code == 403
    assert (await cliente.get("/api/monitor/vip")).json() == []

    cliente.cookies.clear()
    await crear_usuario(usuario="jefa", rol="jefe")
    await entrar(cliente, usuario="jefa")
    csv = b"CLIENTE,NOMBRE,CLASE\n200100,Hotel Palmira,Corporativo\n300,Otro,\n"
    archivo = {"archivo": ("vip.csv", csv, "text/csv")}
    previa = (await cliente.post("/api/configuracion/vip/vista-previa", files=archivo)).json()
    assert (previa["nuevos"], previa["salen"], len(previa["clientes"])) == (2, 0, 2)
    assert (await cliente.get("/api/configuracion/vip")).json() == []  # la vista previa no guarda

    assert (await cliente.put("/api/configuracion/vip", json=previa["clientes"])).json() == {"total": 2}
    assert [c["cliente"] for c in (await cliente.get("/api/configuracion/vip")).json()] == ["200100", "300"]
    malo = await cliente.post("/api/configuracion/vip/vista-previa", files={"archivo": ("vip.xls", b"x", "x")})
    assert malo.status_code == 400 and ".xlsx" in malo.json()["detail"]

    panel = (await cliente.get("/api/monitor/vip")).json()
    assert [(o["num"], o["nombre_vip"], o["clase_vip"]) for o in panel] == [("20", "Hotel Palmira", "Corporativo")]

    async with sesiones() as s:
        s.add(EstadoAlerta(alerta="Clientes VIP", resultado="enviado", detalle="1 orden(es): 20"))
        await s.commit()
    correo = (await cliente.get("/api/configuracion/correo")).json()
    assert "CORREO_SERVIDOR" in correo["falta"] and correo["contrasena_configurada"] is False
    assert [(a["alerta"], a["resultado"]) for a in correo["alertas"]] == [("Clientes VIP", "enviado")]
    prueba = await cliente.post("/api/configuracion/correo/prueba")
    assert prueba.status_code == 502 and "falta configurar" in prueba.json()["detail"]
