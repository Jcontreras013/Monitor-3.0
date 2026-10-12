import io
import zipfile
from datetime import date

from PIL import Image

from app.dominio.fechas import ahora_hn
from app.models import Personal


def png() -> bytes:
    salida = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 30, 30)).save(salida, format="PNG")
    return salida.getvalue()


async def entrar(cliente, crear_usuario, usuario="jefa", rol="jefe", **kw):
    await crear_usuario(usuario=usuario, rol=rol, **kw)
    r = await cliente.post("/api/auth/login", json={"usuario": usuario, "clave": "clave-segura-1"})
    assert r.status_code == 200, r.text
    return r.json()


async def crear(cliente, **datos):
    base = {"seccion": "operaciones", "colaborador": "Ana López", "motivo": "Llegada Tarde",
            "comentario": "Llegó 8:40 am", "fecha_incidencia": ahora_hn().date().isoformat()}
    base.update(datos)
    archivos = base.pop("archivos", None)
    return await cliente.post("/api/expedientes", data=base, files=archivos)


async def test_permisos_por_rol(cliente, crear_usuario):
    yo = await entrar(cliente, crear_usuario, usuario="mon", rol="monitoreo")
    assert "expedientes" not in yo["modulos"]
    assert (await cliente.get("/api/expedientes")).status_code == 403
    await cliente.post("/api/auth/logout")

    yo = await entrar(cliente, crear_usuario, usuario="llam", rol="llamados")
    assert yo["modulos"] == ["expedientes"]
    assert (await cliente.get("/api/expedientes")).status_code == 200
    assert (await cliente.get("/api/monitor/resumen")).status_code == 403


async def test_crear_listar_y_evidencias(cliente, crear_usuario, sesiones):
    async with sesiones() as s:
        s.add(Personal(nombre="ANA LÓPEZ", area="OPERACIONES", cargo="TECNICO PRINCIPAL"))
        await s.commit()
    await entrar(cliente, crear_usuario)

    catalogo = (await cliente.get("/api/expedientes/catalogo")).json()
    assert catalogo["personal"]["OPERACIONES"] == ["ANA LÓPEZ"]

    r = await crear(cliente, archivos=[("archivos", ("foto.png", png(), "image/png"))])
    assert r.status_code == 201, r.text
    nuevo = r.json()
    assert nuevo["colaborador"] == "ANA LÓPEZ" and nuevo["tipo_falta"] == "LLEGADA TARDE"
    assert nuevo["supervisor"] == "Jefa" and nuevo["clasificacion"] == "LEVE"
    assert len(nuevo["archivos"]) == 1

    foto = await cliente.get(f"/api/archivos/{nuevo['archivos'][0]['id']}")
    assert foto.status_code == 200 and foto.headers["content-type"] == "image/png"
    assert foto.headers["x-content-type-options"] == "nosniff"

    for _ in range(2):
        await crear(cliente)
    await crear(cliente, motivo="Otro", motivo_otro="mal cuidado del vehiculo", comentario="Rayones")
    await crear(cliente, motivo="Reco / Cambio de Postes", colaborador="", comentario="Cambio de postes en el centro")

    listado = (await cliente.get("/api/expedientes")).json()
    assert len(listado["registros"]) == 5
    assert listado["panel"]["clasificacion"] == {"GRAVE": 4, "LEVE": 0, "OTRO": 1}  # 3 tardes -> GRAVE
    assert {"colaborador": "ANA LÓPEZ", "tardes": 3, "otras": 1, "total": 4} in listado["resumen_mes"]
    assert "RECO" in listado["colaboradores"]

    solo_tardes = (await cliente.get("/api/expedientes", params={"tipo": "tarde"})).json()
    assert len(solo_tardes["registros"]) == 3
    de_reco = (await cliente.get("/api/expedientes", params={"colaborador": "RECO"})).json()
    assert de_reco["registros"][0]["tipo_falta"] == "RECO / CAMBIO DE POSTES"


async def test_validaciones(cliente, crear_usuario):
    await entrar(cliente, crear_usuario)
    assert (await crear(cliente, motivo="Inventado")).status_code == 400
    assert (await crear(cliente, motivo="Otro", motivo_otro=" ")).status_code == 400
    assert (await crear(cliente, comentario=" ")).status_code == 400
    assert (await crear(cliente, colaborador="")).status_code == 400
    falso = [("archivos", ("foto.png", b"<html>no es imagen</html>", "image/png"))]
    r = await crear(cliente, archivos=falso)
    assert r.status_code == 400 and "no es realmente" in r.json()["detail"]
    exe = [("archivos", ("virus.exe", b"MZ...", "application/octet-stream"))]
    assert (await crear(cliente, archivos=exe)).status_code == 400
    assert (await cliente.get("/api/expedientes")).json()["registros"] == []  # nada a medias


async def test_administrativo_por_area(cliente, crear_usuario):
    await entrar(cliente, crear_usuario)
    r = await crear(cliente, seccion="administrativo", area="SAC", colaborador="Sayra Escobar",
                    motivo="Amonestación Escrita", comentario="Trato inadecuado")
    assert r.status_code == 201, r.text
    await crear(cliente, seccion="administrativo", area="BODEGA", colaborador="Pedro", motivo="Ausencia Laboral",
                comentario="No se presentó")
    assert (await crear(cliente, seccion="administrativo", area="", colaborador="X")).status_code == 400

    todas = (await cliente.get("/api/expedientes", params={"seccion": "administrativo"})).json()
    assert len(todas["registros"]) == 2 and todas["areas"] == ["BODEGA", "SAC"]
    sac = (await cliente.get("/api/expedientes", params={"seccion": "administrativo", "area": "SAC"})).json()
    assert [r["colaborador"] for r in sac["registros"]] == ["SAYRA ESCOBAR"]
    operaciones = (await cliente.get("/api/expedientes")).json()
    assert operaciones["registros"] == []


async def test_borrar_solo_admin(cliente, crear_usuario):
    await entrar(cliente, crear_usuario)
    registro = (await crear(cliente, archivos=[("archivos", ("f.png", png(), "image/png"))])).json()
    assert (await cliente.delete(f"/api/expedientes/{registro['id']}")).status_code == 403
    await cliente.post("/api/auth/logout")

    await entrar(cliente, crear_usuario, usuario="root", rol="admin")
    assert (await cliente.delete(f"/api/expedientes/{registro['id']}")).status_code == 204
    assert (await cliente.delete(f"/api/expedientes/{registro['id']}")).status_code == 404
    assert (await cliente.get(f"/api/archivos/{registro['archivos'][0]['id']}")).status_code == 404


async def test_evidencia_no_visible_sin_permiso(cliente, crear_usuario):
    await entrar(cliente, crear_usuario)
    registro = (await crear(cliente, archivos=[("archivos", ("f.png", png(), "image/png"))])).json()
    await cliente.post("/api/auth/logout")
    await entrar(cliente, crear_usuario, usuario="mon", rol="monitoreo")
    assert (await cliente.get(f"/api/archivos/{registro['archivos'][0]['id']}")).status_code == 404


async def test_reportes(cliente, crear_usuario):
    await entrar(cliente, crear_usuario)
    await crear(cliente, archivos=[("archivos", ("f.png", png(), "image/png"))])
    await crear(cliente, colaborador="Beto Ruiz", motivo="Exceso de Velocidad", comentario="90 km/h")

    pdf = await cliente.get("/api/expedientes/reporte.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert "Reporte_Expedientes_General.pdf" in pdf.headers["content-disposition"]

    docx = await cliente.get("/api/expedientes/reporte.docx", params={"colaborador": "ANA LÓPEZ"})
    assert docx.status_code == 200 and docx.content.startswith(b"PK")
    with zipfile.ZipFile(io.BytesIO(docx.content)) as z:
        texto = z.read("word/document.xml").decode()
    assert "REPORTE DE FALTAS" in texto and "ANA LÓPEZ" in texto and "08:40" in texto

    consolidado = (await cliente.get("/api/expedientes/consolidado-mes")).json()
    assert consolidado["total"] == 2
    pdf_mes = await cliente.get("/api/expedientes/consolidado-mes.pdf")
    assert pdf_mes.content.startswith(b"%PDF")

    vacio = await cliente.get("/api/expedientes/reporte.pdf", params={"desde": date(2020, 1, 1).isoformat(),
                                                                        "hasta": date(2020, 1, 2).isoformat()})
    assert vacio.content.startswith(b"%PDF")


async def test_repositorio(cliente, crear_usuario):
    await entrar(cliente, crear_usuario)
    assert (await cliente.get("/api/expedientes/repositorio")).status_code == 403
    await cliente.post("/api/auth/logout")

    await entrar(cliente, crear_usuario, usuario="oscar", acceso_repositorio=True)
    zip_bytes = io.BytesIO()
    with zipfile.ZipFile(zip_bytes, "w") as z:
        z.writestr("carpeta/contrato.pdf", b"%PDF-1.4 contrato")
        z.writestr("carpeta/.DS_Store", b"basura")
        z.writestr("carpeta/script.exe", b"MZ")
    r = await cliente.post("/api/expedientes/repositorio", data={"colaborador": "ana lópez", "descripcion": "2026"},
                           files=[("archivos", ("docs.zip", zip_bytes.getvalue(), "application/zip")),
                                  ("archivos", ("cv.pdf", b"%PDF-1.4 cv", "application/pdf"))])
    assert r.status_code == 201, r.text
    assert sorted(a["nombre"] for a in r.json()) == ["contrato.pdf", "cv.pdf"]

    carpetas = (await cliente.get("/api/expedientes/repositorio")).json()
    assert carpetas[0]["colaborador"] == "ANA LÓPEZ" and len(carpetas[0]["archivos"]) == 2
    archivo_id = carpetas[0]["archivos"][0]["id"]
    assert (await cliente.get(f"/api/archivos/{archivo_id}")).status_code == 200
    assert (await cliente.delete(f"/api/expedientes/repositorio/{archivo_id}")).status_code == 204
    assert (await cliente.delete("/api/expedientes/repositorio/no-es-uuid")).status_code == 422
