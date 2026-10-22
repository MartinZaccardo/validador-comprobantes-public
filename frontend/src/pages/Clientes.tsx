import { useState } from "react"
import ClienteValidacionesModal from "@/components/ClienteValidacionesModal"
import TabClientesPrincipal from "@/components/TabClientesPrincipal"
import TabSinActividad from "@/components/TabSinActividad"
import TabSinComprobantes from "@/components/TabSinComprobantes"

type Tab = "clientes" | "sin-actividad" | "sin-comprobantes"

const TABS: { id: Tab; label: string }[] = [
  { id: "clientes", label: "Todos" },
  { id: "sin-actividad", label: "Sin actividad" },
  { id: "sin-comprobantes", label: "Sin comprobantes" },
]

export default function Clientes() {
  const [tabActiva, setTabActiva] = useState<Tab>("clientes")
  const [clienteModal, setClienteModal] = useState<{ id: string; nombre: string } | null>(null)

  return (
    <>
      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-8 sm:py-12">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Clientes</h2>
        </div>

        <div className="flex border-b mb-4">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setTabActiva(tab.id)}
              className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
                tabActiva === tab.id
                  ? "border-foreground text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {tabActiva === "clientes" && (
          <TabClientesPrincipal
            onVerComprobantes={(id, nombre) => setClienteModal({ id, nombre })}
          />
        )}
        {tabActiva === "sin-actividad" && <TabSinActividad />}
        {tabActiva === "sin-comprobantes" && <TabSinComprobantes />}
      </main>

      {clienteModal && (
        <ClienteValidacionesModal
          clienteId={clienteModal.id}
          razonSocial={clienteModal.nombre}
          onCerrar={() => setClienteModal(null)}
        />
      )}
    </>
  )
}
