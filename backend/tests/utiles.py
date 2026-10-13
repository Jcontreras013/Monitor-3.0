"""Ayudas compartidas por las pruebas."""

import io

from PIL import Image


def png() -> bytes:
    salida = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 30, 30)).save(salida, format="PNG")
    return salida.getvalue()


async def entrar(cliente, crear_usuario, usuario="jefa", rol="jefe", **kw):
    await crear_usuario(usuario=usuario, rol=rol, **kw)
    r = await cliente.post("/api/auth/login", json={"usuario": usuario, "clave": "clave-segura-1"})
    assert r.status_code == 200, r.text
    return r.json()
