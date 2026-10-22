import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { listarAdmins, toggleActivoAdmin, type AdminResumen } from "@/api/admins"
import { obtenerMe } from "@/api/auth"

export default function Admins() {
  const [admins, setAdmins]         = useState<AdminResumen[]>([])
  const [miId, setMiId]             = useState<string | null>(null)
  const [error, setError]           = useState<string | null>(null)
  const [toggling, setToggling]     = useState<string | null>(null) // id del admin en proceso

  useEffect(() => {
    Promise.all([listarAdmins(), obtenerMe()])
      .then(([lista, yo]) => {
        setAdmins(lista)
        setMiId(yo.id)
      })
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : "No se pudo cargar la lista.")
      })
  }, [])

  async function handleToggle(admin: AdminResumen) {
    setToggling(admin.id)
    setError(null)
    try {
      const actualizado = await toggleActivoAdmin(admin.id, !admin.activo)
      setAdmins((prev) => prev.map((a) => (a.id === actualizado.id ? actualizado : a)))
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al actualizar el admin.")
    } finally {
      setToggling(null)
    }
  }

  return (
    <main className="max-w-2xl mx-auto px-4 sm:px-6 py-8 sm:py-12">
        <h2 className="text-lg font-semibold mb-6">Administradores</h2>

        {error && (
          <p className="text-sm text-destructive mb-4">{error}</p>
        )}

        {admins.length > 0 && (
          <div className="border rounded-lg divide-y">
            {admins.map((admin) => (
              <div key={admin.id} className="px-4 py-3 flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate">{admin.nombre}</p>
                  <p className="text-xs text-muted-foreground truncate">{admin.email}</p>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span
                    className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${
                      admin.activo
                        ? "bg-green-100 text-green-800 border-green-200"
                        : "bg-gray-100 text-gray-500 border-gray-200"
                    }`}
                  >
                    {admin.activo ? "Activo" : "Inactivo"}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={admin.id === miId || toggling === admin.id}
                    onClick={() => handleToggle(admin)}
                  >
                    {toggling === admin.id
                      ? "..."
                      : admin.activo ? "Desactivar" : "Activar"}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
    </main>
  )
}
