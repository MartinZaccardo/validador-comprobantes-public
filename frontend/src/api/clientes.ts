import { apiFetch } from "./client"
import { clearAdminInfo } from "./auth"

export interface ClienteResumen {
  id: string
  codigo_cliente: string
  razon_social: string
  direccion: string | null
  activo: boolean
  creado_en: string | null
}

export interface TelefonoItem {
  id: string
  telefono: string
}

export interface CuitItem {
  id: string
  cuit: string
}

export interface ClienteDetalle extends ClienteResumen {
  telefonos: TelefonoItem[]
  cuits: CuitItem[]
}

export interface PreviewImportacion {
  total_csv: number
  filas_invalidas: number
  nuevos: number
  con_cambios: number
  sin_cambios: number
}

export interface ResultadoImportacion {
  insertados: number
  actualizados: number
  errores: string[]
}

export interface ClientesPaginados {
  items: ClienteResumen[]
  total: number
}

export async function listarClientes(params: {
  q?: string
  soloActivos?: boolean
  page?: number
  pageSize?: number
} = {}): Promise<ClientesPaginados> {
  const qs = new URLSearchParams()
  if (params.q) qs.set("q", params.q)
  if (params.soloActivos) qs.set("solo_activos", "true")
  if (params.page) qs.set("page", String(params.page))
  if (params.pageSize) qs.set("page_size", String(params.pageSize))
  return apiFetch<ClientesPaginados>(`/api/clientes?${qs.toString()}`)
}

export async function crearCliente(data: {
  codigo_cliente: string
  razon_social: string
  direccion?: string
}): Promise<ClienteResumen> {
  return apiFetch<ClienteResumen>("/api/clientes", {
    method: "POST",
    body: JSON.stringify(data),
  })
}

export async function obtenerClienteDetalle(id: string): Promise<ClienteDetalle> {
  return apiFetch<ClienteDetalle>(`/api/clientes/${id}`)
}

export async function agregarTelefono(clienteId: string, telefono: string): Promise<TelefonoItem> {
  return apiFetch<TelefonoItem>(`/api/clientes/${clienteId}/telefonos`, {
    method: "POST",
    body: JSON.stringify({ telefono }),
  })
}

export async function eliminarTelefono(clienteId: string, telefonoId: string): Promise<void> {
  return apiFetch<void>(`/api/clientes/${clienteId}/telefonos/${telefonoId}`, { method: "DELETE" })
}

export async function agregarCuit(clienteId: string, cuit: string): Promise<CuitItem> {
  return apiFetch<CuitItem>(`/api/clientes/${clienteId}/cuits`, {
    method: "POST",
    body: JSON.stringify({ cuit }),
  })
}

export async function eliminarCuit(clienteId: string, cuitId: string): Promise<void> {
  return apiFetch<void>(`/api/clientes/${clienteId}/cuits/${cuitId}`, { method: "DELETE" })
}

export async function exportarClientes(): Promise<void> {
  const respuesta = await fetch("/api/clientes/exportar", { credentials: "include" })
  if (respuesta.status === 401) {
    clearAdminInfo()
    window.location.href = "/login"
    return
  }
  if (!respuesta.ok) throw new Error("Error al exportar los clientes.")
  const blob = await respuesta.blob()
  const url = URL.createObjectURL(blob)
  const enlace = document.createElement("a")
  enlace.href = url
  enlace.download = `clientes_${new Date().toISOString().slice(0, 10)}.csv`
  enlace.click()
  URL.revokeObjectURL(url)
}

export async function actualizarCliente(
  id: string,
  data: { razon_social?: string; direccion?: string },
): Promise<ClienteResumen> {
  return apiFetch<ClienteResumen>(`/api/clientes/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  })
}

export interface ClienteSinActividad {
  id: string
  codigo_cliente: string
  razon_social: string
  ultimo_comprobante: string | null
}

export async function listarClientesSinActividad(dias: number): Promise<ClienteSinActividad[]> {
  return apiFetch<ClienteSinActividad[]>(`/api/clientes/sin-actividad?dias=${dias}`)
}

export async function listarClientesSinComprobantes(): Promise<ClienteSinActividad[]> {
  return apiFetch<ClienteSinActividad[]>("/api/clientes/sin-comprobantes")
}

export interface ValidacionCliente {
  id: string
  estado: string
  identificador_pago: string | null
  monto_detectado: number | null
  procesado_en: string | null
  canal: string
  entidad_emisora: string | null
  codigo_cliente: string | null
  imagen_path: string | null
}

export async function buscarClientes(q: string): Promise<ClienteResumen[]> {
  return apiFetch<ClienteResumen[]>(`/api/clientes/buscar?q=${encodeURIComponent(q)}`)
}

export async function listarValidacionesDeCliente(clienteId: string): Promise<ValidacionCliente[]> {
  return apiFetch<ValidacionCliente[]>(`/api/clientes/${clienteId}/validaciones`)
}

export async function toggleActivoCliente(id: string, activo: boolean): Promise<ClienteResumen> {
  return apiFetch<ClienteResumen>(`/api/clientes/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ activo }),
  })
}

async function _fetchMultipart<T>(path: string, archivo: File): Promise<T> {
  const form = new FormData()
  form.append("archivo", archivo)
  const respuesta = await fetch(path, { method: "POST", credentials: "include", body: form })
  if (respuesta.status === 401) {
    clearAdminInfo()
    window.location.href = "/login"
    throw new Error("Sesión expirada.")
  }
  if (!respuesta.ok) {
    const json = await respuesta.json().catch(() => ({}))
    throw new Error(typeof json?.detail === "string" ? json.detail : "Error en la solicitud.")
  }
  return respuesta.json() as Promise<T>
}

export async function previewImportacion(archivo: File): Promise<PreviewImportacion> {
  return _fetchMultipart<PreviewImportacion>("/api/clientes/importar/preview", archivo)
}

// El upload de archivos usa FormData — no puede pasar por apiFetch porque
// el browser necesita setear Content-Type con el boundary automáticamente.
export async function importarClientes(archivo: File): Promise<ResultadoImportacion> {
  return _fetchMultipart<ResultadoImportacion>("/api/clientes/importar", archivo)
}
