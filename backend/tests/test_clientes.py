"""
Tests de integración: módulo de clientes.
Cubre CRUD, gestión de teléfonos y CUITs, importación CSV y dry-run de preview.
"""
import uuid

import db.connection as db_conn

_CSV_HEADER = "codigo_cliente,razon_social,direccion,telefonos,cuits\n"


# =============================================================================
# Helpers
# =============================================================================

def _listar(client, token, solo_activos=False):
    return client.get(
        "/api/clientes",
        params={"solo_activos": solo_activos},
        cookies={"access_token": token},
    )


def _crear(client, token, codigo, razon_social, direccion=None):
    body = {"codigo_cliente": codigo, "razon_social": razon_social}
    if direccion:
        body["direccion"] = direccion
    return client.post("/api/clientes", json=body, cookies={"access_token": token})


def _obtener(client, token, cliente_id):
    return client.get(f"/api/clientes/{cliente_id}", cookies={"access_token": token})


def _actualizar(client, token, cliente_id, **campos):
    return client.patch(
        f"/api/clientes/{cliente_id}",
        json=campos,
        cookies={"access_token": token},
    )


def _agregar_telefono(client, token, cliente_id, telefono):
    return client.post(
        f"/api/clientes/{cliente_id}/telefonos",
        json={"telefono": telefono},
        cookies={"access_token": token},
    )


def _eliminar_telefono(client, token, cliente_id, telefono_id):
    return client.delete(
        f"/api/clientes/{cliente_id}/telefonos/{telefono_id}",
        cookies={"access_token": token},
    )


def _agregar_cuit(client, token, cliente_id, cuit):
    return client.post(
        f"/api/clientes/{cliente_id}/cuits",
        json={"cuit": cuit},
        cookies={"access_token": token},
    )


def _eliminar_cuit(client, token, cliente_id, cuit_id):
    return client.delete(
        f"/api/clientes/{cliente_id}/cuits/{cuit_id}",
        cookies={"access_token": token},
    )


def _csv_bytes(filas: list[str]) -> bytes:
    return (_CSV_HEADER + "\n".join(filas)).encode("utf-8")


def _preview(client, token, csv_content: bytes):
    return client.post(
        "/api/clientes/importar/preview",
        files={"archivo": ("clientes.csv", csv_content, "text/csv")},
        cookies={"access_token": token},
    )


def _importar(client, token, csv_content: bytes):
    return client.post(
        "/api/clientes/importar",
        files={"archivo": ("clientes.csv", csv_content, "text/csv")},
        cookies={"access_token": token},
    )


# =============================================================================
# GET /api/clientes
# =============================================================================

def test_listar_devuelve_200(client, admin_token, cliente_test):
    resp = _listar(client, admin_token)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    assert "items" in data and "total" in data


def test_listar_campos_esperados(client, admin_token, cliente_test):
    resp = _listar(client, admin_token)
    assert resp.status_code == 200
    cliente = next((c for c in resp.json()["items"] if c["id"] == cliente_test["id"]), None)
    assert cliente is not None
    for campo in ("id", "codigo_cliente", "razon_social", "direccion", "activo", "creado_en"):
        assert campo in cliente, f"Falta '{campo}'"


def test_listar_sin_token_devuelve_401(client):
    assert client.get("/api/clientes").status_code == 401


def test_listar_solo_activos_excluye_inactivos(client, admin_token, cliente_test):
    _actualizar(client, admin_token, cliente_test["id"], activo=False)
    resp = _listar(client, admin_token, solo_activos=True)
    assert resp.status_code == 200
    ids = [c["id"] for c in resp.json()["items"]]
    assert cliente_test["id"] not in ids


# =============================================================================
# POST /api/clientes
# =============================================================================

def test_crear_cliente_devuelve_201(client, admin_token, limpiar_clientes_importados):
    resp = _crear(client, admin_token, "TESTIMPORT_CREAR", "Nuevo SA", "Av. Test 1")
    assert resp.status_code == 201
    body = resp.json()
    assert body["codigo_cliente"] == "TESTIMPORT_CREAR"
    assert body["razon_social"] == "Nuevo SA"
    assert body["activo"] is True


def test_crear_cliente_campos_esperados(client, admin_token, limpiar_clientes_importados):
    resp = _crear(client, admin_token, "TESTIMPORT_CAMPOS", "Campos SA")
    assert resp.status_code == 201
    for campo in ("id", "codigo_cliente", "razon_social", "direccion", "activo", "telefonos", "cuits"):
        assert campo in resp.json(), f"Falta '{campo}'"


def test_crear_cliente_codigo_duplicado_devuelve_409(client, admin_token, cliente_test):
    resp = _crear(client, admin_token, cliente_test["codigo_cliente"], "Duplicado SRL")
    assert resp.status_code == 409
    assert cliente_test["codigo_cliente"] in resp.json()["detail"]


def test_crear_cliente_sin_razon_social_devuelve_422(client, admin_token):
    resp = client.post(
        "/api/clientes",
        json={"codigo_cliente": "TESTIMPORT_422"},
        cookies={"access_token": admin_token},
    )
    assert resp.status_code == 422


def test_crear_cliente_sin_token_devuelve_401(client):
    resp = client.post("/api/clientes", json={"codigo_cliente": "X", "razon_social": "Y"})
    assert resp.status_code == 401


# =============================================================================
# GET /api/clientes/{id}
# =============================================================================

def test_obtener_cliente_devuelve_detalle(client, admin_token, cliente_test):
    resp = _obtener(client, admin_token, cliente_test["id"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == cliente_test["id"]
    assert "telefonos" in body
    assert "cuits" in body


def test_obtener_cliente_inexistente_devuelve_404(client, admin_token):
    resp = _obtener(client, admin_token, str(uuid.uuid4()))
    assert resp.status_code == 404


def test_obtener_cliente_sin_token_devuelve_401(client, cliente_test):
    assert client.get(f"/api/clientes/{cliente_test['id']}").status_code == 401


# =============================================================================
# PATCH /api/clientes/{id}
# =============================================================================

def test_actualizar_razon_social(client, admin_token, cliente_test):
    resp = _actualizar(client, admin_token, cliente_test["id"], razon_social="Actualizada SRL")
    assert resp.status_code == 200
    assert resp.json()["razon_social"] == "Actualizada SRL"


def test_actualizar_activo_false(client, admin_token, cliente_test):
    resp = _actualizar(client, admin_token, cliente_test["id"], activo=False)
    assert resp.status_code == 200
    assert resp.json()["activo"] is False


def test_actualizar_sin_campos_devuelve_400(client, admin_token, cliente_test):
    resp = _actualizar(client, admin_token, cliente_test["id"])
    assert resp.status_code == 400


def test_actualizar_cliente_inexistente_devuelve_404(client, admin_token):
    resp = _actualizar(client, admin_token, str(uuid.uuid4()), razon_social="X")
    assert resp.status_code == 404


def test_actualizar_sin_token_devuelve_401(client, cliente_test):
    resp = client.patch(f"/api/clientes/{cliente_test['id']}", json={"razon_social": "X"})
    assert resp.status_code == 401


# =============================================================================
# POST /api/clientes/{id}/telefonos
# =============================================================================

def test_agregar_telefono_devuelve_201(client, admin_token, cliente_test):
    resp = _agregar_telefono(client, admin_token, cliente_test["id"], "+5491100000001")
    assert resp.status_code == 201
    assert resp.json()["telefono"] == "+5491100000001"


def test_agregar_telefono_duplicado_devuelve_409(client, admin_token, cliente_test):
    _agregar_telefono(client, admin_token, cliente_test["id"], "+5491100000002")
    resp = _agregar_telefono(client, admin_token, cliente_test["id"], "+5491100000002")
    assert resp.status_code == 409


def test_agregar_telefono_aparece_en_detalle(client, admin_token, cliente_test):
    _agregar_telefono(client, admin_token, cliente_test["id"], "+5491100000003")
    detalle = _obtener(client, admin_token, cliente_test["id"]).json()
    telefonos = [t["telefono"] for t in detalle["telefonos"]]
    assert "+5491100000003" in telefonos


def test_agregar_telefono_sin_token_devuelve_401(client, cliente_test):
    resp = client.post(
        f"/api/clientes/{cliente_test['id']}/telefonos",
        json={"telefono": "+5491100000099"},
    )
    assert resp.status_code == 401


# =============================================================================
# DELETE /api/clientes/{id}/telefonos/{tid}
# =============================================================================

def test_eliminar_telefono_devuelve_204(client, admin_token, cliente_test):
    telefono_id = _agregar_telefono(
        client, admin_token, cliente_test["id"], "+5491100000004"
    ).json()["id"]
    resp = _eliminar_telefono(client, admin_token, cliente_test["id"], telefono_id)
    assert resp.status_code == 204


def test_eliminar_telefono_inexistente_devuelve_404(client, admin_token, cliente_test):
    resp = _eliminar_telefono(client, admin_token, cliente_test["id"], str(uuid.uuid4()))
    assert resp.status_code == 404


# =============================================================================
# POST /api/clientes/{id}/cuits — DELETE /api/clientes/{id}/cuits/{cid}
# =============================================================================

def test_agregar_cuit_devuelve_201(client, admin_token, cliente_test):
    resp = _agregar_cuit(client, admin_token, cliente_test["id"], "20111222333")
    assert resp.status_code == 201
    assert resp.json()["cuit"] == "20111222333"


def test_agregar_cuit_duplicado_devuelve_409(client, admin_token, cliente_test):
    _agregar_cuit(client, admin_token, cliente_test["id"], "20111222444")
    resp = _agregar_cuit(client, admin_token, cliente_test["id"], "20111222444")
    assert resp.status_code == 409


def test_eliminar_cuit_devuelve_204(client, admin_token, cliente_test):
    cuit_id = _agregar_cuit(client, admin_token, cliente_test["id"], "20111222555").json()["id"]
    assert _eliminar_cuit(client, admin_token, cliente_test["id"], cuit_id).status_code == 204


def test_eliminar_cuit_inexistente_devuelve_404(client, admin_token, cliente_test):
    resp = _eliminar_cuit(client, admin_token, cliente_test["id"], str(uuid.uuid4()))
    assert resp.status_code == 404


# =============================================================================
# POST /api/clientes/importar/preview
# =============================================================================

def test_preview_nuevos(client, admin_token, limpiar_clientes_importados):
    csv = _csv_bytes(["TESTIMPORT_P1,Nuevo Preview,,+5491100000010,20100000001"])
    resp = _preview(client, admin_token, csv)
    assert resp.status_code == 200
    body = resp.json()
    assert body["nuevos"] == 1
    assert body["con_cambios"] == 0
    assert body["sin_cambios"] == 0
    assert body["total_csv"] == 1
    assert body["filas_invalidas"] == 0


def test_preview_sin_cambios_cuando_csv_es_identico(client, admin_token, cliente_test):
    # CSV con los mismos datos que tiene el cliente_test en DB
    csv = _csv_bytes([f'{cliente_test["codigo_cliente"]},Cliente Test SA,"Corrientes 1234, CABA",,'])
    resp = _preview(client, admin_token, csv)
    assert resp.status_code == 200
    body = resp.json()
    assert body["sin_cambios"] == 1
    assert body["con_cambios"] == 0
    assert body["nuevos"] == 0


def test_preview_con_cambios_cuando_razon_social_difiere(client, admin_token, cliente_test):
    csv = _csv_bytes([f"{cliente_test['codigo_cliente']},Razon Social Modificada,,"])
    resp = _preview(client, admin_token, csv)
    assert resp.status_code == 200
    body = resp.json()
    assert body["con_cambios"] == 1
    assert body["sin_cambios"] == 0


def test_preview_con_cambios_cuando_csv_tiene_telefono_nuevo(client, admin_token, cliente_test):
    # cliente_test no tiene teléfonos — CSV con uno nuevo debe contar como con_cambios
    csv = _csv_bytes([f'{cliente_test["codigo_cliente"]},Cliente Test SA,"Corrientes 1234, CABA",+5491100000099,'])
    resp = _preview(client, admin_token, csv)
    assert resp.status_code == 200
    body = resp.json()
    assert body["con_cambios"] == 1
    assert body["sin_cambios"] == 0


def test_preview_con_cambios_cuando_csv_tiene_cuit_nuevo(client, admin_token, cliente_test):
    # cliente_test no tiene CUITs — CSV con uno nuevo debe contar como con_cambios
    csv = _csv_bytes([f'{cliente_test["codigo_cliente"]},Cliente Test SA,"Corrientes 1234, CABA",,20999999991'])
    resp = _preview(client, admin_token, csv)
    assert resp.status_code == 200
    body = resp.json()
    assert body["con_cambios"] == 1
    assert body["sin_cambios"] == 0


def test_preview_cuenta_filas_invalidas(client, admin_token):
    csv = _csv_bytes([
        "TESTIMPORT_OK,Valido,,",
        ",Sin codigo,,",     # fila inválida — sin codigo_cliente
        "TESTIMPORT_OK2,,",  # fila inválida — sin razon_social
    ])
    resp = _preview(client, admin_token, csv)
    assert resp.status_code == 200
    assert resp.json()["total_csv"] == 1
    assert resp.json()["filas_invalidas"] == 2


def test_preview_csv_vacio_devuelve_400(client, admin_token):
    csv = _CSV_HEADER.encode()
    resp = _preview(client, admin_token, csv)
    assert resp.status_code == 400


def test_preview_archivo_no_csv_devuelve_400(client, admin_token):
    resp = client.post(
        "/api/clientes/importar/preview",
        files={"archivo": ("datos.txt", b"codigo;razon", "text/plain")},
        cookies={"access_token": admin_token},
    )
    assert resp.status_code == 400


def test_preview_sin_token_devuelve_401(client):
    csv = _csv_bytes(["TESTIMPORT_AUTH,Test,,"])
    resp = client.post(
        "/api/clientes/importar/preview",
        files={"archivo": ("clientes.csv", csv, "text/csv")},
    )
    assert resp.status_code == 401


# =============================================================================
# POST /api/clientes/importar
# =============================================================================

def test_importar_inserta_nuevos(client, admin_token, limpiar_clientes_importados):
    csv = _csv_bytes([
        "TESTIMPORT_I1,Importado Uno,,+5491100000020,20200000001",
        "TESTIMPORT_I2,Importado Dos,Av. Corrientes 1,,",
    ])
    resp = _importar(client, admin_token, csv)
    assert resp.status_code == 200
    body = resp.json()
    assert body["insertados"] == 2
    assert body["actualizados"] == 0
    assert body["errores"] == []


def test_importar_actualiza_existentes(client, admin_token, cliente_test, limpiar_clientes_importados):
    csv = _csv_bytes([f"{cliente_test['codigo_cliente']},Razon Actualizada por Import,,"])
    resp = _importar(client, admin_token, csv)
    assert resp.status_code == 200
    assert resp.json()["actualizados"] == 1
    assert resp.json()["insertados"] == 0

    detalle = _obtener(client, admin_token, cliente_test["id"]).json()
    assert detalle["razon_social"] == "Razon Actualizada por Import"


def test_importar_sin_cambios_no_cuenta_como_actualizado(client, admin_token, limpiar_clientes_importados):
    csv = _csv_bytes(["TESTIMPORT_SC,Sin Cambios SRL,Av. Mayo 1234,,"])
    _importar(client, admin_token, csv)

    resp = _importar(client, admin_token, csv)
    assert resp.status_code == 200
    body = resp.json()
    assert body["insertados"] == 0
    assert body["actualizados"] == 0
    assert body["errores"] == []


def test_importar_agrega_telefonos_y_cuits(client, admin_token, limpiar_clientes_importados):
    csv = _csv_bytes(["TESTIMPORT_TC,Con Contacto,,+5491100000030,20300000001"])
    _importar(client, admin_token, csv)

    pool = db_conn.get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM clientes WHERE codigo_cliente = 'TESTIMPORT_TC'"
            )
            cliente_id = cur.fetchone()[0]
    finally:
        pool.putconn(conn)

    detalle = _obtener(client, admin_token, str(cliente_id)).json()
    assert any(t["telefono"] == "5491100000030" for t in detalle["telefonos"])
    assert any(c["cuit"] == "20300000001" for c in detalle["cuits"])


def test_importar_csv_vacio_devuelve_400(client, admin_token):
    resp = _importar(client, admin_token, _CSV_HEADER.encode())
    assert resp.status_code == 400


def test_importar_sin_token_devuelve_401(client):
    csv = _csv_bytes(["TESTIMPORT_AUTH2,Test,,"])
    resp = client.post(
        "/api/clientes/importar",
        files={"archivo": ("clientes.csv", csv, "text/csv")},
    )
    assert resp.status_code == 401


# =============================================================================
# GET /api/clientes/sin-actividad
# =============================================================================

def test_sin_actividad_devuelve_200(client, admin_token):
    resp = client.get(
        "/api/clientes/sin-actividad",
        cookies={"access_token": admin_token},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_sin_comprobantes_incluye_cliente_nuevo(client, admin_token, cliente_test):
    resp = client.get(
        "/api/clientes/sin-comprobantes",
        cookies={"access_token": admin_token},
    )
    assert resp.status_code == 200
    codigos = [c["codigo_cliente"] for c in resp.json()]
    assert cliente_test["codigo_cliente"] in codigos


def test_sin_actividad_sin_token_devuelve_401(client):
    assert client.get("/api/clientes/sin-actividad").status_code == 401
