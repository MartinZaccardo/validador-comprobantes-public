import { useState, useEffect } from "react"
import { listarClientesSinActividad, type ClienteSinActividad } from "@/api/clientes"
import { formatearFecha } from "@/lib/validaciones-ui"

export default function TabSinActividad() {
  const [dias, setDias] = useState(7)
  const [clientes, setClientes] = useState<ClienteSinActividad[]>([])
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelado = false
    async function fetchear() {
      setCargando(true)
      setError(null)
      try {
        const resultado = await listarClientesSinActividad(dias)
        if (!cancelado) setClientes(resultado)
      } catch (e: unknown) {
        if (!cancelado) setError(e instanceof Error ? e.message : "No se pudo cargar.")
      } finally {
        if (!cancelado) setCargando(false)
      }
    }
    fetchear()
    return () => { cancelado = true }
  }, [dias])

  return (
    <div>
      <div className="flex items-center gap-2 mb-4 text-sm">
        <span className="text-muted-foreground">Sin comprobantes hace más de</span>
        {[7, 14, 30].map((d) => (
          <button
            key={d}
            onClick={() => setDias(d)}
            className={`px-2.5 py-1 rounded-md border text-xs font-medium transition-colors ${
              dias === d
                ? "bg-foreground text-background border-foreground"
                : "border-border text-muted-foreground hover:text-foreground"
            }`}
          >
            {d} días
          </button>
        ))}
      </div>

      {cargando ? (
        <p className="text-sm text-muted-foreground text-center py-12">Cargando...</p>
      ) : error ? (
        <p className="text-sm text-destructive">{error}</p>
      ) : clientes.length === 0 ? (
        <p className="text-sm text-muted-foreground text-center py-12">
          Todos los clientes enviaron comprobantes en los últimos {dias} días.
        </p>
      ) : (
        <>
          {/* Mobile: cards */}
          <div className="flex flex-col divide-y border rounded-lg md:hidden">
            {clientes.map((c) => (
              <div key={c.id} className="px-4 py-3">
                <p className="text-sm font-medium">{c.razon_social}</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  <span className="font-mono">{c.codigo_cliente}</span>
                  {c.ultimo_comprobante && ` · ${formatearFecha(c.ultimo_comprobante)}`}
                  {!c.ultimo_comprobante && " · Sin comprobantes"}
                </p>
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
                  <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Último comprobante</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {clientes.map((c) => (
                  <tr key={c.id} className="hover:bg-muted/20 transition-colors">
                    <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{c.codigo_cliente}</td>
                    <td className="px-4 py-3 font-medium">{c.razon_social}</td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {c.ultimo_comprobante ? formatearFecha(c.ultimo_comprobante) : "Sin comprobantes"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
