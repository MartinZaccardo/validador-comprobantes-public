import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { TrashIcon } from "@/components/icons";
import {
  actualizarCliente,
  agregarTelefono,
  eliminarTelefono,
  agregarCuit,
  eliminarCuit,
  type ClienteDetalle,
  type ClienteResumen,
  type TelefonoItem,
  type CuitItem,
} from "@/api/clientes";

interface Props {
  detalle: ClienteDetalle;
  clienteId: string;
  editando: boolean;
  onActualizado: (cliente: ClienteResumen) => void;
  onCancelarEdicion: () => void;
  onTelefonoAgregado: (item: TelefonoItem) => void;
  onTelefonoEliminado: (telefonoId: string) => void;
  onCuitAgregado: (item: CuitItem) => void;
  onCuitEliminado: (cuitId: string) => void;
}

export default function ClienteFilaDetalle({
  detalle,
  clienteId,
  editando,
  onActualizado,
  onCancelarEdicion,
  onTelefonoAgregado,
  onTelefonoEliminado,
  onCuitAgregado,
  onCuitEliminado,
}: Props) {
  const [editRazonSocial, setEditRazonSocial] = useState("");
  const [editDireccion, setEditDireccion] = useState("");
  const [guardandoEdit, setGuardandoEdit] = useState(false);
  const [errorEdit, setErrorEdit] = useState<string | null>(null);
  const [nuevoTelefono, setNuevoTelefono] = useState("");
  const [nuevoCuit, setNuevoCuit] = useState("");
  const [agregandoTelefono, setAgregandoTelefono] = useState(false);
  const [agregandoCuit, setAgregandoCuit] = useState(false);
  const [eliminando, setEliminando] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [prevEditando, setPrevEditando] = useState(editando);
  if (prevEditando !== editando) {
    setPrevEditando(editando);
    if (editando) {
      setEditRazonSocial(detalle.razon_social);
      setEditDireccion(detalle.direccion ?? "");
      setErrorEdit(null);
    }
  }

  async function handleGuardarEdit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setGuardandoEdit(true);
    setErrorEdit(null);
    try {
      const actualizado = await actualizarCliente(clienteId, {
        razon_social: editRazonSocial.trim(),
        direccion: editDireccion.trim() || undefined,
      });
      onActualizado(actualizado);
      onCancelarEdicion();
      toast.success("Datos del cliente actualizados");
    } catch (err) {
      setErrorEdit(
        err instanceof Error ? err.message : "Error al guardar los cambios.",
      );
    } finally {
      setGuardandoEdit(false);
    }
  }

  async function handleAgregarTelefono() {
    if (!nuevoTelefono.trim()) return;
    setAgregandoTelefono(true);
    setError(null);
    try {
      const item = await agregarTelefono(clienteId, nuevoTelefono.trim());
      onTelefonoAgregado(item);
      setNuevoTelefono("");
      toast.success("Teléfono agregado");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Error al agregar el teléfono.",
      );
    } finally {
      setAgregandoTelefono(false);
    }
  }

  async function handleEliminarTelefono(telefonoId: string) {
    setEliminando(telefonoId);
    setError(null);
    try {
      await eliminarTelefono(clienteId, telefonoId);
      onTelefonoEliminado(telefonoId);
      toast.success("Teléfono eliminado");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Error al eliminar el teléfono.",
      );
    } finally {
      setEliminando(null);
    }
  }

  async function handleAgregarCuit() {
    if (!nuevoCuit.trim()) return;
    setAgregandoCuit(true);
    setError(null);
    try {
      const item = await agregarCuit(clienteId, nuevoCuit.trim());
      onCuitAgregado(item);
      setNuevoCuit("");
      toast.success("CUIT agregado");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Error al agregar el CUIT.",
      );
    } finally {
      setAgregandoCuit(false);
    }
  }

  async function handleEliminarCuit(cuitId: string) {
    setEliminando(cuitId);
    setError(null);
    try {
      await eliminarCuit(clienteId, cuitId);
      onCuitEliminado(cuitId);
      toast.success("CUIT eliminado");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Error al eliminar el CUIT.",
      );
    } finally {
      setEliminando(null);
    }
  }

  return (
    <div className="space-y-4">
      {editando && (
        <form onSubmit={handleGuardarEdit} className="space-y-3 pb-4 border-b">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">
                Razón social *
              </label>
              <input
                value={editRazonSocial}
                onChange={(e) => setEditRazonSocial(e.target.value)}
                required
                className="w-full text-sm border rounded-md px-3 py-1.5 bg-background focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">
                Dirección
              </label>
              <input
                value={editDireccion}
                onChange={(e) => setEditDireccion(e.target.value)}
                className="w-full text-sm border rounded-md px-3 py-1.5 bg-background focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>
          </div>
          {errorEdit && <p className="text-xs text-destructive">{errorEdit}</p>}
          <div className="flex gap-2">
            <Button type="submit" size="sm" disabled={guardandoEdit}>
              {guardandoEdit ? "Guardando..." : "Guardar"}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={guardandoEdit}
              onClick={onCancelarEdicion}
            >
              Cancelar
            </Button>
          </div>
        </form>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        {error && (
          <p className="col-span-full text-xs text-destructive">{error}</p>
        )}

        {/* Teléfonos */}
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-2">
            Teléfonos
          </p>
          <ul className="space-y-1 mb-2">
            {detalle.telefonos.length === 0 && (
              <li className="text-xs text-muted-foreground">Sin teléfonos</li>
            )}
            {detalle.telefonos.map((t) => (
              <li
                key={t.id}
                className="flex items-center justify-between gap-2 text-sm"
              >
                <span className="font-mono text-xs">{t.telefono}</span>
                <button
                  disabled={eliminando === t.id}
                  onClick={() => handleEliminarTelefono(t.id)}
                  className="text-muted-foreground hover:text-destructive transition-colors disabled:opacity-40"
                  aria-label="Eliminar teléfono"
                >
                  <TrashIcon />
                </button>
              </li>
            ))}
          </ul>
          <div className="flex gap-2">
            <input
              value={nuevoTelefono}
              onChange={(e) => setNuevoTelefono(e.target.value)}
              placeholder="5491122334455"
              className="flex-1 text-xs border rounded-md px-2 py-1 bg-background focus:outline-none focus:ring-1 focus:ring-ring"
              onKeyDown={(e) =>
                e.key === "Enter" &&
                (e.preventDefault(), handleAgregarTelefono())
              }
            />
            <Button
              size="sm"
              variant="outline"
              disabled={agregandoTelefono}
              onClick={handleAgregarTelefono}
            >
              {agregandoTelefono ? "..." : "Agregar"}
            </Button>
          </div>
        </div>

        {/* CUITs */}
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-2">
            CUITs/CUILs
          </p>
          <ul className="space-y-1 mb-2">
            {detalle.cuits.length === 0 && (
              <li className="text-xs text-muted-foreground">Sin CUITs</li>
            )}
            {detalle.cuits.map((ct) => (
              <li
                key={ct.id}
                className="flex items-center justify-between gap-2 text-sm"
              >
                <span className="font-mono text-xs">{ct.cuit}</span>
                <button
                  disabled={eliminando === ct.id}
                  onClick={() => handleEliminarCuit(ct.id)}
                  className="text-muted-foreground hover:text-destructive transition-colors disabled:opacity-40"
                  aria-label="Eliminar CUIT"
                >
                  <TrashIcon />
                </button>
              </li>
            ))}
          </ul>
          <div className="flex gap-2">
            <input
              value={nuevoCuit}
              onChange={(e) => setNuevoCuit(e.target.value)}
              placeholder="20123456789"
              className="flex-1 text-xs border rounded-md px-2 py-1 bg-background focus:outline-none focus:ring-1 focus:ring-ring"
              onKeyDown={(e) =>
                e.key === "Enter" && (e.preventDefault(), handleAgregarCuit())
              }
            />
            <Button
              size="sm"
              variant="outline"
              disabled={agregandoCuit}
              onClick={handleAgregarCuit}
            >
              {agregandoCuit ? "..." : "Agregar"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
