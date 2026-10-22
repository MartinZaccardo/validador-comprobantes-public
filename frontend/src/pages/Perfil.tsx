import { useState, useEffect } from "react"
import { Link } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { obtenerMe, actualizarPerfil, logout, type AdminInfo } from "@/api/auth"
import { ChevronRightIcon } from "@/components/icons"

export default function Perfil() {
  const [admin, setAdmin]           = useState<AdminInfo | null>(null)
  const [error, setError]           = useState<string | null>(null)
  const [telefono, setTelefono]     = useState("")
  const [guardando, setGuardando]   = useState(false)
  const [guardadoOk, setGuardadoOk] = useState(false)

  useEffect(() => {
    obtenerMe()
      .then((a) => {
        setAdmin(a)
        setTelefono(a.telefono ?? "")
      })
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : "No se pudo cargar el perfil.")
      })
  }, [])

  async function handleGuardarTelefono() {
    if (!admin) return
    const telefonoLimpio = telefono.trim() || null
    if (telefonoLimpio === (admin.telefono ?? null)) return

    setGuardando(true)
    setGuardadoOk(false)
    setError(null)
    try {
      const actualizado = await actualizarPerfil({ telefono: telefonoLimpio })
      setAdmin(actualizado)
      setTelefono(actualizado.telefono ?? "")
      setGuardadoOk(true)
      setTimeout(() => setGuardadoOk(false), 2000)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al guardar el teléfono.")
    } finally {
      setGuardando(false)
    }
  }

  const telefonoModificado = admin !== null && telefono.trim() !== (admin.telefono ?? "")

  return (
    <main className="max-w-md mx-auto px-4 sm:px-6 py-8 sm:py-12">
        <h2 className="text-lg font-semibold mb-6">Mi perfil</h2>

        {error && (
          <p className="text-sm text-destructive mb-4">{error}</p>
        )}

        {admin && (
          <>
            <div className="border rounded-lg divide-y">
              <div className="px-4 py-3 flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Nombre</span>
                <span className="text-sm font-medium">{admin.nombre}</span>
              </div>
              <div className="px-4 py-3 flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Email</span>
                <span className="text-sm font-medium">{admin.email}</span>
              </div>
              <div className="px-4 py-3 flex items-center justify-between gap-4">
                <span className="text-sm text-muted-foreground shrink-0">Teléfono</span>
                <div className="flex items-center gap-2">
                  <input
                    type="tel"
                    value={telefono}
                    onChange={(e) => setTelefono(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleGuardarTelefono()}
                    placeholder="Sin teléfono"
                    disabled={guardando}
                    className="h-8 w-44 rounded-md border border-input bg-background px-2 text-sm
                               placeholder:text-muted-foreground focus-visible:outline-none
                               focus-visible:ring-2 focus-visible:ring-ring
                               disabled:opacity-50 text-right"
                  />
                  {telefonoModificado && (
                    <Button size="sm" onClick={handleGuardarTelefono} disabled={guardando}>
                      {guardando ? "Guardando..." : "Guardar"}
                    </Button>
                  )}
                  {guardadoOk && !telefonoModificado && (
                    <span className="text-xs text-green-600">Guardado</span>
                  )}
                </div>
              </div>
            </div>

            <div className="mt-8 flex items-center gap-4">
              <Button variant="destructive" onClick={() => void logout()}>
                Cerrar sesión
              </Button>
              {admin.es_superadmin && (
                <Link
                  to="/admins"
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  <span className="flex items-center gap-1">
                    Gestionar admins
                    <ChevronRightIcon />
                  </span>
                </Link>
              )}
            </div>
          </>
        )}
    </main>
  )
}
