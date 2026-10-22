import type { EstadoValidacion } from "@/api/validaciones"

export const ESTADOS_ORDEN: EstadoValidacion[] = [
  "APROBADO",
  "DUPLICADO",
  "MONTO_ADULTERADO",
  "PAGO_NO_ACREDITADO",
  "REVISION_MANUAL",
  "NUMERO_OP_NO_ENCONTRADO",
  "ERROR_DESTINATARIO",
  "IMAGEN_INVALIDA",
  "ERROR_MP",
]

export const LABEL_ESTADO: Record<EstadoValidacion, string> = {
  APROBADO:                "Aprobado",
  DUPLICADO:               "Duplicado",
  MONTO_ADULTERADO:        "Monto adulterado",
  PAGO_NO_ACREDITADO:      "Pago no acreditado",
  REVISION_MANUAL:         "Revisión manual",
  NUMERO_OP_NO_ENCONTRADO: "N° op. no encontrado",
  ERROR_DESTINATARIO:      "Error destinatario",
  IMAGEN_INVALIDA:         "Imagen inválida",
  ERROR_MP:                "Error MP",
}

export const COLORES_ESTADO: Record<EstadoValidacion, string> = {
  APROBADO:                "bg-green-100 text-green-800 border-green-200",
  DUPLICADO:               "bg-yellow-100 text-yellow-800 border-yellow-200",
  MONTO_ADULTERADO:        "bg-orange-100 text-orange-800 border-orange-200",
  PAGO_NO_ACREDITADO:      "bg-sky-100 text-sky-800 border-sky-200",
  REVISION_MANUAL:         "bg-amber-100 text-amber-800 border-amber-200",
  NUMERO_OP_NO_ENCONTRADO: "bg-purple-100 text-purple-800 border-purple-200",
  ERROR_DESTINATARIO:      "bg-red-100 text-red-800 border-red-200",
  IMAGEN_INVALIDA:         "bg-gray-100 text-gray-500 border-gray-200",
  ERROR_MP:                "bg-red-100 text-red-800 border-red-200",
}

export const LABEL_CANAL: Record<string, string> = {
  MANUAL:   "Manual",
  WhatsApp: "WhatsApp",
}

export const COLORES_CANAL: Record<string, string> = {
  MANUAL:   "bg-violet-100 text-violet-700 border-violet-200",
  WhatsApp: "bg-green-100 text-green-700 border-green-200",
}

export function formatearFecha(iso: string | null): string {
  if (!iso) return "—"
  return new Date(iso).toLocaleString("es-AR", {
    dateStyle: "short",
    timeStyle: "short",
  })
}

export function formatearMonto(monto: number | null): string {
  if (monto === null) return "—"
  return new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency: "ARS",
    maximumFractionDigits: 2,
  }).format(monto)
}
