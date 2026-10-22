"""
Cliente de Mercado Pago.

verificar_pago() devuelve (estado, mp_status_code).
  · 404 → REVISION_MANUAL (número encontrado pero MP no lo reconoce; operator revisa)
  · 200 approved → APROBADO / MONTO_ADULTERADO según comparación de monto
"""
import logging
import re
from datetime import datetime, timedelta, timezone

import httpx
from config import config
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

_logger = logging.getLogger(__name__)


def _es_reintentable(exc: BaseException) -> bool:
    """Reintenta errores de red y 5xx. Los 4xx no son transitorios — no se reintentan."""
    if isinstance(exc, httpx.RequestError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


class MpClient:
    _BASE_URL = "https://api.mercadopago.com"

    def __init__(self) -> None:
        self._headers = {"Authorization": f"Bearer {config.mp_access_token}"}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception(_es_reintentable),
        reraise=True,
    )
    async def _llamar_api_mp(self, numero_operacion: str) -> httpx.Response:
        # 404 es respuesta válida de negocio ("pago no existe") — no lanza excepción.
        async with httpx.AsyncClient() as client:
            respuesta_http = await client.get(
                f"{self._BASE_URL}/v1/payments/{numero_operacion}",
                headers=self._headers,
                timeout=30,
            )
            if respuesta_http.status_code == 404:
                return respuesta_http
            respuesta_http.raise_for_status()
            return respuesta_http

    async def verificar_pago(
        self,
        numero_operacion: str,
        monto_ocr: str | None,
        cuit_ocr: str | None,
    ) -> tuple[str, int | None]:
        if cuit_ocr is not None and not _cuits_coinciden(cuit_ocr, config.cuit_destinatario):
            return "ERROR_DESTINATARIO", None

        try:
            respuesta_http = await self._llamar_api_mp(numero_operacion)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise
            if e.response.status_code >= 500:
                # 500 persistente después de 3 reintentos: MP no puede procesar el número.
                # No es un error nuestro — el operador lo revisa manualmente.
                return "REVISION_MANUAL", e.response.status_code
            return "ERROR_MP", e.response.status_code
        except httpx.RequestError:
            return "ERROR_MP", None

        if respuesta_http.status_code == 404:
            return "REVISION_MANUAL", 404

        pago = respuesta_http.json()

        if pago.get("status") != "approved":
            return "PAGO_NO_ACREDITADO", respuesta_http.status_code

        if monto_ocr is not None:
            monto_mp = float(pago.get("transaction_amount", 0))
            monto_detectado = _parsear_monto(monto_ocr)
            # Tolerancia 1.0: cubre la pérdida de centavos por fuente decorativa de MP
            # (OCR lee "$8" en lugar de "$8,66" → diff máx ~$0.99).
            # Cualquier adulteración real implica una diferencia de al menos $1.
            if monto_detectado is not None and abs(monto_detectado - monto_mp) > 1.0:
                return "MONTO_ADULTERADO", respuesta_http.status_code

        return "APROBADO", respuesta_http.status_code

    async def buscar_pago_por_coelsa_id(
        self,
        coelsa_id: str,
        monto_ocr: str | None,
        fecha_ocr: str | None,
        cuit_ocr: str | None,
    ) -> tuple[str, int | None]:
        """
        Busca un pago por COELSA ID (e2e_id).

        MP no permite buscar por e2e_id directamente — filtramos por monto + fecha
        para acotar resultados, y luego el e2e_id actúa como validador exacto.
        """
        if cuit_ocr is not None and not _cuits_coinciden(cuit_ocr, config.cuit_destinatario):
            return "ERROR_DESTINATARIO", None

        params: dict = {
            "sort": "date_created",
            "criteria": "desc",
            "offset": 0,
            "limit": 50,
        }
        monto_decimal = _parsear_monto(monto_ocr) if monto_ocr else None
        if monto_decimal is not None:
            params["transaction_amount"] = monto_decimal
        if fecha_ocr:
            try:
                fecha_dt = datetime.strptime(fecha_ocr, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                params["begin_date"] = (fecha_dt - timedelta(days=2)).strftime("%Y-%m-%dT00:00:00.000Z")
                params["end_date"]   = (fecha_dt + timedelta(days=2)).strftime("%Y-%m-%dT23:59:59.000Z")
            except (ValueError, TypeError):
                pass

        if "transaction_amount" not in params and "begin_date" not in params:
            _logger.warning("buscar_pago_por_coelsa_id: sin monto ni fecha — REVISION_MANUAL")
            return "REVISION_MANUAL", None

        try:
            async with httpx.AsyncClient() as client:
                respuesta_http = await client.get(
                    f"{self._BASE_URL}/v1/payments/search",
                    headers=self._headers,
                    params=params,
                    timeout=30,
                )
                respuesta_http.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise
            _logger.error("MP search COELSA_ID HTTP %s: %s", e.response.status_code, e.response.text[:200])
            return "ERROR_MP", e.response.status_code
        except httpx.RequestError as e:
            _logger.error("MP search COELSA_ID red: %s", e)
            return "ERROR_MP", None

        resultados = respuesta_http.json().get("results", [])
        pago = next(
            (
                p for p in resultados
                if p.get("point_of_interaction", {})
                   .get("transaction_data", {})
                   .get("e2e_id") == coelsa_id
            ),
            None,
        )

        if pago is None:
            return "REVISION_MANUAL", respuesta_http.status_code

        if pago.get("status") != "approved":
            return "PAGO_NO_ACREDITADO", respuesta_http.status_code

        if monto_ocr is not None and monto_decimal is not None:
            monto_mp = float(pago.get("transaction_amount", 0))
            if abs(monto_decimal - monto_mp) > 1.0:
                return "MONTO_ADULTERADO", respuesta_http.status_code

        return "APROBADO", respuesta_http.status_code

    async def buscar_pago_por_monto_fecha(
        self,
        monto_ocr: str,
        fecha_ocr: str,
        cuit_ocr: str | None,
        cuit_remitente: str | None = None,
    ) -> tuple[str, int | None, str | None]:
        """
        Fuzzy match por monto + fecha ±2 días para comprobantes sin identificador trazable.

        Devuelve (estado, mp_status_code, pago_id_mp).
        pago_id_mp es el ID de pago de MP para usar como identificador_pago en DB.

        Desambiguación: si cuit_remitente está disponible, filtra los resultados por
        payer.identification.number para reducir falsos REVISION_MANUAL cuando hay
        varios pagos del mismo monto en el día.
        """
        if cuit_ocr is not None and not _cuits_coinciden(cuit_ocr, config.cuit_destinatario):
            return "ERROR_DESTINATARIO", None, None

        monto_decimal = _parsear_monto(monto_ocr)
        if monto_decimal is None:
            return "REVISION_MANUAL", None, None

        try:
            fecha_dt = datetime.strptime(fecha_ocr, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return "REVISION_MANUAL", None, None

        begin_date = (fecha_dt - timedelta(days=2)).strftime("%Y-%m-%dT00:00:00.000Z")
        end_date   = (fecha_dt + timedelta(days=2)).strftime("%Y-%m-%dT23:59:59.000Z")

        try:
            async with httpx.AsyncClient() as client:
                respuesta_http = await client.get(
                    f"{self._BASE_URL}/v1/payments/search",
                    headers=self._headers,
                    params={
                        "transaction_amount": monto_decimal,
                        "begin_date": begin_date,
                        "end_date": end_date,
                        "status": "approved",
                        "sort": "date_created",
                        "criteria": "desc",
                        "offset": 0,
                        "limit": 50,
                    },
                    timeout=30,
                )
                respuesta_http.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise
            _logger.error("MP search fuzzy HTTP %s: %s", e.response.status_code, e.response.text[:200])
            return "ERROR_MP", e.response.status_code, None
        except httpx.RequestError as e:
            _logger.error("MP search fuzzy red: %s", e)
            return "ERROR_MP", None, None

        resultados = respuesta_http.json().get("results", [])

        if cuit_remitente and len(resultados) > 1:
            solo_digitos = re.compile(r"[^0-9]")
            filtrados = [
                p for p in resultados
                if solo_digitos.sub("", str(
                    p.get("payer", {}).get("identification", {}).get("number", "")
                )) == cuit_remitente
            ]
            if filtrados:
                resultados = filtrados

        if len(resultados) != 1:
            return "REVISION_MANUAL", respuesta_http.status_code, None

        pago_id = str(resultados[0].get("id", ""))
        if not pago_id:
            return "REVISION_MANUAL", respuesta_http.status_code, None

        return "APROBADO", respuesta_http.status_code, pago_id


def _parsear_monto(monto_str: str) -> float | None:
    monto_normalizado = monto_str.replace("$", "").strip().replace(" ", "")

    if "." in monto_normalizado and "," in monto_normalizado:
        monto_normalizado = monto_normalizado.replace(".", "").replace(",", ".")
        try:
            return float(monto_normalizado)
        except ValueError:
            return None

    if "," in monto_normalizado:
        digitos_tras_coma = monto_normalizado.split(",")[-1]
        monto_normalizado = monto_normalizado.replace(",", ".") if len(digitos_tras_coma) == 2 else monto_normalizado.replace(",", "")
        try:
            return float(monto_normalizado)
        except ValueError:
            return None

    if "." in monto_normalizado:
        digitos_tras_punto = monto_normalizado.split(".")[-1]
        if len(digitos_tras_punto) != 2:
            monto_normalizado = monto_normalizado.replace(".", "")
        try:
            return float(monto_normalizado)
        except ValueError:
            return None

    try:
        return float(monto_normalizado)
    except ValueError:
        return None


def _cuits_coinciden(cuit_ocr: str, cuit_esperado: str) -> bool:
    solo_digitos = re.compile(r"[^0-9]")
    return solo_digitos.sub("", cuit_ocr) == solo_digitos.sub("", cuit_esperado)
