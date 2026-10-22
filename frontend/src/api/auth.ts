/**
 * Funciones de autenticación.
 *
 * El JWT viaja como cookie httpOnly — JavaScript nunca puede leerlo.
 * Esto elimina el vector de robo de token por XSS.
 *
 * En localStorage guardamos solo AdminInfo (sin secretos) como hint de UI:
 * sirve para saber si mostrar el dashboard o redirigir a /login en el render
 * inicial, sin tocar el servidor. Si la cookie expira pero el hint sigue,
 * el primer request 401 lo limpia y redirige.
 */

import { apiFetch } from "./client"

const ADMIN_INFO_KEY = "admin_info"

// ---------------------------------------------------------------------------
// Tipos
// ---------------------------------------------------------------------------

export interface AdminInfo {
  id: string
  email: string
  nombre: string
  es_superadmin: boolean
  telefono: string | null
}

export interface LoginResponse {
  admin: AdminInfo
}

// ---------------------------------------------------------------------------
// Gestión del hint de sesión en localStorage
// ---------------------------------------------------------------------------

export function getAdminInfo(): AdminInfo | null {
  const raw = localStorage.getItem(ADMIN_INFO_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as AdminInfo
  } catch {
    return null
  }
}

export function setAdminInfo(admin: AdminInfo): void {
  localStorage.setItem(ADMIN_INFO_KEY, JSON.stringify(admin))
}

export function clearAdminInfo(): void {
  localStorage.removeItem(ADMIN_INFO_KEY)
}

export function estaAutenticado(): boolean {
  return getAdminInfo() !== null
}

// ---------------------------------------------------------------------------
// Funciones de API
// ---------------------------------------------------------------------------

export async function login(email: string, password: string): Promise<LoginResponse> {
  const respuesta = await fetch("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
    credentials: "include",  // Necesario para que el browser almacene la cookie httpOnly
  })

  if (!respuesta.ok) {
    const cuerpo = await respuesta.json().catch(() => ({ detail: "Error desconocido" }))
    throw new Error(cuerpo.detail ?? `Error ${respuesta.status}`)
  }

  const datos = (await respuesta.json()) as LoginResponse
  setAdminInfo(datos.admin)
  return datos
}

export async function logout(): Promise<void> {
  try {
    // Le pide al servidor que borre la cookie httpOnly (JS no puede hacerlo directamente)
    await fetch("/auth/logout", {
      method: "POST",
      credentials: "include",
    })
  } catch {
    // Si el request falla, igual limpiamos el estado local y redirigimos
  }
  clearAdminInfo()
  window.location.href = "/login"
}

export async function obtenerMe(): Promise<AdminInfo> {
  return apiFetch<AdminInfo>("/auth/me")
}

export async function actualizarPerfil(
  datos: { telefono?: string | null }
): Promise<AdminInfo> {
  return apiFetch<AdminInfo>("/auth/me", {
    method: "PATCH",
    body: JSON.stringify(datos),
  })
}
