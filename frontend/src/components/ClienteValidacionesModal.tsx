import { useState, useEffect } from "react";
import {
  listarValidacionesDeCliente,
  type ValidacionCliente,
} from "@/api/clientes";
import {
  formatearFecha,
  formatearMonto,
  LABEL_ESTADO,
  COLORES_ESTADO,
  LABEL_CANAL,
} from "@/lib/validaciones-ui";

interface Props {
  clienteId: string;
  razonSocial: string;
  onCerrar: () => void;
}

type EstadoImagen = "cargando" | "lista" | "no_disponible";

export default function ClienteValidacionesModal({
  clienteId,
  razonSocial,
  onCerrar,
}: Props) {
  const [validaciones, setValidaciones] = useState<ValidacionCliente[]>([]);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [viendoId, setViendoId] = useState<string | null>(null);
  const [urlImagen, setUrlImagen] = useState<string | null>(null);
  const [estadoImagen, setEstadoImagen] =
    useState<EstadoImagen>("no_disponible");

  useEffect(() => {
    let cancelado = false;
    async function fetchear() {
      setCargando(true);
      setError(null);
      try {
        const datos = await listarValidacionesDeCliente(clienteId);
        if (!cancelado) setValidaciones(datos);
      } catch (e: unknown) {
        if (!cancelado)
          setError(e instanceof Error ? e.message : "No se pudo cargar.");
      } finally {
        if (!cancelado) setCargando(false);
      }
    }
    fetchear();
    return () => {
      cancelado = true;
    };
  }, [clienteId]);

  useEffect(() => {
    if (!viendoId) return;
    let cancelado = false;
    async function cargarImagen() {
      try {
        const resp = await fetch(`/api/validaciones/${viendoId}/imagen`, {
          credentials: "include",
        });
        if (!cancelado) {
          if (!resp.ok) {
            setEstadoImagen("no_disponible");
            return;
          }
          const data = (await resp.json()) as { url?: string };
          if (data?.url) {
            setUrlImagen(data.url);
            setEstadoImagen("lista");
          } else setEstadoImagen("no_disponible");
        }
      } catch {
        if (!cancelado) setEstadoImagen("no_disponible");
      }
    }
    cargarImagen();
    return () => {
      cancelado = true;
    };
  }, [viendoId]);

  function handleToggleVer(id: string) {
    if (viendoId === id) {
      setViendoId(null);
      setUrlImagen(null);
      setEstadoImagen("no_disponible");
    } else {
      setViendoId(id);
      setUrlImagen(null);
      setEstadoImagen("cargando");
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 pt-12 px-4 overflow-y-auto"
      onClick={(e) => {
        if (e.target === e.currentTarget) onCerrar();
      }}
    >
      <div className="bg-background rounded-xl shadow-lg w-full max-w-4xl p-6 mb-12">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-base">
            Comprobantes — {razonSocial}
          </h3>
          <button
            onClick={onCerrar}
            className="text-muted-foreground hover:text-foreground transition-colors cursor-pointer text-lg leading-none"
            aria-label="Cerrar"
          >
            ✕
          </button>
        </div>

        {cargando && (
          <p className="text-sm text-muted-foreground text-center py-8">
            Cargando...
          </p>
        )}

        {error && <p className="text-sm text-destructive py-4">{error}</p>}

        {!cargando && !error && validaciones.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-8">
            Este cliente no tiene comprobantes vinculados.
          </p>
        )}

        {!cargando && validaciones.length > 0 && (
          <div className="space-y-4">
            {/* Mobile: cards */}
            <div className="flex flex-col gap-3 md:hidden">
              {validaciones.map((v) => (
                <div
                  key={v.id}
                  className={`border rounded-lg p-4 ${viendoId === v.id ? "bg-muted/20" : "bg-background"}`}
                >
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span
                      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${
                        COLORES_ESTADO[v.estado as keyof typeof COLORES_ESTADO] ?? "bg-gray-100 text-gray-500 border-gray-200"
                      }`}
                    >
                      {LABEL_ESTADO[v.estado as keyof typeof LABEL_ESTADO] ?? v.estado}
                    </span>
                    <span className="text-xs text-muted-foreground">{LABEL_CANAL[v.canal] ?? v.canal}</span>
                  </div>
                  <p className="text-base font-semibold mb-1">{formatearMonto(v.monto_detectado)}</p>
                  <div className="text-xs text-muted-foreground space-y-0.5 mb-3">
                    <p>{formatearFecha(v.procesado_en)}{v.entidad_emisora && ` · ${v.entidad_emisora.replace(/_/g, " ")}`}</p>
                    {v.identificador_pago && <p className="font-mono">Op: {v.identificador_pago}</p>}
                  </div>
                  {v.imagen_path && (
                    <>
                      <button
                        onClick={() => handleToggleVer(v.id)}
                        className={`text-xs underline underline-offset-2 transition-colors ${
                          viendoId === v.id ? "text-foreground" : "text-muted-foreground hover:text-foreground"
                        }`}
                      >
                        {viendoId === v.id ? "Ocultar imagen" : "Ver imagen"}
                      </button>
                      {viendoId === v.id && (
                        <div className="mt-3 border rounded-lg overflow-hidden bg-muted/30 flex items-center justify-center min-h-24">
                          {estadoImagen === "cargando" && <p className="text-xs text-muted-foreground py-6">Cargando imagen...</p>}
                          {estadoImagen === "no_disponible" && <p className="text-xs text-muted-foreground py-6">Imagen no disponible</p>}
                          {estadoImagen === "lista" && urlImagen && (
                            <a href={urlImagen} target="_blank" rel="noopener noreferrer" title="Click para abrir en tamaño completo" className="block cursor-zoom-in w-full">
                              <img src={urlImagen} alt="Comprobante" className="max-h-64 w-full object-contain" />
                            </a>
                          )}
                        </div>
                      )}
                    </>
                  )}
                </div>
              ))}
            </div>

            {/* Desktop: tabla */}
            <div className="hidden md:block border rounded-lg overflow-x-auto max-h-[480px] overflow-y-auto">
              <table className="w-full min-w-[720px] text-sm">
                <thead className="bg-muted/50 sticky top-0 z-10">
                  <tr>
                    <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Fecha</th>
                    <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Estado</th>
                    <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Monto</th>
                    <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">N° Operación</th>
                    <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Canal</th>
                    <th className="text-left px-4 py-2.5 font-medium text-muted-foreground">Banco</th>
                    <th className="px-4 py-2.5" />
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {validaciones.map((v) => (
                    <>
                      <tr
                        key={v.id}
                        className={`transition-colors ${viendoId === v.id ? "bg-muted/30" : "hover:bg-muted/20"}`}
                      >
                        <td className="px-4 py-3 text-muted-foreground whitespace-nowrap">{formatearFecha(v.procesado_en)}</td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${COLORES_ESTADO[v.estado as keyof typeof COLORES_ESTADO] ?? "bg-gray-100 text-gray-500 border-gray-200"}`}>
                            {LABEL_ESTADO[v.estado as keyof typeof LABEL_ESTADO] ?? v.estado}
                          </span>
                        </td>
                        <td className="px-4 py-3">{formatearMonto(v.monto_detectado)}</td>
                        <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{v.identificador_pago ?? "—"}</td>
                        <td className="px-4 py-3 text-muted-foreground">{LABEL_CANAL[v.canal] ?? v.canal}</td>
                        <td className="px-4 py-3 text-muted-foreground">{v.entidad_emisora?.replace(/_/g, " ") ?? "—"}</td>
                        <td className="px-4 py-3 text-right">
                          {v.imagen_path && (
                            <button
                              onClick={() => handleToggleVer(v.id)}
                              className={`text-xs underline underline-offset-2 transition-colors ${viendoId === v.id ? "text-foreground" : "text-muted-foreground hover:text-foreground"}`}
                            >
                              {viendoId === v.id ? "Ocultar" : "Ver"}
                            </button>
                          )}
                        </td>
                      </tr>
                      {viendoId === v.id && (
                        <tr key={`${v.id}-imagen`}>
                          <td colSpan={7} className="px-4 pb-4 pt-0">
                            <div className="border rounded-lg overflow-hidden bg-muted/30 flex items-center justify-center min-h-24">
                              {estadoImagen === "cargando" && <p className="text-xs text-muted-foreground py-8">Cargando imagen...</p>}
                              {estadoImagen === "no_disponible" && <p className="text-xs text-muted-foreground py-8">Imagen no disponible</p>}
                              {estadoImagen === "lista" && urlImagen && (
                                <a href={urlImagen} target="_blank" rel="noopener noreferrer" title="Click para abrir en tamaño completo" className="block cursor-zoom-in w-full">
                                  <img src={urlImagen} alt="Comprobante" className="max-h-96 w-full object-contain" />
                                </a>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
