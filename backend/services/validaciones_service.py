"""
Lógica de negocio de validaciones individuales.

Los routers delegan acá. Este módulo no importa FastAPI.
"""
import psycopg2.pool
from db import queries_validaciones
from db.base import q
from exceptions.exceptions import EstadoNoReverificable, ValidacionNoEncontrada

from services.mp_client import MpClient

_ESTADOS_REVERIFICABLES = {"REVISION_MANUAL", "NUMERO_OP_NO_ENCONTRADO"}


class ValidacionesService:
    def __init__(self, pool: psycopg2.pool.ThreadedConnectionPool) -> None:
        self.pool = pool

    async def reverificar(
        self,
        tenant_id: str,
        validacion_id: str,
        numero_operacion: str,
    ) -> dict:
        validacion = await q(queries_validaciones.obtener_validacion_por_id, self.pool, validacion_id, tenant_id)
        if validacion is None:
            raise ValidacionNoEncontrada()

        if validacion["estado"] not in _ESTADOS_REVERIFICABLES:
            raise EstadoNoReverificable(validacion["estado"])

        monto_str: str | None = (
            str(validacion["monto_detectado"]) if validacion["monto_detectado"] is not None else None
        )

        cliente_mp = MpClient()
        nuevo_estado, mp_status_code = await cliente_mp.verificar_pago(
            numero_operacion=numero_operacion,
            monto_ocr=monto_str,
            cuit_ocr=validacion["cuit_destinatario_detectado"],
        )

        return await q(
            queries_validaciones.actualizar_validacion_reverificada,
            self.pool,
            validacion_id,
            tenant_id,
            numero_operacion,
            nuevo_estado,
            mp_status_code,
        )

    async def editar(
        self,
        tenant_id: str,
        validacion_id: str,
        numero_operacion: str | None,
        estado: str | None,
        observaciones: str | None,
        admin_id: str,
    ) -> dict:
        validacion = await q(queries_validaciones.obtener_validacion_por_id, self.pool, validacion_id, tenant_id)
        if validacion is None:
            raise ValidacionNoEncontrada()

        nuevo_numero = numero_operacion if numero_operacion is not None else validacion["identificador_pago"]
        nuevo_estado = estado if estado is not None else validacion["estado"]
        actualizar_observaciones = observaciones is not None

        actualizada = await q(
            queries_validaciones.actualizar_validacion_manual,
            self.pool,
            validacion_id,
            tenant_id,
            nuevo_numero,
            nuevo_estado,
            admin_id,
            observaciones=observaciones,
            actualizar_observaciones=actualizar_observaciones,
        )

        if nuevo_numero != validacion["identificador_pago"]:
            await q(
                queries_validaciones.guardar_auditoria,
                self.pool, admin_id, validacion_id,
                "numero_operacion",
                validacion["identificador_pago"],
                nuevo_numero or "",
            )

        if nuevo_estado != validacion["estado"]:
            await q(
                queries_validaciones.guardar_auditoria,
                self.pool, admin_id, validacion_id,
                "estado",
                validacion["estado"],
                nuevo_estado,
            )

        if actualizar_observaciones and observaciones != validacion.get("observaciones"):
            await q(
                queries_validaciones.guardar_auditoria,
                self.pool, admin_id, validacion_id,
                "observaciones",
                validacion.get("observaciones") or "",
                observaciones or "",
            )

        return actualizada
