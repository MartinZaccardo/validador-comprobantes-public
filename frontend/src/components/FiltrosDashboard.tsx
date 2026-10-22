import { useState } from "react";
import { Button } from "@/components/ui/button";
import { type EstadoValidacion, type CanalValidacion } from "@/api/validaciones";
import { type FiltrosDashboardValues } from "@/lib/filtros-dashboard";
import { ESTADOS_ORDEN, LABEL_ESTADO } from "@/lib/validaciones-ui";
import { ChevronDownIcon, ChevronUpIcon } from "@/components/icons";

const OPCIONES_ESTADO: { value: EstadoValidacion | ""; label: string }[] = [
  { value: "", label: "Todos los estados" },
  ...ESTADOS_ORDEN.map((e) => ({ value: e, label: LABEL_ESTADO[e] })),
];

interface Props {
  filtros: FiltrosDashboardValues;
  bancos: string[];
  onChange: (cambio: Partial<FiltrosDashboardValues>) => void;
  onLimpiar: () => void;
  totalMostrados: number;
  totalTodos: number;
  hayFiltros: boolean;
}

export default function FiltrosDashboard({
  filtros,
  bancos,
  onChange,
  onLimpiar,
  totalMostrados,
  totalTodos,
  hayFiltros,
}: Props) {
  const [abierto, setAbierto] = useState(false);

  const labelResultados = hayFiltros
    ? `${totalMostrados} de ${totalTodos} resultado${totalTodos !== 1 ? "s" : ""}`
    : `${totalTodos} resultado${totalTodos !== 1 ? "s" : ""}`;

  return (
    <div>
      {/* Trigger — solo mobile */}
      <div className="flex items-center justify-between md:hidden mb-2">
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
        <span className="text-sm text-muted-foreground">{labelResultados}</span>
      </div>

      {/* Controles */}
      <div className={`${abierto ? "flex" : "hidden"} md:flex flex-wrap items-center gap-2`}>
        <select
          value={filtros.estado}
          onChange={(e) =>
            onChange({ estado: e.target.value as EstadoValidacion | "" })
          }
          className="flex h-8 rounded-md border border-input bg-background px-2 text-sm cursor-pointer"
        >
          {OPCIONES_ESTADO.map((op) => (
            <option key={op.value} value={op.value}>
              {op.label}
            </option>
          ))}
        </select>

        <select
          value={filtros.canal}
          onChange={(e) =>
            onChange({ canal: e.target.value as CanalValidacion | "" })
          }
          className="flex h-8 rounded-md border border-input bg-background px-2 text-sm cursor-pointer"
        >
          <option value="">Todos los canales</option>
          <option value="MANUAL">Manual</option>
          <option value="WhatsApp">WhatsApp</option>
        </select>

        <select
          value={filtros.banco}
          onChange={(e) => onChange({ banco: e.target.value })}
          className="flex h-8 rounded-md border border-input bg-background px-2 text-sm cursor-pointer"
        >
          <option value="">Todos los bancos</option>
          {bancos.map((b) => (
            <option key={b} value={b}>
              {b.replace(/_/g, " ")}
            </option>
          ))}
        </select>

        <input
          type="text"
          value={filtros.cliente}
          onChange={(e) => onChange({ cliente: e.target.value })}
          placeholder="Cliente..."
          className="flex h-8 rounded-md border border-input bg-background px-2 text-sm w-32"
        />

        <input
          type="text"
          value={filtros.numero_operacion}
          onChange={(e) => onChange({ numero_operacion: e.target.value })}
          placeholder="N° operación..."
          className="flex h-8 rounded-md border border-input bg-background px-2 text-sm w-32"
        />

        <input
          type="text"
          value={filtros.usuario}
          onChange={(e) => onChange({ usuario: e.target.value })}
          placeholder="Admin / Vendedor..."
          className="flex h-8 rounded-md border border-input bg-background px-2 text-sm w-40"
        />

        {hayFiltros && (
          <Button size="sm" variant="outline" onClick={onLimpiar}>
            Limpiar
          </Button>
        )}

        <span className="hidden md:inline text-sm text-muted-foreground ml-auto">
          {labelResultados}
        </span>
      </div>
    </div>
  );
}
