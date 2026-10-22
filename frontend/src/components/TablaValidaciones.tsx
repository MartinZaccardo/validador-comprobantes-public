import { useState } from "react";
import { Button } from "@/components/ui/button";
import { NoteIcon, TrashIcon } from "@/components/icons";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { eliminarValidacion, type Validacion } from "@/api/validaciones";
import EditarValidacionModal from "@/components/EditarValidacionModal";
import {
  COLORES_ESTADO,
  COLORES_CANAL,
  LABEL_ESTADO,
  LABEL_CANAL,
  formatearFecha,
  formatearMonto,
} from "@/lib/validaciones-ui";

interface Props {
  validaciones: Validacion[];
  mensajeVacio: string;
  mostrarProcesado?: boolean;
  onActualizada: (v: Validacion) => void;
  onEliminada: (id: string) => void;
  onError?: (msg: string) => void;
}

export default function TablaValidaciones({
  validaciones,
  mensajeVacio,
  mostrarProcesado = true,
  onActualizada,
  onEliminada,
  onError,
}: Props) {
  const [validacionEditando, setValidacionEditando] = useState<Validacion | null>(null);
  const [idConfirmando, setIdConfirmando] = useState<string | null>(null);
  const [eliminando, setEliminando] = useState<string | null>(null);

  async function handleEliminar(id: string) {
    setEliminando(id);
    try {
      await eliminarValidacion(id);
      onEliminada(id);
      setIdConfirmando(null);
    } catch (e) {
      onError?.(e instanceof Error ? e.message : "Error al eliminar el comprobante");
      setIdConfirmando(null);
    } finally {
      setEliminando(null);
    }
  }

  function handleValidacionGuardada(actualizada: Validacion) {
    onActualizada(actualizada);
    setValidacionEditando(null);
  }

  if (validaciones.length === 0) {
    return (
      <p className="text-center text-muted-foreground py-12">{mensajeVacio}</p>
    );
  }

  return (
    <>
      {/* Mobile: cards */}
      <div className="flex flex-col gap-3 md:hidden">
        {validaciones.map((v) => (
          <div key={v.id} className="border rounded-lg bg-background p-4">
            <div className="flex items-center justify-between gap-2 mb-2">
              <span
                className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium whitespace-nowrap ${COLORES_ESTADO[v.estado]}`}
              >
                {LABEL_ESTADO[v.estado]}
              </span>
              <span
                className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${COLORES_CANAL[v.canal] ?? ""}`}
              >
                {LABEL_CANAL[v.canal] ?? v.canal}
              </span>
            </div>

            <p className="text-base font-semibold mb-1">{formatearMonto(v.monto_detectado)}</p>

            <div className="text-xs text-muted-foreground space-y-0.5 mb-3">
              <p>
                <span className="font-mono">{v.codigo_cliente ?? "—"}</span>
                {v.entidad_emisora && (
                  <span> · {v.entidad_emisora.replace(/_/g, " ")}</span>
                )}
              </p>
              {v.identificador_pago && (
                <p className="font-mono">Op: {v.identificador_pago}</p>
              )}
              {(v.canal === "MANUAL" ? v.creado_por_nombre : v.codigo_vendedor) ? (
                <p>
                  {v.canal === "MANUAL" ? v.creado_por_nombre : v.codigo_vendedor}
                  {mostrarProcesado && v.procesado_en && (
                    <span> · {formatearFecha(v.procesado_en)}</span>
                  )}
                </p>
              ) : mostrarProcesado && v.procesado_en ? (
                <p>{formatearFecha(v.procesado_en)}</p>
              ) : null}
            </div>

            {idConfirmando === v.id ? (
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">¿Eliminar?</span>
                <Button
                  size="sm"
                  variant="destructive"
                  onClick={() => handleEliminar(v.id)}
                  disabled={eliminando === v.id}
                >
                  {eliminando === v.id ? "..." : "Sí"}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setIdConfirmando(null)}
                  disabled={eliminando === v.id}
                >
                  No
                </Button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setValidacionEditando(v)}
                  title={v.observaciones ?? "Agregar observación"}
                  className="cursor-pointer"
                >
                  {v.observaciones ? (
                    <span className="text-primary"><NoteIcon /></span>
                  ) : (
                    <span className="text-muted-foreground/30 hover:text-muted-foreground transition-colors"><NoteIcon /></span>
                  )}
                </button>
                <Button variant="outline" size="sm" onClick={() => setValidacionEditando(v)}>
                  Revisar
                </Button>
                <button
                  onClick={() => setIdConfirmando(v.id)}
                  title="Eliminar comprobante"
                  className="ml-auto cursor-pointer text-muted-foreground/30 hover:text-destructive transition-colors"
                >
                  <TrashIcon />
                </button>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Desktop: tabla */}
      <div className="hidden md:block overflow-auto max-h-[calc(100vh-16rem)] rounded-md border">
        <Table>
          <TableHeader className="sticky top-0 z-10 bg-background">
            <TableRow>
              <TableHead>Cliente</TableHead>
              <TableHead>Usuario</TableHead>
              <TableHead>Canal</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead>Operación</TableHead>
              <TableHead>Banco</TableHead>
              <TableHead>Monto</TableHead>
              {mostrarProcesado && <TableHead className="whitespace-nowrap">Procesado</TableHead>}
              <TableHead className="text-right sticky right-0 bg-background border-l">
                Acciones
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {validaciones.map((v) => (
              <TableRow key={v.id}>
                <TableCell className="font-mono text-sm">
                  {v.codigo_cliente ?? "—"}
                </TableCell>
                <TableCell className="font-mono text-sm text-muted-foreground">
                  {v.canal === "MANUAL"
                    ? (v.creado_por_nombre ?? "—")
                    : (v.codigo_vendedor ?? "—")}
                </TableCell>
                <TableCell>
                  <span
                    className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${COLORES_CANAL[v.canal] ?? ""}`}
                  >
                    {LABEL_CANAL[v.canal] ?? v.canal}
                  </span>
                </TableCell>
                <TableCell>
                  <span
                    className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium whitespace-nowrap ${COLORES_ESTADO[v.estado]}`}
                  >
                    {LABEL_ESTADO[v.estado]}
                  </span>
                </TableCell>
                <TableCell className="font-mono text-sm">
                  {v.identificador_pago ?? "—"}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                  {v.entidad_emisora ? v.entidad_emisora.replace(/_/g, " ") : "—"}
                </TableCell>
                <TableCell className="text-sm">
                  {formatearMonto(v.monto_detectado)}
                </TableCell>
                {mostrarProcesado && (
                  <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                    {formatearFecha(v.procesado_en)}
                  </TableCell>
                )}
                <TableCell className="text-right sticky right-0 bg-background border-l">
                  {idConfirmando === v.id ? (
                    <div className="flex items-center justify-end gap-1">
                      <span className="text-xs text-muted-foreground mr-1">
                        ¿Eliminar?
                      </span>
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => handleEliminar(v.id)}
                        disabled={eliminando === v.id}
                      >
                        {eliminando === v.id ? "..." : "Sí"}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setIdConfirmando(null)}
                        disabled={eliminando === v.id}
                      >
                        No
                      </Button>
                    </div>
                  ) : (
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => setValidacionEditando(v)}
                        title={v.observaciones ?? "Agregar observación"}
                        className="cursor-pointer"
                      >
                        {v.observaciones ? (
                          <span className="text-primary">
                            <NoteIcon />
                          </span>
                        ) : (
                          <span className="text-muted-foreground/30 hover:text-muted-foreground transition-colors">
                            <NoteIcon />
                          </span>
                        )}
                      </button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setValidacionEditando(v)}
                      >
                        Revisar
                      </Button>
                      <button
                        onClick={() => setIdConfirmando(v.id)}
                        title="Eliminar comprobante"
                        className="cursor-pointer text-muted-foreground/30 hover:text-destructive transition-colors"
                      >
                        <TrashIcon />
                      </button>
                    </div>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {validacionEditando && (
        <EditarValidacionModal
          validacion={validacionEditando}
          onGuardado={handleValidacionGuardada}
          onCerrar={() => setValidacionEditando(null)}
        />
      )}
    </>
  );
}
