import { apiFetch } from "./client";
import { clearAdminInfo } from "./auth";

// ---------------------------------------------------------------------------
// Tipos
// ---------------------------------------------------------------------------

export type EstadoValidacion =
  | "APROBADO"
  | "DUPLICADO"
  | "MONTO_ADULTERADO"
  | "PAGO_NO_ACREDITADO"
  | "REVISION_MANUAL"
  | "NUMERO_OP_NO_ENCONTRADO"
  | "ERROR_DESTINATARIO"
  | "IMAGEN_INVALIDA"
  | "ERROR_MP";

export type CanalValidacion = "MANUAL" | "WhatsApp";

export interface Validacion {
  id: string;
  run_id: string | null; // null para canal='MANUAL'
  respuesta_id: number | null; // null para canal='MANUAL'
  codigo_cliente: string | null;
  codigo_vendedor: string | null;
  canal: CanalValidacion;
  estado: EstadoValidacion;
  identificador_pago: string | null;
  monto_detectado: number | null;
  cuit_destinatario_detectado: string | null;
  es_comprobante_valido: boolean | null;
  mp_status_code: number | null;
  error: string | null;
  procesado_en: string | null; // ISO 8601
  fecha_modificacion: string | null; // ISO 8601 — se rellena en ediciones manuales
  modificado_por_nombre: string | null; // admin que hizo el último cambio
  creado_por_nombre: string | null; // admin que subió el comprobante (solo canal='MANUAL')
  imagen_path: string | null; // ruta relativa del archivo (solo canal='MANUAL')
  observaciones: string | null; // texto libre del admin sobre el comprobante
  estado_inicial: string | null; // estado que determinó el sistema al procesar
  entidad_emisora: string | null; // banco/billetera detectado por OCR ("MERCADO_PAGO", "GALICIA", etc.)
}

// ---------------------------------------------------------------------------
// Funciones de API
// ---------------------------------------------------------------------------

export interface FiltrosValidaciones {
  estado?: EstadoValidacion;
  canal?: CanalValidacion;
  fecha_desde?: string; // YYYY-MM-DD — procesado_en
  fecha_hasta?: string; // YYYY-MM-DD — procesado_en
  fecha_mod_desde?: string; // YYYY-MM-DD — fecha_modificacion
  fecha_mod_hasta?: string; // YYYY-MM-DD — fecha_modificacion
  codigo_cliente?: string;
  numero_operacion?: string;
  usuario?: string;
  entidad_emisora?: string;
  limit?: number;
  offset?: number;
}

export interface Metricas {
  total: number;
  por_estado: Partial<Record<EstadoValidacion, number>>;
  por_canal: Partial<Record<CanalValidacion, number>>;
  por_banco: Record<string, number>;
}

export async function listarValidaciones(
  filtros: FiltrosValidaciones = {},
): Promise<Validacion[]> {
  const params = new URLSearchParams();
  if (filtros.estado) params.set("estado", filtros.estado);
  if (filtros.canal) params.set("canal", filtros.canal);
  if (filtros.fecha_desde) params.set("fecha_desde", filtros.fecha_desde);
  if (filtros.fecha_hasta) params.set("fecha_hasta", filtros.fecha_hasta);
  if (filtros.fecha_mod_desde)
    params.set("fecha_mod_desde", filtros.fecha_mod_desde);
  if (filtros.fecha_mod_hasta)
    params.set("fecha_mod_hasta", filtros.fecha_mod_hasta);
  if (filtros.codigo_cliente)
    params.set("codigo_cliente", filtros.codigo_cliente);
  if (filtros.numero_operacion)
    params.set("numero_operacion", filtros.numero_operacion);
  if (filtros.usuario) params.set("usuario", filtros.usuario);
  if (filtros.entidad_emisora) params.set("entidad_emisora", filtros.entidad_emisora);
  if (filtros.limit) params.set("limit", String(filtros.limit));
  if (filtros.offset) params.set("offset", String(filtros.offset));

  const query = params.toString();
  return apiFetch<Validacion[]>(`/api/validaciones${query ? `?${query}` : ""}`);
}

export async function obtenerMetricas(
  fecha_desde?: string,
  fecha_hasta?: string,
): Promise<Metricas> {
  const params = new URLSearchParams();
  if (fecha_desde) params.set("fecha_desde", fecha_desde);
  if (fecha_hasta) params.set("fecha_hasta", fecha_hasta);
  const query = params.toString();
  return apiFetch<Metricas>(`/api/metricas${query ? `?${query}` : ""}`);
}

export async function editarValidacion(
  id: string,
  cambios: {
    numero_operacion?: string;
    estado?: string;
    observaciones?: string;
  },
): Promise<Validacion> {
  return apiFetch<Validacion>(`/api/validaciones/${id}`, {
    method: "PATCH",
    body: JSON.stringify(cambios),
  });
}

export async function reemplazarImagen(
  id: string,
  archivo: File,
): Promise<Validacion> {
  const formData = new FormData();
  formData.append("imagen", archivo);
  const respuesta = await fetch(`/api/validaciones/${id}/imagen`, {
    method: "PATCH",
    // Sin Content-Type — el browser lo genera con el boundary correcto para FormData
    body: formData,
    credentials: "include",
  });
  if (respuesta.status === 401) {
    clearAdminInfo();
    window.location.href = "/login";
    throw new Error("Sesión expirada");
  }
  if (!respuesta.ok) {
    const detalle = await respuesta.json().catch(() => ({}));
    throw new Error(detalle?.detail ?? "Error al reemplazar la imagen");
  }
  return respuesta.json();
}

export async function eliminarValidacion(id: string): Promise<void> {
  await apiFetch<void>(`/api/validaciones/${id}`, { method: "DELETE" });
}

export async function listarBancos(): Promise<string[]> {
  return apiFetch<string[]>("/api/validaciones/bancos");
}

export async function reverificarValidacion(
  validacionId: string,
  numeroCorregido: string,
): Promise<Validacion> {
  return apiFetch<Validacion>(`/api/validaciones/${validacionId}/reverificar`, {
    method: "POST",
    body: JSON.stringify({ numero_operacion: numeroCorregido }),
  });
}
