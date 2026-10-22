import { useState, useEffect } from "react"
import { listarClientesSinComprobantes, type ClienteSinActividad } from "@/api/clientes"

export default function TabSinComprobantes() {
  const [clientes, setClientes] = useState<ClienteSinActividad[]>([])
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelado = false
    async function fetchear() {
      setCargando(true)
      setError(null)
      try {
        const resultado = await listarClientesSinComprobantes()
        if (!cancelado) setClientes(resultado)
      } catch (e: unknown) {
        if (!cancelado) setError(e instanceof Error ? e.message : "No se pudo cargar.")
      } finally {
        if (!cancelado) setCargando(false)
      }
    }
    fetchear()
    return () => { cancelado = true }
  }, [])

  if (cargando) {
    return <p className="text-sm text-muted-foreground text-center py-12">Cargando...</p>
  }
  if (error) {
    return <p className="text-sm text-destructive">{error}</p>
  }
  if (clientes.length === 0) {
    return (
      <p className="text-sm text-muted-foreground text-center py-12">
        Todos los clientes enviaron al menos un comprobante.
      </p>
    )
  }

  return (
    <>
      {/* Mobile: lista simple */}
      <div className="flex flex-col divide-y border rounded-lg md:hidden">
        {clientes.map((c) => (
          <div key={c.id} className="px-4 py-3">
            <p className="text-sm font-medium">{c.razon_social}</p>
            <p className="text-xs text-muted-foreground font-mono mt-0.5">{c.codigo_cliente}</p>
          </div>
        ))}
      </div>

      {/* Desktop: tabla */}
      <div className="hidden md:block border rounded-lg overflow-x-auto">
        <table className="w-full min-w-[480px] text-sm">
          <thead className="bg-muted/50">
            <tr>
              <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Código</th>
              <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Razón social</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {clientes.map((c) => (
              <tr key={c.id} className="hover:bg-muted/20 transition-colors">
                <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{c.codigo_cliente}</td>
                <td className="px-4 py-3 font-medium">{c.razon_social}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
