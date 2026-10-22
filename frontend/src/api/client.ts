/**
 * Base HTTP client con autenticación por cookie httpOnly.
 *
 * El JWT viaja automáticamente en cada request como cookie httpOnly —
 * no hay que leerlo ni agregarlo manualmente. credentials: "include"
 * es lo que le indica al browser que debe adjuntar las cookies.
 *
 * Comportamiento en 401:
 *   Limpia el hint de sesión de localStorage y redirige a /login.
 *   Cubre tokens expirados y sesiones revocadas (admin desactivado).
 */
import { clearAdminInfo } from "./auth"

const MENSAJES_HTTP: Record<number, string> = {
  400: "Solicitud inválida. Revisá los datos ingresados.",
  403: "No tenés permiso para realizar esta acción.",
  404: "No se encontró el recurso solicitado.",
  409: "El recurso ya existe o hay un conflicto.",
  500: "Error interno del servidor. Si el problema persiste, contactá soporte.",
  502: "El servidor no está disponible en este momento. Intentá de nuevo en unos minutos.",
  503: "Servicio no disponible. Intentá de nuevo en unos minutos.",
  504: "El servidor tardó demasiado en responder. Intentá de nuevo.",
}

// Para 409 y 422, FastAPI manda un detail en JSON con info útil para el operador.
// Para el resto, el body es HTML o stack trace — no se muestra al usuario.
async function mensajeDeError(respuesta: Response): Promise<string> {
  if (respuesta.status === 409 || respuesta.status === 422) {
    try {
      const json = await respuesta.json()
      if (typeof json?.detail === "string") return json.detail
      if (Array.isArray(json?.detail)) {
        const primer_error = json.detail[0]
        if (primer_error?.msg) return `Datos inválidos: ${primer_error.msg}`
      }
    } catch {
      // body no es JSON válido — caemos al mensaje genérico
    }
    if (respuesta.status === 422) return "Datos inválidos. Revisá los campos obligatorios."
  }

  return MENSAJES_HTTP[respuesta.status] ?? "Ocurrió un error inesperado. Intentá de nuevo."
}

/**
 * Wrapper sobre fetch con cookie httpOnly automática y manejo de errores HTTP.
 * Lanza un Error si el servidor responde con error.
 */
export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const respuesta = await fetch(path, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      // options.headers al final para que el caller pueda sobreescribir
      ...options.headers,
    },
  })

  if (respuesta.status === 401) {
    // Cookie ausente, expirada o admin desactivado — forzar re-login
    clearAdminInfo()
    window.location.href = "/login"
    throw new Error("Sesión expirada. Redirigiendo a login...")
  }

  if (!respuesta.ok) {
    throw new Error(await mensajeDeError(respuesta))
  }

  // 204 No Content y similares no tienen cuerpo
  if (respuesta.status === 204) return undefined as T
  return respuesta.json() as Promise<T>
}
