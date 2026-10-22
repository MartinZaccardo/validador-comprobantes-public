import { useState } from "react";
import { Button } from "@/components/ui/button";
import { type EstadoValidacion, type CanalValidacion } from "@/api/validaciones";
import { type FiltrosEstadisticasValues } from "@/lib/filtros-estadisticas";
import { ESTADOS_ORDEN, LABEL_ESTADO } from "@/lib/validaciones-ui";
import { ChevronDownIcon, ChevronUpIcon } from "@/components/icons";

interface Props {
  filtros: FiltrosEstadisticasValues;
  bancos: string[];
  onChange: (f: FiltrosEstadisticasValues) => void;
  cargando: boolean;
  onAplicar: () => void;
  onLimpiar: () => void;
  hayFiltros: boolean;
}

export default function FiltrosEstadisticas({
  filtros,
  bancos,
  onChange,
  cargando,
  onAplicar,
  onLimpiar,
  hayFiltros,
}: Props) {
  const [abierto, setAbierto] = useState(false);

  return (
    <div>
      {/* Trigger — solo mobile */}
      <div className="flex items-center gap-2 md:hidden mb-2">
        <button
          onClick={() => setAbierto((v) => !v)}
          className="flex items-center gap-1.5 text-sm font-medium text-foreground"
        >
          Filtros
          {hayFiltros && (
            <span className="inline-flex items-center rounded-full bg-primary/10 text-primary border border-primary/20 px-1.5 py-0.5 text-xs font-medium">
              activos
            </span>
          )}
          {abierto ? <ChevronUpIcon /> : <ChevronDownIcon />}
        </button>
      </div>

    <div className={`${abierto ? "flex" : "hidden"} md:flex flex-wrap items-end gap-3`}>
      <div className="space-y-1">
        <label className="text-xs text-muted-foreground">Procesado desde</label>
        <input
          type="date"
          value={filtros.fecha_desde}
          onChange={(e) => onChange({ ...filtros, fecha_desde: e.target.value })}
          className="flex h-8 rounded-md border border-input bg-background px-2 text-sm cursor-pointer"
        />
      </div>

      <div className="space-y-1">
        <label className="text-xs text-muted-foreground">Procesado hasta</label>
        <input
          type="date"
          value={filtros.fecha_hasta}
          onChange={(e) => onChange({ ...filtros, fecha_hasta: e.target.value })}
          className="flex h-8 rounded-md border border-input bg-background px-2 text-sm cursor-pointer"
        />
      </div>

      <div className="space-y-1">
        <label className="text-xs text-muted-foreground">Modificado desde</label>
        <input
          type="date"
          value={filtros.fecha_mod_desde}
          onChange={(e) =>
            onChange({ ...filtros, fecha_mod_desde: e.target.value })
          }
          className="flex h-8 rounded-md border border-input bg-background px-2 text-sm cursor-pointer"
        />
      </div>

      <div className="space-y-1">
        <label className="text-xs text-muted-foreground">Modificado hasta</label>
        <input
          type="date"
          value={filtros.fecha_mod_hasta}
          onChange={(e) =>
            onChange({ ...filtros, fecha_mod_hasta: e.target.value })
          }
          className="flex h-8 rounded-md border border-input bg-background px-2 text-sm cursor-pointer"
        />
      </div>

      <div className="space-y-1">
        <label className="text-xs text-muted-foreground">Canal</label>
        <select
          value={filtros.canal}
          onChange={(e) =>
            onChange({ ...filtros, canal: e.target.value as CanalValidacion | "" })
          }
          className="flex h-8 rounded-md border border-input bg-background px-2 text-sm cursor-pointer"
        >
          <option value="">Todos</option>
          <option value="MANUAL">Manual</option>
          <option value="WhatsApp">WhatsApp</option>
        </select>
      </div>

      <div className="space-y-1">
        <label className="text-xs text-muted-foreground">Banco</label>
        <select
          value={filtros.banco}
          onChange={(e) => onChange({ ...filtros, banco: e.target.value })}
          className="flex h-8 rounded-md border border-input bg-background px-2 text-sm cursor-pointer"
        >
          <option value="">Todos</option>
          {bancos.map((b) => (
            <option key={b} value={b}>
              {b.replace(/_/g, " ")}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-1">
        <label className="text-xs text-muted-foreground">Estado</label>
        <select
          value={filtros.estado}
          onChange={(e) =>
            onChange({ ...filtros, estado: e.target.value as EstadoValidacion | "" })
          }
          className="flex h-8 rounded-md border border-input bg-background px-2 text-sm cursor-pointer"
        >
          <option value="">Todos</option>
          {ESTADOS_ORDEN.map((e) => (
            <option key={e} value={e}>
              {LABEL_ESTADO[e]}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-1">
        <label className="text-xs text-muted-foreground">Cliente</label>
        <input
          type="text"
          value={filtros.codigo_cliente}
          onChange={(e) =>
            onChange({ ...filtros, codigo_cliente: e.target.value })
          }
          onKeyDown={(e) => e.key === "Enter" && onAplicar()}
          placeholder="Buscar..."
          className="flex h-8 rounded-md border border-input bg-background px-2 text-sm w-36"
        />
      </div>

      <div className="space-y-1">
        <label className="text-xs text-muted-foreground">N° de operación</label>
        <input
          type="text"
          value={filtros.numero_operacion}
          onChange={(e) =>
            onChange({ ...filtros, numero_operacion: e.target.value })
          }
          onKeyDown={(e) => e.key === "Enter" && onAplicar()}
          placeholder="Buscar..."
          className="flex h-8 rounded-md border border-input bg-background px-2 text-sm w-36"
        />
      </div>

      <div className="space-y-1">
        <label className="text-xs text-muted-foreground">Usuario</label>
        <input
          type="text"
          value={filtros.usuario}
          onChange={(e) => onChange({ ...filtros, usuario: e.target.value })}
          onKeyDown={(e) => e.key === "Enter" && onAplicar()}
          placeholder="Vendedor o admin..."
          className="flex h-8 rounded-md border border-input bg-background px-2 text-sm w-36"
        />
      </div>

      <div className="flex gap-2">
        <Button size="sm" onClick={onAplicar} disabled={cargando}>
          {cargando ? "Cargando..." : "Aplicar"}
        </Button>
        {hayFiltros && (
          <Button size="sm" variant="outline" onClick={onLimpiar}>
            Limpiar
          </Button>
        )}
      </div>
    </div>
    </div>
  );
}
