/**
 * API de análisis manual de un comprobante individual.
 *
 * Por qué NO usamos apiFetch() de client.ts:
 *   apiFetch() pone "Content-Type: application/json" en los headers.
 *   Para un upload de archivo (FormData), el Content-Type tiene que ser
 *   "multipart/form-data; boundary=..." — el browser lo genera automáticamente
 *   si NO especificamos Content-Type. Si lo sobreescribimos, el servidor
 *   no puede encontrar el boundary y falla al parsear el archivo.
 *   Por eso construimos el fetch manualmente.
 *   La cookie httpOnly se adjunta automáticamente con credentials: "include".
 */
import { clearAdminInfo } from "./auth";

export interface ResultadoAnalisis {
  id: string;
  estado: string;
  canal: string;
  codigo_cliente: string;
  identificador_pago: string | null;
  monto_detectado: number | null;
  cuit_destinatario_detectado: string | null;
  es_comprobante_valido: boolean;
  mp_status_code: number | null;
  imagen_path: string | null;
  procesado_en: string | null;
  error: string | null;
  creado_por_nombre: string | null;
  observaciones: string | null;
  estado_inicial: string | null;
  entidad_emisora: string | null;
}

export async function analizarImagen(
  archivo: File,
  codigoCliente: string,
  signal?: AbortSignal,
): Promise<ResultadoAnalisis> {
  const formData = new FormData();
  formData.append("archivo", archivo);
  formData.append("codigo_cliente", codigoCliente);

  const respuesta = await fetch("/api/analizar", {
    method: "POST",
    // Sin Content-Type — el browser lo genera con el boundary correcto para FormData
    // Sin Authorization — la cookie httpOnly se adjunta automáticamente
    body: formData,
    signal,
    credentials: "include",
  });

  if (respuesta.status === 401) {
    clearAdminInfo();
    window.location.href = "/login";
    throw new Error("Sesión expirada");
  }

  if (!respuesta.ok) {
    const MENSAJES: Record<number, string> = {
      413: "La imagen es demasiado grande. Máximo 10 MB.",
      422: "Datos inválidos. Verificá el código de cliente y el archivo.",
      500: "Error interno del servidor. Si el problema persiste, contactá soporte.",
      502: "El servidor no está disponible en este momento. Intentá de nuevo en unos minutos.",
      503: "Servicio no disponible. Intentá de nuevo en unos minutos.",
    };
    throw new Error(
      MENSAJES[respuesta.status] ??
        "Ocurrió un error inesperado. Intentá de nuevo.",
    );
  }

  return respuesta.json() as Promise<ResultadoAnalisis>;
}
