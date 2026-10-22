import { apiFetch } from "./client"

export interface AdminResumen {
  id: string
  nombre: string
  email: string
  activo: boolean
  creado_en: string | null
}

export async function listarAdmins(): Promise<AdminResumen[]> {
  return apiFetch<AdminResumen[]>("/api/admins")
}

export async function toggleActivoAdmin(id: string, activo: boolean): Promise<AdminResumen> {
  return apiFetch<AdminResumen>(`/api/admins/${id}/activo`, {
    method: "PATCH",
    body: JSON.stringify({ activo }),
  })
}
