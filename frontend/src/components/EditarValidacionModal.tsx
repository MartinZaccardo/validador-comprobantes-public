import { useState, useEffect, useRef, type SyntheticEvent } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  editarValidacion,
  reemplazarImagen,
  type Validacion,
  type EstadoValidacion,
} from "@/api/validaciones";
import { formatearFecha } from "@/lib/validaciones-ui";

// ---------------------------------------------------------------------------
// Tipos
// ---------------------------------------------------------------------------

interface Props {
  validacion: Validacion;
  onGuardado: (actualizada: Validacion) => void;
  onCerrar: () => void;
}

// ---------------------------------------------------------------------------
// Constantes
// ---------------------------------------------------------------------------

const ESTADOS: { value: EstadoValidacion; label: string }[] = [
  { value: "APROBADO", label: "Aprobado" },
  { value: "DUPLICADO", label: "Duplicado" },
  { value: "MONTO_ADULTERADO", label: "Monto adulterado" },
  { value: "PAGO_NO_ACREDITADO", label: "Pago no acreditado" },
  { value: "REVISION_MANUAL", label: "Revisión manual" },
  { value: "NUMERO_OP_NO_ENCONTRADO", label: "N° op. no encontrado" },
  { value: "ERROR_DESTINATARIO", label: "Error destinatario" },
  { value: "IMAGEN_INVALIDA", label: "Imagen inválida" },
  { value: "ERROR_MP", label: "Error MP" },
];

// ---------------------------------------------------------------------------
// Componente
// ---------------------------------------------------------------------------

/**
 * Modal de edición de una validación.
 *
 * Permite al admin cambiar el número de operación y/o el estado sin
 * llamar a Mercado Pago — la decisión es manual y queda registrada en
 * la tabla de auditoría del backend.
 *
 * Preview de imagen:
 *   Solo para validaciones con canal='MANUAL' que tienen imagen_path.
 *   <img src> no puede enviar headers de auth, así que hacemos fetch()
 *   con el JWT, recibimos el blob y creamos una URL local temporal con
 *   URL.createObjectURL(). Al cerrar el modal, la URL se revoca para
 *   liberar memoria del navegador.
 */
export default function EditarValidacionModal({
  validacion,
  onGuardado,
  onCerrar,
}: Props) {
  const [nuevoEstado, setNuevoEstado] = useState<EstadoValidacion>(
    validacion.estado,
  );
  const [nuevoNumeroOp, setNuevoNumeroOp] = useState(
    validacion.identificador_pago ?? "",
  );
  const [nuevasObservaciones, setNuevasObservaciones] = useState(
    validacion.observaciones ?? "",
  );
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [urlImagen, setUrlImagen] = useState<string | null>(null);
  type EstadoImagen = "cargando" | "lista" | "no_disponible";
  const [estadoImagen, setEstadoImagen] = useState<EstadoImagen>(
    validacion.imagen_path ? "cargando" : "no_disponible",
  );

  const [nuevaImagen, setNuevaImagen] = useState<File | null>(null);
  const [previewNuevaImagen, setPreviewNuevaImagen] = useState<string | null>(
    null,
  );
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Revoca la blob URL al cambiar la selección o al cerrar el modal
  useEffect(() => {
    return () => {
      if (previewNuevaImagen) URL.revokeObjectURL(previewNuevaImagen);
    };
  }, [previewNuevaImagen]);

  // ── Carga de imagen ────────────────────────────────────────────────────
  useEffect(() => {
    if (!validacion.imagen_path) return;

    fetch(`/api/validaciones/${validacion.id}/imagen`, {
      credentials: "include",
    })
      .then((respuesta) => {
        if (!respuesta.ok) {
          setEstadoImagen("no_disponible");
          return null;
        }
        return respuesta.json();
      })
      .then((data) => {
        if (!data?.url) return;
        setUrlImagen(data.url);
        setEstadoImagen("lista");
      })
      .catch(() => {
        setEstadoImagen("no_disponible");
      });
  }, [validacion.id, validacion.imagen_path]);

  function handleSeleccionarImagen(e: React.ChangeEvent<HTMLInputElement>) {
    const archivo = e.target.files?.[0];
    if (!archivo) return;
    if (previewNuevaImagen) URL.revokeObjectURL(previewNuevaImagen);
    setNuevaImagen(archivo);
    setPreviewNuevaImagen(URL.createObjectURL(archivo));
  }

  // ── Guardar cambios ────────────────────────────────────────────────────
  async function handleGuardar(evento: SyntheticEvent<HTMLFormElement>) {
    evento.preventDefault();
    setError(null);

    const cambios: {
      estado?: string;
      numero_operacion?: string;
      observaciones?: string;
    } = {};

    if (nuevoEstado !== validacion.estado) {
      cambios.estado = nuevoEstado;
    }

    const numeroLimpio = nuevoNumeroOp.trim();
    if (numeroLimpio !== (validacion.identificador_pago ?? "")) {
      if (numeroLimpio) {
        cambios.numero_operacion = numeroLimpio;
      }
    }

    // observaciones: se incluye si cambió respecto al valor original
    const obsOriginal = validacion.observaciones ?? "";
    if (nuevasObservaciones !== obsOriginal) {
      cambios.observaciones = nuevasObservaciones;
    }

    const hayCambiosTexto = Object.keys(cambios).length > 0;

    if (!hayCambiosTexto && !nuevaImagen) {
      setError("No hay cambios para guardar.");
      return;
    }

    setGuardando(true);
    try {
      let actualizada: Validacion | null = null;

      if (nuevaImagen) {
        actualizada = await reemplazarImagen(validacion.id, nuevaImagen);
      }

      if (hayCambiosTexto) {
        actualizada = await editarValidacion(validacion.id, cambios);
      }

      if (actualizada) {
        onGuardado(actualizada);
        toast.success("Cambios guardados");
        onCerrar();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al guardar los cambios");
    } finally {
      setGuardando(false);
    }
  }

  return (
    // Backdrop: clic fuera cierra el modal
    <div className="fixed inset-0 z-50 bg-black/50 overflow-y-auto">
      <div
        className="flex min-h-full items-center justify-center p-4"
        onClick={(e) => {
          if (e.target === e.currentTarget) onCerrar();
        }}
      >
        <div className="bg-background rounded-lg border shadow-lg w-full max-w-md">
          <div className="flex items-start justify-between px-6 pt-6 pb-4 border-b">
            <div className="space-y-1">
              <h2 className="text-lg font-semibold">Editar validación</h2>
              <p className="text-sm text-muted-foreground font-mono">
                Cliente: {validacion.codigo_cliente ?? "—"}
              </p>
            </div>
            <button
              onClick={onCerrar}
              disabled={guardando}
              className="text-muted-foreground hover:text-foreground transition-colors cursor-pointer text-lg leading-none disabled:opacity-40 ml-4 mt-0.5"
              aria-label="Cerrar"
            >
              ✕
            </button>
          </div>
          <div className="space-y-5 px-6 py-5">

          {/* ── Preview de imagen ───────────────────────────────────────── */}
          <div className="space-y-2">
            <div className="rounded-md overflow-hidden border bg-muted/30 flex items-center justify-center min-h-24">
              {previewNuevaImagen ? (
                <img
                  src={previewNuevaImagen}
                  alt="Nueva imagen seleccionada"
                  className="max-h-48 w-full object-contain"
                />
              ) : validacion.imagen_path ? (
                estadoImagen === "lista" && urlImagen ? (
                  <a
                    href={urlImagen}
                    target="_blank"
                    rel="noopener noreferrer"
                    title="Click para abrir en tamaño completo"
                    className="block cursor-zoom-in"
                  >
                    <img
                      src={urlImagen}
                      alt="Comprobante"
                      className="max-h-48 w-full object-contain"
                    />
                  </a>
                ) : (
                  <p className="text-xs text-muted-foreground py-6">
                    {estadoImagen === "cargando"
                      ? "Cargando imagen..."
                      : "Imagen no disponible"}
                  </p>
                )
              ) : (
                <p className="text-xs text-muted-foreground py-6">Sin imagen</p>
              )}
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="hidden"
              onChange={handleSeleccionarImagen}
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={guardando}
              className="text-xs text-muted-foreground underline underline-offset-2 cursor-pointer hover:text-foreground disabled:cursor-not-allowed"
            >
              {previewNuevaImagen
                ? `Cambiar selección (${nuevaImagen?.name})`
                : validacion.imagen_path
                  ? "Reemplazar imagen"
                  : "Agregar imagen"}
            </button>
          </div>

          {/* ── Metadatos read-only ─────────────────────────────────────── */}
          <div className="bg-muted/50 rounded-lg p-3 grid grid-cols-2 gap-x-4 gap-y-3">
            {validacion.monto_detectado != null && (
              <div>
                <p className="text-xs text-muted-foreground">Monto</p>
                <p className="text-sm font-medium">
                  ${validacion.monto_detectado.toLocaleString("es-AR")}
                </p>
              </div>
            )}
            {validacion.entidad_emisora && (
              <div>
                <p className="text-xs text-muted-foreground">Banco</p>
                <p className="text-sm font-medium">
                  {validacion.entidad_emisora.replace(/_/g, " ")}
                </p>
              </div>
            )}
            {validacion.cuit_destinatario_detectado && (
              <div>
                <p className="text-xs text-muted-foreground">
                  CUIT destinatario
                </p>
                <p className="text-sm font-medium">
                  {validacion.cuit_destinatario_detectado}
                </p>
              </div>
            )}
            {validacion.estado_inicial &&
              validacion.estado_inicial !== validacion.estado && (
                <div>
                  <p className="text-xs text-muted-foreground">
                    Estado inicial
                  </p>
                  <p className="text-sm font-medium">
                    {validacion.estado_inicial.replace(/_/g, " ")}
                  </p>
                </div>
              )}
            {validacion.procesado_en && (
              <div>
                <p className="text-xs text-muted-foreground">Procesado</p>
                <p className="text-sm font-medium">
                  {formatearFecha(validacion.procesado_en)}
                </p>
              </div>
            )}
            {validacion.modificado_por_nombre && (
              <div>
                <p className="text-xs text-muted-foreground">Modificado por</p>
                <p className="text-sm font-medium">
                  {validacion.modificado_por_nombre}
                </p>
              </div>
            )}
            {validacion.fecha_modificacion && (
              <div>
                <p className="text-xs text-muted-foreground">
                  Fecha modificación
                </p>
                <p className="text-sm font-medium">
                  {formatearFecha(validacion.fecha_modificacion)}
                </p>
              </div>
            )}
          </div>

          <form onSubmit={handleGuardar} className="space-y-4">
            {/* Número de operación */}
            <div className="space-y-2">
              <label htmlFor="numero-operacion" className="text-sm font-medium">
                Número de operación
              </label>
              <input
                id="numero-operacion"
                type="text"
                value={nuevoNumeroOp}
                onChange={(e) => setNuevoNumeroOp(e.target.value)}
                placeholder="Dejar vacío para no modificar"
                disabled={guardando}
                className="flex h-10 w-full rounded-md border border-input bg-background
                         px-3 py-2 text-sm font-mono ring-offset-background
                         placeholder:text-muted-foreground
                         focus-visible:outline-none focus-visible:ring-2
                         focus-visible:ring-ring focus-visible:ring-offset-2
                         disabled:cursor-not-allowed disabled:opacity-50"
              />
            </div>

            {/* Estado */}
            <div className="space-y-2">
              <label htmlFor="estado" className="text-sm font-medium">
                Estado
              </label>
              <select
                id="estado"
                value={nuevoEstado}
                onChange={(e) =>
                  setNuevoEstado(e.target.value as EstadoValidacion)
                }
                disabled={guardando}
                className="flex h-10 w-full rounded-md border border-input bg-background
                         px-3 py-2 text-sm ring-offset-background
                         focus-visible:outline-none focus-visible:ring-2
                         focus-visible:ring-ring focus-visible:ring-offset-2
                         disabled:cursor-not-allowed disabled:opacity-50"
              >
                {ESTADOS.map((op) => (
                  <option key={op.value} value={op.value}>
                    {op.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Observaciones */}
            <div className="space-y-2">
              <label htmlFor="observaciones" className="text-sm font-medium">
                Observaciones
              </label>
              <textarea
                id="observaciones"
                value={nuevasObservaciones}
                onChange={(e) => setNuevasObservaciones(e.target.value)}
                placeholder="Notas internas sobre este comprobante..."
                disabled={guardando}
                rows={3}
                className="flex w-full rounded-md border border-input bg-background
                         px-3 py-2 text-sm ring-offset-background resize-none
                         placeholder:text-muted-foreground
                         focus-visible:outline-none focus-visible:ring-2
                         focus-visible:ring-ring focus-visible:ring-offset-2
                         disabled:cursor-not-allowed disabled:opacity-50"
              />
            </div>

            {error && <p className="text-sm text-destructive">{error}</p>}

            {/* Botones */}
            <div className="flex justify-end gap-3 pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={onCerrar}
                disabled={guardando}
              >
                Cancelar
              </Button>
              <Button type="submit" disabled={guardando}>
                {guardando ? "Guardando..." : "Guardar"}
              </Button>
            </div>
          </form>
          </div>
        </div>
      </div>
    </div>
  );
}
