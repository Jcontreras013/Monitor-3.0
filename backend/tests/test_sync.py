"""Robot de sincronización contra un Cepheus simulado y un Postgres real."""

import asyncio
import json
from datetime import timedelta

import asyncpg
import httpx
from sqlalchemy import select

from app import repositorio
from app.config import url_libpq
from app.dominio.fechas import ahora_hn
from app.dominio.normalizacion import normalizar_orden
from app.eventos import CANAL_ORDENES
from app.models import DispositivoFttx, EstadoRobot, Orden
from worker.sync import ciclo_protegido, ejecutar_ciclo


def config_cepheus(entorno, **extra):
    return entorno.model_copy(update={
        "cepheus_url": "https://cepheus.interno/api/ordenes",
        "cepheus_usuario": "robot",
        "cepheus_contrasena": "secreta",
        "cepheus_usuarios_consulta": ["cuenta1", "cuenta2"],
        **extra,
    })


def cepheus_falso(respuestas):
    """Cliente httpx que contesta, en orden, las respuestas dadas y guarda las peticiones."""
    peticiones = []
    pendientes = list(respuestas)

    def manejar(request: httpx.Request):
        peticiones.append(request)
        return pendientes.pop(0)

    return httpx.AsyncClient(transport=httpx.MockTransport(manejar)), peticiones


def ok(ordenes):
    return httpx.Response(200, json={"codigo": 200, "mensaje": "OK", "ordenes": ordenes})


def orden_api(num, **kw):
    datos = {"IDORDEN": num, "NOMACTIVIDAD": "SOPFIBRA", "ESTADO": "Asignada", "TECNICO": "Ana López",
             "FECHAAPERTURA": (ahora_hn() - timedelta(days=1)).strftime("%d/%m/%Y %H:%M")}
    datos.update(kw)
    return datos


async def todas(sesiones):
    async with sesiones() as s:
        return {o.num: o for o in (await s.scalars(select(Orden))).all()}


async def test_ciclo_guarda_ordenes_y_aplica_catalogo_fttx(sesiones, entorno):
    async with sesiones() as s:
        s.add(DispositivoFttx(tecnico_clave="ANA LÓPEZ", tecnico="Ana López", mx="MX-07"))
        await s.commit()
    cliente, peticiones = cepheus_falso([ok([
        orden_api("100", COMENTARIO="ONU OFFLINE", **{"COLUMNA NUEVA": "x"}),
        orden_api("101", NOMACTIVIDAD="ACTUALIZARDATOSTECNICOS"),
        orden_api("102", ESTADO="", **{"ESTADO ORDEN": "Iniciada"}),
    ])])

    resultado = await ejecutar_ciclo(sesiones, config_cepheus(entorno), cliente_http=cliente)

    assert resultado.ok
    assert (resultado.recibidas, resultado.cambiadas, resultado.descartadas) == (3, 2, 1)
    ordenes = await todas(sesiones)
    assert set(ordenes) == {"100", "102"}
    assert ordenes["100"].es_offline and ordenes["100"].mx == "MX-07"
    assert ordenes["100"].datos == {"COLUMNA NUEVA": "x"}
    assert ordenes["102"].estado == "INICIADA"
    # La URL se arma igual que en el robot anterior.
    url = str(peticiones[0].url)
    assert "usuario=cuenta1&medios=FTTH,C&fechaInicio=" in url and "&horaInicio=07:00" in url
    assert peticiones[0].headers["authorization"].startswith("Basic ")


async def test_una_orden_cerrada_no_se_reabre_con_una_copia_vieja(sesiones, entorno):
    ahora = ahora_hn()
    async with sesiones() as s:
        cerrada = normalizar_orden({"NUM": "200", "ACTIVIDAD": "SOPFIBRA", "ESTADO": "CERRADA", "TECNICO": "Ana",
                                    "HORA_LIQ": (ahora - timedelta(hours=1)).isoformat()}, ahora)
        await repositorio.guardar_ordenes(s, [cerrada])
        await s.commit()
    cliente, _ = cepheus_falso([ok([orden_api("200"), orden_api("201")])])

    assert (await ejecutar_ciclo(sesiones, config_cepheus(entorno), cliente_http=cliente)).ok

    ordenes = await todas(sesiones)
    assert ordenes["200"].estado == "CERRADA" and not ordenes["200"].es_viva
    assert ordenes["201"].es_viva


async def test_viva_que_ya_no_viene_deja_de_ser_vigente(sesiones, entorno):
    cfg = config_cepheus(entorno)
    cliente, _ = cepheus_falso([ok([orden_api("300"), orden_api("301")]), ok([orden_api("300")])])
    assert (await ejecutar_ciclo(sesiones, cfg, cliente_http=cliente)).ok
    resultado = await ejecutar_ciclo(sesiones, cfg, cliente_http=cliente)

    assert resultado.no_vigentes == 1
    assert resultado.cambiadas == 0  # la 300 llegó igual: no se reescribe
    ordenes = await todas(sesiones)
    assert ordenes["300"].vigente and not ordenes["301"].vigente
    # Si vuelve a aparecer, vuelve a contar.
    cliente2, _ = cepheus_falso([ok([orden_api("300"), orden_api("301")])])
    await ejecutar_ciclo(sesiones, cfg, cliente_http=cliente2)
    assert (await todas(sesiones))["301"].vigente


async def test_limite_de_consultas_no_insiste_con_otras_cuentas(sesiones, entorno):
    cliente, peticiones = cepheus_falso([
        httpx.Response(200, json={"codigo": 102, "mensaje": "Excedió consultas por hora"}),
    ])
    resultado = await ejecutar_ciclo(sesiones, config_cepheus(entorno), cliente_http=cliente)
    assert not resultado.ok and "102" in resultado.motivo
    assert len(peticiones) == 1


async def test_si_una_cuenta_falla_prueba_la_siguiente(sesiones, entorno):
    cliente, peticiones = cepheus_falso([
        httpx.Response(400, text="La fecha no puede ser anterior a 2 meses"),
        ok([orden_api("400")]),
    ])
    resultado = await ejecutar_ciclo(sesiones, config_cepheus(entorno), cliente_http=cliente)
    assert resultado.ok and len(peticiones) == 2
    assert "usuario=cuenta2" in str(peticiones[1].url)


async def test_sin_configuracion_no_consulta(sesiones, entorno):
    resultado = await ejecutar_ciclo(sesiones, entorno.model_copy(update={"cepheus_url": ""}))
    assert not resultado.ok and "CEPHEUS_URL" in resultado.motivo


async def test_estado_del_robot_conserva_la_ultima_sincronizacion_buena(sesiones, entorno, monkeypatch):
    import worker.sync as sync

    respuestas = iter([sync.ResultadoCiclo(ok=True, recibidas=5), sync.ResultadoCiclo(ok=False, motivo="sin red")])

    async def falso(*_args, **_kw):
        return next(respuestas)

    monkeypatch.setattr(sync, "ejecutar_ciclo", falso)
    await ciclo_protegido(sesiones, entorno)
    async with sesiones() as s:
        primera_ok = (await s.get(EstadoRobot, 1)).ultima_sync_ok
    await ciclo_protegido(sesiones, entorno)
    async with sesiones() as s:
        estado = await s.get(EstadoRobot, 1)
    assert not estado.sync_ok and estado.motivo == "sin red"
    assert estado.ultima_sync_ok == primera_ok is not None


async def test_avisa_a_los_navegadores_al_terminar(sesiones, entorno):
    recibido: asyncio.Queue = asyncio.Queue()
    conexion = await asyncpg.connect(url_libpq(entorno.database_url))
    await conexion.add_listener(CANAL_ORDENES, lambda *a: recibido.put_nowait(a[3]))
    try:
        cliente, _ = cepheus_falso([ok([orden_api("500")])])
        await ejecutar_ciclo(sesiones, config_cepheus(entorno), cliente_http=cliente)
        aviso = json.loads(await asyncio.wait_for(recibido.get(), timeout=5))
        assert aviso["cambiadas"] == 1
    finally:
        await conexion.close()
