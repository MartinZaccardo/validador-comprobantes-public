import React, { useState, useEffect, useRef } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import {
  listarClientes,
  importarClientes,
  previewImportacion,
  toggleActivoCliente,
  obtenerClienteDetalle,
  type ClienteResumen,
  type ClienteDetalle,
  type PreviewImportacion,
  type ResultadoImportacion,
  type TelefonoItem,
  type CuitItem,
  type ClientesPaginados,
} from "@/api/clientes"
import { ChevronDownIcon, ChevronUpIcon, ChevronLeftIcon, ChevronRightIcon } from "@/components/icons"
import ClienteNuevoForm from "@/components/ClienteNuevoForm"
import ClienteFilaDetalle from "@/components/ClienteFilaDetalle"

interface Props {
  onVerComprobantes: (id: string, nombre: string) => void
}

const PAGE_SIZE = 50

export default function TabClientesPrincipal({ onVerComprobantes }: Props) {
  const [clientes, setClientes] = useState<ClienteResumen[]>([])
  const [totalClientes, setTotalClientes] = useState(0)
  const [cargandoClientes, setCargandoClientes] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busqueda, setBusqueda] = useState("")
  const [filtroAplicado, setFiltroAplicado] = useState("")
  const [paginaActual, setPaginaActual] = useState(1)

  const [toggling, setToggling] = useState<string | null>(null)
  const [mostrarForm, setMostrarForm] = useState(false)

  const [previsualizando, setPrevisualizando] = useState(false)
  const [preview, setPreview] = useState<PreviewImportacion | null>(null)
  const [archivoEnEspera, setArchivoEnEspera] = useState<File | null>(null)
  const [importando, setImportando] = useState(false)
  const [resultadoImport, setResultadoImport] = useState<ResultadoImportacion | null>(null)

  const [expandidoId, setExpandidoId] = useState<string | null>(null)
  const [editandoClienteId, setEditandoClienteId] = useState<string | null>(null)
  const [detalleMap, setDetalleMap] = useState<Record<string, ClienteDetalle>>({})
  const [cargandoDetalle, setCargandoDetalle] = useState(false)

  const fileInputRef = useRef<HTMLInputElement>(null)

  const totalPaginas = Math.max(1, Math.ceil(totalClientes / PAGE_SIZE))
  const paginaClamped = Math.min(paginaActual, totalPaginas)

  useEffect(() => {
    let cancelado = false
    async function fetchear() {
      setCargandoClientes(true)
      setError(null)
      try {
        const resultado: ClientesPaginados = await listarClientes({
          q: filtroAplicado || undefined,
          page: paginaActual,
          pageSize: PAGE_SIZE,
        })
        if (!cancelado) {
          setClientes(resultado.items)
          setTotalClientes(resultado.total)
        }
      } catch (e: unknown) {
        if (!cancelado) setError(e instanceof Error ? e.message : "No se pudo cargar la lista.")
      } finally {
        if (!cancelado) setCargandoClientes(false)
      }
    }
    fetchear()
    return () => { cancelado = true }
  }, [filtroAplicado, paginaActual])

  async function handleSeleccionarArchivo(e: React.ChangeEvent<HTMLInputElement>) {
    const archivo = e.target.files?.[0]
    if (!archivo) return
    setPrevisualizando(true)
    setResultadoImport(null)
    setError(null)
    try {
      const resultado = await previewImportacion(archivo)
      setPreview(resultado)
      setArchivoEnEspera(archivo)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al analizar el CSV.")
    } finally {
      setPrevisualizando(false)
      if (fileInputRef.current) fileInputRef.current.value = ""
    }
  }

  async function handleConfirmarImport() {
    if (!archivoEnEspera) return
    setImportando(true)
    setPreview(null)
    try {
      const resultado = await importarClientes(archivoEnEspera)
      setResultadoImport(resultado)
      setDetalleMap({})
      setBusqueda("")
      setFiltroAplicado("")
      setPaginaActual(1)
      toast.success(
        `${resultado.insertados} cliente${resultado.insertados !== 1 ? "s" : ""} importado${resultado.insertados !== 1 ? "s" : ""}` +
        (resultado.actualizados > 0 ? `, ${resultado.actualizados} actualizado${resultado.actualizados !== 1 ? "s" : ""}` : ""),
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al importar el CSV.")
    } finally {
      setImportando(false)
      setArchivoEnEspera(null)
    }
  }

  function handleCancelarImport() {
    setPreview(null)
    setArchivoEnEspera(null)
  }

  async function handleToggle(cliente: ClienteResumen) {
    setToggling(cliente.id)
    setError(null)
    try {
      const actualizado = await toggleActivoCliente(cliente.id, !cliente.activo)
      setClientes((prev) => prev.map((c) => (c.id === actualizado.id ? actualizado : c)))
      toast.success(actualizado.activo ? "Cliente activado" : "Cliente desactivado")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al actualizar el cliente.")
    } finally {
      setToggling(null)
    }
  }

  async function handleExpandir(id: string) {
    setExpandidoId(id)
    if (!detalleMap[id]) {
      setCargandoDetalle(true)
      try {
        const detalle = await obtenerClienteDetalle(id)
        setDetalleMap((prev) => ({ ...prev, [id]: detalle }))
      } catch (err) {
        setError(err instanceof Error ? err.message : "Error al cargar el detalle.")
        setExpandidoId(null)
      } finally {
        setCargandoDetalle(false)
      }
    }
  }

  function handleToggleDetalle(id: string) {
    if (expandidoId === id) {
      setExpandidoId(null)
      setEditandoClienteId(null)
    } else {
      handleExpandir(id)
    }
  }

  async function handleIniciarEdicion(id: string) {
    await handleExpandir(id)
    setEditandoClienteId(id)
  }

  function handleActualizado(clienteId: string, actualizado: ClienteResumen) {
    setClientes((prev) => prev.map((c) => (c.id === actualizado.id ? actualizado : c)))
    setDetalleMap((prev) => ({ ...prev, [clienteId]: { ...prev[clienteId], ...actualizado } }))
  }

  function handleTelefonoAgregado(clienteId: string, item: TelefonoItem) {
    setDetalleMap((prev) => ({
      ...prev,
      [clienteId]: { ...prev[clienteId], telefonos: [...prev[clienteId].telefonos, item] },
    }))
  }

  function handleTelefonoEliminado(clienteId: string, telefonoId: string) {
    setDetalleMap((prev) => ({
      ...prev,
      [clienteId]: {
        ...prev[clienteId],
        telefonos: prev[clienteId].telefonos.filter((t) => t.id !== telefonoId),
      },
    }))
  }

  function handleCuitAgregado(clienteId: string, item: CuitItem) {
    setDetalleMap((prev) => ({
      ...prev,
      [clienteId]: { ...prev[clienteId], cuits: [...prev[clienteId].cuits, item] },
    }))
  }

  function handleCuitEliminado(clienteId: string, cuitId: string) {
    setDetalleMap((prev) => ({
      ...prev,
      [clienteId]: {
        ...prev[clienteId],
        cuits: prev[clienteId].cuits.filter((ct) => ct.id !== cuitId),
      },
    }))
  }

  return (
    <>
      <div className="flex justify-end gap-2 mb-4">
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          className="hidden"
          onChange={handleSeleccionarArchivo}
        />
        <Button
          variant="outline"
          size="sm"
          disabled={previsualizando || importando || !!preview}
          onClick={() => fileInputRef.current?.click()}
        >
          {previsualizando ? "Analizando..." : "Importar CSV"}
        </Button>
        <Button size="sm" onClick={() => setMostrarForm((v) => !v)}>
          {mostrarForm ? "Cancelar" : "Nuevo cliente"}
        </Button>
      </div>

      {preview && (
        <div className="mb-4 p-4 rounded-md border border-amber-200 bg-amber-50 text-sm space-y-3">
          <div className="flex flex-wrap gap-4">
            <span><span className="font-medium">{preview.total_csv}</span> clientes en el CSV</span>
            {preview.nuevos > 0 && (
              <span className="text-green-700">· <span className="font-medium">{preview.nuevos}</span> nuevos</span>
            )}
            {preview.con_cambios > 0 && (
              <span className="text-amber-700">· <span className="font-medium">{preview.con_cambios}</span> con cambios</span>
            )}
            {preview.sin_cambios > 0 && (
              <span className="text-muted-foreground">· <span className="font-medium">{preview.sin_cambios}</span> sin cambios</span>
            )}
            {preview.filas_invalidas > 0 && (
              <span className="text-destructive">· <span className="font-medium">{preview.filas_invalidas}</span> filas inválidas</span>
            )}
          </div>
          <div className="flex gap-2">
            <Button size="sm" disabled={importando} onClick={handleConfirmarImport}>
              {importando ? "Importando..." : "Confirmar importación"}
            </Button>
            <Button size="sm" variant="outline" disabled={importando} onClick={handleCancelarImport}>
              Cancelar
            </Button>
          </div>
        </div>
      )}

      {resultadoImport && (
        <div className="mb-4 p-3 rounded-md bg-muted text-sm flex gap-3 flex-wrap">
          <span><span className="font-medium">{resultadoImport.insertados}</span> insertados</span>
          {resultadoImport.actualizados > 0 && (
            <span className="text-muted-foreground">· {resultadoImport.actualizados} actualizados</span>
          )}
          {resultadoImport.errores.length > 0 && (
            <span className="text-destructive">· {resultadoImport.errores.length} con error</span>
          )}
        </div>
      )}

      {error && <p className="text-sm text-destructive mb-4">{error}</p>}

      {mostrarForm && (
        <ClienteNuevoForm
          onCreado={(nuevo) => {
            setBusqueda("")
            setFiltroAplicado("")
            setPaginaActual(1)
            setMostrarForm(false)
            toast.success(`Cliente "${nuevo.razon_social}" creado`)
          }}
          onCancelar={() => setMostrarForm(false)}
        />
      )}

      <div className="flex items-center gap-2 mb-3">
        <input
          type="text"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              setFiltroAplicado(busqueda)
              setPaginaActual(1)
            }
          }}
          placeholder="Buscar por razón social o código..."
          className="flex h-8 rounded-md border border-input bg-background px-2 text-sm w-72"
        />
        <Button
          size="sm"
          variant="outline"
          onClick={() => { setFiltroAplicado(busqueda); setPaginaActual(1) }}
        >
          Buscar
        </Button>
        {filtroAplicado && (
          <button
            onClick={() => { setBusqueda(""); setFiltroAplicado(""); setPaginaActual(1) }}
            className="text-xs text-muted-foreground hover:text-foreground underline underline-offset-2"
          >
            Limpiar
          </button>
        )}
        {filtroAplicado && !cargandoClientes && (
          <span className="text-xs text-muted-foreground">
            {totalClientes} resultado{totalClientes !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      {cargandoClientes ? (
        <p className="text-sm text-muted-foreground text-center py-12">Cargando...</p>
      ) : clientes.length === 0 ? (
        <p className="text-sm text-muted-foreground text-center py-12">
          {filtroAplicado ? `Sin resultados para "${filtroAplicado}".` : "No hay clientes registrados."}
        </p>
      ) : (
        <>
          {/* Mobile: cards */}
          <div className="flex flex-col gap-3 md:hidden">
            {clientes.map((c) => (
              <div key={c.id} className="border rounded-lg bg-background">
                <div className="px-4 py-3">
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <span className="font-medium text-sm leading-snug">{c.razon_social}</span>
                    <span
                      className={`shrink-0 inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${
                        c.activo
                          ? "bg-green-100 text-green-800 border-green-200"
                          : "bg-gray-100 text-gray-500 border-gray-200"
                      }`}
                    >
                      {c.activo ? "Activo" : "Inactivo"}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground font-mono">{c.codigo_cliente}</p>
                  {c.direccion && (
                    <p className="text-xs text-muted-foreground mt-0.5">{c.direccion}</p>
                  )}
                </div>
                <div className="px-4 pb-3 flex items-center gap-2 flex-wrap border-t pt-3">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onVerComprobantes(c.id, c.razon_social)}
                  >
                    Comprobantes
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => handleIniciarEdicion(c.id)}>
                    Editar
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={toggling === c.id}
                    onClick={() => handleToggle(c)}
                  >
                    {toggling === c.id ? "..." : c.activo ? "Desactivar" : "Activar"}
                  </Button>
                  <button
                    onClick={() => handleToggleDetalle(c.id)}
                    className="ml-auto p-1 text-muted-foreground hover:text-foreground transition-colors"
                    aria-label="Ver detalle"
                  >
                    {expandidoId === c.id ? <ChevronUpIcon /> : <ChevronDownIcon />}
                  </button>
                </div>
                {expandidoId === c.id && (
                  <div className="px-4 py-4 bg-muted/10 border-t border-dashed">
                    {cargandoDetalle && !detalleMap[c.id] ? (
                      <p className="text-sm text-muted-foreground">Cargando...</p>
                    ) : detalleMap[c.id] ? (
                      <ClienteFilaDetalle
                        detalle={detalleMap[c.id]}
                        clienteId={c.id}
                        editando={editandoClienteId === c.id}
                        onActualizado={(actualizado) => handleActualizado(c.id, actualizado)}
                        onCancelarEdicion={() => setEditandoClienteId(null)}
                        onTelefonoAgregado={(item) => handleTelefonoAgregado(c.id, item)}
                        onTelefonoEliminado={(id) => handleTelefonoEliminado(c.id, id)}
                        onCuitAgregado={(item) => handleCuitAgregado(c.id, item)}
                        onCuitEliminado={(id) => handleCuitEliminado(c.id, id)}
                      />
                    ) : null}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Desktop: tabla */}
          <div className="hidden md:block border rounded-lg overflow-x-auto">
            <table className="w-full min-w-[800px] text-sm">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Código</th>
                  <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Razón social</th>
                  <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Dirección</th>
                  <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Estado</th>
                  <th className="px-4 py-2.5" />
                </tr>
              </thead>
              <tbody className="divide-y">
                {clientes.map((c) => (
                  <React.Fragment key={c.id}>
                    <tr className="hover:bg-muted/20 transition-colors">
                      <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{c.codigo_cliente}</td>
                      <td className="px-4 py-3 font-medium">{c.razon_social}</td>
                      <td className="px-4 py-3 text-muted-foreground">{c.direccion ?? "—"}</td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${
                            c.activo
                              ? "bg-green-100 text-green-800 border-green-200"
                              : "bg-gray-100 text-gray-500 border-gray-200"
                          }`}
                        >
                          {c.activo ? "Activo" : "Inactivo"}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => onVerComprobantes(c.id, c.razon_social)}
                          >
                            Comprobantes
                          </Button>
                          <Button variant="outline" size="sm" onClick={() => handleIniciarEdicion(c.id)}>
                            Editar
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={toggling === c.id}
                            onClick={() => handleToggle(c)}
                          >
                            {toggling === c.id ? "..." : c.activo ? "Desactivar" : "Activar"}
                          </Button>
                          <button
                            onClick={() => handleToggleDetalle(c.id)}
                            className="p-1 text-muted-foreground hover:text-foreground transition-colors"
                            aria-label="Ver detalle"
                          >
                            {expandidoId === c.id ? <ChevronUpIcon /> : <ChevronDownIcon />}
                          </button>
                        </div>
                      </td>
                    </tr>

                    {expandidoId === c.id && (
                      <tr>
                        <td colSpan={5} className="px-6 py-4 bg-muted/10 border-t border-dashed">
                          {cargandoDetalle && !detalleMap[c.id] ? (
                            <p className="text-sm text-muted-foreground">Cargando...</p>
                          ) : detalleMap[c.id] ? (
                            <ClienteFilaDetalle
                              detalle={detalleMap[c.id]}
                              clienteId={c.id}
                              editando={editandoClienteId === c.id}
                              onActualizado={(actualizado) => handleActualizado(c.id, actualizado)}
                              onCancelarEdicion={() => setEditandoClienteId(null)}
                              onTelefonoAgregado={(item) => handleTelefonoAgregado(c.id, item)}
                              onTelefonoEliminado={(id) => handleTelefonoEliminado(c.id, id)}
                              onCuitAgregado={(item) => handleCuitAgregado(c.id, item)}
                              onCuitEliminado={(id) => handleCuitEliminado(c.id, id)}
                            />
                          ) : null}
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {totalPaginas > 1 && (
        <div className="flex items-center justify-between mt-3">
          <span className="text-xs text-muted-foreground">
            Página {paginaClamped} de {totalPaginas} · {totalClientes} cliente{totalClientes !== 1 ? "s" : ""}
          </span>
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPaginaActual((p) => p - 1)}
              disabled={paginaClamped === 1}
            >
              <ChevronLeftIcon />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPaginaActual((p) => p + 1)}
              disabled={paginaClamped === totalPaginas}
            >
              <ChevronRightIcon />
            </Button>
          </div>
        </div>
      )}
    </>
  )
}
