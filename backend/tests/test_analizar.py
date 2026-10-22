"""
Tests de integración: POST /api/analizar y GET /api/validaciones/{id}/imagen.

Usan una imagen PNG mínima generada en memoria — no requieren archivos en disco
ni conexión real con Mercado Pago (mockeamos MpClient).

Por qué mockeamos MpClient y no la DB:
  MpClient hace requests HTTP externos — en tests de integración queremos
  controlar el resultado sin depender de credenciales ni del servicio externo.
  La DB de test es local y controlada, así que la usamos real.
"""
import io
import struct
import uuid
import zlib
from pathlib import Path
from unittest.mock import AsyncMock, patch

import db.connection as db_conn
import pytest
from models.resultado import FuenteOCR, ResultadoOCR


@pytest.fixture(autouse=True)
def _mock_r2(monkeypatch):
    """Intercepta llamadas a R2 — en CI no hay credenciales reales."""
    async def _subir_noop(key: str, imagen_bytes: bytes) -> None:
        pass

    async def _url_firmada_fake(key: str) -> str:
        return f"https://fake-r2-ci.example.com/{key}"

    monkeypatch.setattr("services.analizar_service.subir_imagen_async", _subir_noop)
    monkeypatch.setattr("routers.validaciones.subir_imagen_async", _subir_noop)
    monkeypatch.setattr("routers.validaciones.generar_url_firmada_async", _url_firmada_fake)


# ---------------------------------------------------------------------------
# Imagen PNG mínima válida generada en memoria
# ---------------------------------------------------------------------------

def _crear_png_minimo() -> bytes:
    """
    Construye un PNG de 1x1 pixel (blanco) desde cero, sin depender de Pillow.

    Estructura PNG:
      · Signature (8 bytes)
      · Chunk IHDR: ancho, alto, bit depth, color type, etc.
      · Chunk IDAT: datos de imagen comprimidos (zlib)
      · Chunk IEND: fin del archivo
    """
    def chunk_png(tipo: bytes, datos: bytes) -> bytes:
        crc = zlib.crc32(tipo + datos) & 0xFFFFFFFF
        return struct.pack(">I", len(datos)) + tipo + datos + struct.pack(">I", crc)

    firma = b"\x89PNG\r\n\x1a\n"

    # IHDR: 1x1, 8 bits por canal, RGB (color_type=2)
    ihdr_datos = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr = chunk_png(b"IHDR", ihdr_datos)

    # IDAT: un pixel blanco (RGB = 255, 255, 255)
    # El filtro de scanline es 0 (None), luego R, G, B
    scanline = b"\x00\xff\xff\xff"
    idat = chunk_png(b"IDAT", zlib.compress(scanline))

    iend = chunk_png(b"IEND", b"")

    return firma + ihdr + idat + iend


_PNG_MINIMO = _crear_png_minimo()


# ---------------------------------------------------------------------------
# Helper de upload
# ---------------------------------------------------------------------------

def _subir_imagen(client, admin_token, codigo_cliente="CLI001", contenido=None, content_type="image/png"):
    """Helper que realiza el POST /api/analizar con multipart/form-data."""
    imagen = contenido if contenido is not None else _PNG_MINIMO
    return client.post(
        "/api/analizar",
        files={"archivo": ("comprobante.png", io.BytesIO(imagen), content_type)},
        data={"codigo_cliente": codigo_cliente},
        cookies={"access_token": admin_token},
    )


# ---------------------------------------------------------------------------
# POST /api/analizar — casos básicos
# ---------------------------------------------------------------------------

def test_analizar_sin_jwt_devuelve_401(client):
    respuesta = client.post(
        "/api/analizar",
        files={"archivo": ("img.png", io.BytesIO(_PNG_MINIMO), "image/png")},
        data={"codigo_cliente": "CLI001"},
    )
    assert respuesta.status_code == 401


def test_analizar_sin_codigo_cliente_devuelve_422(client, admin_token):
    respuesta = client.post(
        "/api/analizar",
        files={"archivo": ("img.png", io.BytesIO(_PNG_MINIMO), "image/png")},
        cookies={"access_token": admin_token},
    )
    assert respuesta.status_code == 422


def test_analizar_codigo_cliente_vacio_devuelve_422(client, admin_token):
    respuesta = client.post(
        "/api/analizar",
        files={"archivo": ("img.png", io.BytesIO(_PNG_MINIMO), "image/png")},
        data={"codigo_cliente": "   "},
        cookies={"access_token": admin_token},
    )
    assert respuesta.status_code == 422


def test_analizar_tipo_no_permitido_devuelve_400(client, admin_token):
    respuesta = client.post(
        "/api/analizar",
        files={"archivo": ("doc.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        data={"codigo_cliente": "CLI001"},
        cookies={"access_token": admin_token},
    )
    assert respuesta.status_code == 400


def test_analizar_mime_spoofing_devuelve_400(client, admin_token):
    """
    Un archivo con contenido EXE (MZ header) pero Content-Type image/png
    debe ser rechazado por la validación de magic bytes.

    Verifica que no alcanza con declarar el tipo correcto — el contenido
    real del archivo también se valida.
    """
    exe_bytes = b"MZ" + b"\x00" * 100  # header de ejecutable Windows
    respuesta = client.post(
        "/api/analizar",
        files={"archivo": ("foto.png", io.BytesIO(exe_bytes), "image/png")},
        data={"codigo_cliente": "CLI001"},
        cookies={"access_token": admin_token},
    )
    assert respuesta.status_code == 400


def test_analizar_archivo_vacio_devuelve_400(client, admin_token):
    """
    Un archivo de 0 bytes no tiene magic bytes válidos y debe ser rechazado.
    """
    respuesta = client.post(
        "/api/analizar",
        files={"archivo": ("foto.png", io.BytesIO(b""), "image/png")},
        data={"codigo_cliente": "CLI001"},
        cookies={"access_token": admin_token},
    )
    assert respuesta.status_code == 400


# ---------------------------------------------------------------------------
# POST /api/analizar — persiste en DB
# ---------------------------------------------------------------------------

def test_analizar_persiste_validacion_en_db(client, admin_token, admin_test):
    """
    Un upload exitoso crea una fila en validaciones con canal='MANUAL'.
    El resultado incluye un 'id' que puede usarse en otros endpoints.
    """
    # El PNG mínimo no contiene texto — el OCR devolverá IMAGEN_INVALIDA o
    # NUMERO_OP_NO_ENCONTRADO. No necesitamos mockear MP porque no llega a llamarlo.
    respuesta = _subir_imagen(client, admin_token)

    assert respuesta.status_code == 200
    datos = respuesta.json()

    assert "id" in datos
    assert datos["canal"] == "MANUAL"
    assert datos["codigo_cliente"] == "CLI001"
    assert datos["estado"] in {
        "IMAGEN_INVALIDA", "NUMERO_OP_NO_ENCONTRADO", "REVISION_MANUAL",
        "APROBADO", "DUPLICADO", "MONTO_ADULTERADO",
        "PAGO_NO_ACREDITADO", "ERROR_DESTINATARIO", "ERROR_MP",
    }

    # Limpiar: borrar la validación creada por este test
    _limpiar_validacion(client, admin_token, datos["id"])


def test_analizar_modificado_por_nombre_es_null_en_upload_nuevo(client, admin_token):
    """
    Una validación recién creada por upload no fue editada manualmente —
    modificado_por_nombre debe ser null.

    Verifica que guardar_validacion_manual retorna el campo (no lo omite)
    y que su valor inicial es None.
    """
    respuesta = _subir_imagen(client, admin_token)

    assert respuesta.status_code == 200
    datos = respuesta.json()

    assert "modificado_por_nombre" in datos
    assert datos["modificado_por_nombre"] is None

    _limpiar_validacion(client, admin_token, datos["id"])


def test_analizar_canal_es_manual(client, admin_token):
    """Las validaciones creadas por upload manual siempre tienen canal='MANUAL'."""
    respuesta = _subir_imagen(client, admin_token)
    assert respuesta.status_code == 200
    assert respuesta.json()["canal"] == "MANUAL"

    _limpiar_validacion(client, admin_token, respuesta.json()["id"])


def test_analizar_guarda_imagen_path(client, admin_token):
    """
    La respuesta incluye imagen_path con la ruta relativa donde se guardó el archivo.
    El path debe contener el tenant_id y el id de la validación.
    """
    respuesta = _subir_imagen(client, admin_token)
    assert respuesta.status_code == 200
    datos = respuesta.json()

    imagen_path = datos.get("imagen_path")
    assert imagen_path is not None
    assert datos["id"] in imagen_path          # nombre del archivo = UUID de la validación
    assert imagen_path.endswith(".png")        # extensión preservada

    _limpiar_validacion(client, admin_token, datos["id"])


def test_analizar_con_mp_aprobado(client, admin_token):
    """
    Cuando el OCR detecta un número de operación y MP responde APROBADO,
    la validación se guarda con estado='APROBADO'.

    Mockeamos MpClient.verificar_pago para no depender del servicio externo.
    """
    with patch("services.validacion_core.MpClient") as MockMp:
        instancia_mp = MockMp.return_value
        instancia_mp.verificar_pago = AsyncMock(return_value=("APROBADO", 200))

        with patch("services.analizar_service.procesar_imagen", new_callable=AsyncMock) as mock_ocr:
            mock_ocr.return_value = ResultadoOCR(
                fuente=FuenteOCR.LLM_GEMINI,
                es_comprobante_valido=True,
                identificador_pago="12345678",
                monto_detectado="1500.00",
                cuit_destinatario_detectado="20123456789",
            )
            respuesta = _subir_imagen(client, admin_token, codigo_cliente="CLI_MP")

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["estado"] == "APROBADO"
    assert datos["canal"] == "MANUAL"

    _limpiar_validacion(client, admin_token, datos["id"])


# ---------------------------------------------------------------------------
# GET /api/validaciones/{id}/imagen
# ---------------------------------------------------------------------------

def test_imagen_devuelve_archivo(client, admin_token):
    """
    Después de subir una imagen, GET /api/validaciones/{id}/imagen
    devuelve el archivo con status 200.
    """
    respuesta_upload = _subir_imagen(client, admin_token)
    assert respuesta_upload.status_code == 200
    validacion_id = respuesta_upload.json()["id"]

    respuesta_imagen = client.get(
        f"/api/validaciones/{validacion_id}/imagen",
        cookies={"access_token": admin_token},
    )
    assert respuesta_imagen.status_code == 200
    assert len(respuesta_imagen.content) > 0

    _limpiar_validacion(client, admin_token, validacion_id)


def test_imagen_sin_jwt_devuelve_401(client, admin_token):
    respuesta_upload = _subir_imagen(client, admin_token)
    validacion_id = respuesta_upload.json()["id"]

    respuesta_imagen = client.get(f"/api/validaciones/{validacion_id}/imagen")
    assert respuesta_imagen.status_code == 401

    _limpiar_validacion(client, admin_token, validacion_id)


def test_imagen_validacion_inexistente_devuelve_404(client, admin_token):
    respuesta = client.get(
        f"/api/validaciones/{uuid.uuid4()}/imagen",
        cookies={"access_token": admin_token},
    )
    assert respuesta.status_code == 404


def test_imagen_validacion_sin_imagen_devuelve_404(client, admin_token, validacion_test):
    """
    validacion_test tiene canal='MANUAL' pero no tiene imagen_path (fue creada
    directamente en DB por el fixture sin imagen). Debe devolver 404.
    """
    respuesta = client.get(
        f"/api/validaciones/{validacion_test}/imagen",
        cookies={"access_token": admin_token},
    )
    assert respuesta.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/validaciones/{id}/imagen
# ---------------------------------------------------------------------------

def _reemplazar_imagen(client, admin_token, validacion_id, contenido=None, content_type="image/png"):
    """Helper para PATCH /api/validaciones/{id}/imagen."""
    imagen = contenido if contenido is not None else _PNG_MINIMO
    return client.patch(
        f"/api/validaciones/{validacion_id}/imagen",
        files={"imagen": ("comprobante.png", io.BytesIO(imagen), content_type)},
        cookies={"access_token": admin_token},
    )


def test_reemplazar_imagen_sin_jwt_devuelve_401(client, validacion_test):
    resp = client.patch(
        f"/api/validaciones/{validacion_test}/imagen",
        files={"imagen": ("comprobante.png", io.BytesIO(_PNG_MINIMO), "image/png")},
    )
    assert resp.status_code == 401


def test_reemplazar_imagen_uuid_invalido_devuelve_404(client, admin_token):
    resp = _reemplazar_imagen(client, admin_token, "no-es-uuid")
    assert resp.status_code == 404


def test_reemplazar_imagen_validacion_inexistente_devuelve_404(client, admin_token):
    import uuid as _uuid
    resp = _reemplazar_imagen(client, admin_token, str(_uuid.uuid4()))
    assert resp.status_code == 404


def test_reemplazar_imagen_tipo_no_permitido_devuelve_400(client, admin_token, validacion_test):
    resp = _reemplazar_imagen(client, admin_token, validacion_test, content_type="application/pdf")
    assert resp.status_code == 400


def test_reemplazar_imagen_actualiza_imagen_path(client, admin_token, validacion_test):
    """Reemplazar la imagen actualiza imagen_path en DB y lo devuelve en la respuesta."""
    resp = _reemplazar_imagen(client, admin_token, validacion_test)
    assert resp.status_code == 200
    datos = resp.json()
    assert datos["imagen_path"] is not None
    assert validacion_test in datos["imagen_path"]
    assert datos["imagen_path"].endswith(".png")


def test_reemplazar_imagen_aislamiento_multi_tenant(client, admin_token):
    """Tenant A no puede reemplazar la imagen de una validación de tenant B."""
    pool = db_conn.get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO validaciones (tenant_id, estado, canal) VALUES (%s, 'IMAGEN_INVALIDA', 'MANUAL') RETURNING id::text",
                ("otro_tenant_img",),
            )
            vid_otro = cur.fetchone()[0]
        conn.commit()
    finally:
        pool.putconn(conn)

    try:
        resp = _reemplazar_imagen(client, admin_token, vid_otro)
        assert resp.status_code == 404
    finally:
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM validaciones WHERE id = %s::uuid", (vid_otro,))
            conn.commit()
        finally:
            pool.putconn(conn)


# ---------------------------------------------------------------------------
# Helper de teardown
# ---------------------------------------------------------------------------

def _limpiar_validacion(client, admin_token, validacion_id: str) -> None:
    """
    Elimina la validación y su imagen de disco creada por un test.
    Usa la DB directamente para no depender de un endpoint DELETE (que no existe).
    """
    pool = db_conn.get_pool()
    conexion = pool.getconn()
    try:
        with conexion.cursor() as cur:
            # Obtener imagen_path antes de borrar
            cur.execute(
                "SELECT imagen_path FROM validaciones WHERE id = %s::uuid",
                (validacion_id,),
            )
            fila = cur.fetchone()
            imagen_path_relativo = fila[0] if fila else None

            cur.execute(
                "DELETE FROM auditoria WHERE validacion_id = %s::uuid",
                (validacion_id,),
            )
            cur.execute(
                "DELETE FROM validaciones WHERE id = %s::uuid",
                (validacion_id,),
            )
        conexion.commit()
    finally:
        pool.putconn(conexion)

    # Borrar imagen del disco si existe
    if imagen_path_relativo:
        backend_dir = Path(__file__).parent.parent
        ruta_imagen = backend_dir / imagen_path_relativo
        if ruta_imagen.exists():
            ruta_imagen.unlink()
