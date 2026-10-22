"""
Tests de security headers.

Verifica que el middleware agrega los 5 headers de seguridad a todas
las respuestas. Los testeamos contra /health (no requiere auth) y contra
un endpoint protegido para confirmar que aplica en ambos casos.
"""

_HEADERS_ESPERADOS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "SAMEORIGIN",
    "referrer-policy": "strict-origin-when-cross-origin",
    "strict-transport-security": "max-age=31536000",
    "server": "",
}


def test_security_headers_en_endpoint_publico(client):
    """Los headers aparecen en respuestas sin auth (/health)."""
    resp = client.get("/health")
    assert resp.status_code == 200

    for header, valor in _HEADERS_ESPERADOS.items():
        assert header in resp.headers, f"Falta el header '{header}'"
        assert resp.headers[header] == valor, (
            f"{header}: esperado '{valor}', recibido '{resp.headers[header]}'"
        )


def test_security_headers_en_endpoint_protegido(client, admin_token):
    """Los headers aparecen también en respuestas con auth."""
    resp = client.get(
        "/auth/me",
        cookies={"access_token": admin_token},
    )
    assert resp.status_code == 200

    for header in _HEADERS_ESPERADOS:
        assert header in resp.headers, f"Falta el header '{header}' en endpoint protegido"


def test_security_headers_en_respuesta_de_error(client):
    """Los headers aparecen incluso en respuestas de error (401)."""
    resp = client.get("/auth/me")
    assert resp.status_code == 401

    for header in _HEADERS_ESPERADOS:
        assert header in resp.headers, f"Falta el header '{header}' en respuesta de error"


def test_content_security_policy(client):
    """CSP presente y contiene las directivas críticas."""
    resp = client.get("/health")
    assert "content-security-policy" in resp.headers, "Falta el header Content-Security-Policy"

    csp = resp.headers["content-security-policy"]
    directivas_criticas = {
        "default-src 'self'": "catch-all restrictivo",
        "script-src 'self'": "bloquea scripts externos (XSS)",
        "object-src 'none'": "bloquea plugins Flash/Java",
        "frame-ancestors 'none'": "bloquea embedding en iframes (clickjacking)",
        "base-uri 'self'": "bloquea base tag injection",
        "form-action 'self'": "bloquea exfiltración via formularios",
    }
    for directiva, descripcion in directivas_criticas.items():
        assert directiva in csp, f"Falta directiva CSP '{directiva}' ({descripcion})"
