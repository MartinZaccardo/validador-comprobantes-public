import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
  crearCliente,
  agregarTelefono,
  agregarCuit,
  type ClienteResumen,
} from "@/api/clientes"

interface Props {
  onCreado: (cliente: ClienteResumen) => void
  onCancelar: () => void
}

export default function ClienteNuevoForm({ onCreado, onCancelar }: Props) {
  const [codigo, setCodigo] = useState("")
  const [razonSocial, setRazonSocial] = useState("")
  const [direccion, setDireccion] = useState("")
  const [telefonosInput, setTelefonosInput] = useState("")
  const [cuitsInput, setCuitsInput] = useState("")
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setGuardando(true)
    setError(null)
    try {
      const nuevo = await crearCliente({
        codigo_cliente: codigo.trim(),
        razon_social: razonSocial.trim(),
        direccion: direccion.trim() || undefined,
      })
      const telefonos = telefonosInput.split(";").map((t) => t.trim()).filter(Boolean)
      const cuits = cuitsInput.split(";").map((c) => c.trim()).filter(Boolean)
      await Promise.all([
        ...telefonos.map((t) => agregarTelefono(nuevo.id, t).catch(() => null)),
        ...cuits.map((c) => agregarCuit(nuevo.id, c).catch(() => null)),
      ])
      onCreado(nuevo)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al crear el cliente.")
    } finally {
      setGuardando(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mb-6 p-4 border rounded-lg space-y-3">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div>
          <label className="text-xs text-muted-foreground mb-1 block">Código *</label>
          <input
            value={codigo}
            onChange={(e) => setCodigo(e.target.value)}
            required
            placeholder="1001"
            className="w-full text-sm border rounded-md px-3 py-1.5 bg-background focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
        <div>
          <label className="text-xs text-muted-foreground mb-1 block">Razón social *</label>
          <input
            value={razonSocial}
            onChange={(e) => setRazonSocial(e.target.value)}
            required
            placeholder="Ferretería El Tornillo"
            className="w-full text-sm border rounded-md px-3 py-1.5 bg-background focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
        <div>
          <label className="text-xs text-muted-foreground mb-1 block">Dirección</label>
          <input
            value={direccion}
            onChange={(e) => setDireccion(e.target.value)}
            placeholder="Av. Rivadavia 1234, CABA"
            className="w-full text-sm border rounded-md px-3 py-1.5 bg-background focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
        <div>
          <label className="text-xs text-muted-foreground mb-1 block">Teléfonos (separar con ;)</label>
          <input
            value={telefonosInput}
            onChange={(e) => setTelefonosInput(e.target.value)}
            placeholder="5491122334455;5491199887766"
            className="w-full text-sm border rounded-md px-3 py-1.5 bg-background focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
        <div>
          <label className="text-xs text-muted-foreground mb-1 block">CUITs (separar con ;)</label>
          <input
            value={cuitsInput}
            onChange={(e) => setCuitsInput(e.target.value)}
            placeholder="20123456789;30987654321"
            className="w-full text-sm border rounded-md px-3 py-1.5 bg-background focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" size="sm" onClick={onCancelar}>
          Cancelar
        </Button>
        <Button type="submit" size="sm" disabled={guardando}>
          {guardando ? "Guardando..." : "Guardar"}
        </Button>
      </div>
    </form>
  )
}
