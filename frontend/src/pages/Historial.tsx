import { useState, useEffect, useMemo } from "react";
import { ChevronDownIcon, ChevronUpIcon } from "@/components/icons";
import FiltrosEstadisticas from "@/components/FiltrosEstadisticas";
import {
  FILTROS_INICIALES,
  type FiltrosEstadisticasValues,
} from "@/lib/filtros-estadisticas";
import TablaValidaciones from "@/components/TablaValidaciones";
import {
  listarValidaciones,
  listarBancos,
  obtenerMetricas,
  type Validacion,
  type Metricas,
} from "@/api/validaciones";
import {
  COLORES_ESTADO,
  COLORES_CANAL,
  LABEL_CANAL,
  ESTADOS_ORDEN,
  LABEL_ESTADO,
} from "@/lib/validaciones-ui";

// ---------------------------------------------------------------------------
// Componente
// ---------------------------------------------------------------------------

export default function Historial() {
  const [metricas, setMetricas] = useState<Metricas | null>(null);
  const [validaciones, setValidaciones] = useState<Validacion[]>([]);
  const [filtros, setFiltros] = useState(FILTROS_INICIALES);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [bancos, setBancos] = useState<string[]>([]);
  const [kpisAbiertos, setKpisAbiertos] = useState(false);

  useEffect(() => {
    cargarTodo(FILTROS_INICIALES);
    listarBancos()
      .then(setBancos)
      .catch((e) => console.error("[Historial] Error al cargar bancos:", e));
  }, []);

  async function cargarTodo(f: FiltrosEstadisticasValues) {
    setCargando(true);
    setError(null);
    try {
      const [m, v] = await Promise.all([
        obtenerMetricas(),
        listarValidaciones({
          estado: f.estado || undefined,
          canal: f.canal || undefined,
          fecha_desde: f.fecha_desde || undefined,
          fecha_hasta: f.fecha_hasta || undefined,
          fecha_mod_desde: f.fecha_mod_desde || undefined,
          fecha_mod_hasta: f.fecha_mod_hasta || undefined,
          codigo_cliente: f.codigo_cliente || undefined,
          numero_operacion: f.numero_operacion || undefined,
          usuario: f.usuario || undefined,
          entidad_emisora: f.banco || undefined,
          limit: 500,
        }),
      ]);
      setMetricas(m);
      setValidaciones(v);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Error al cargar historial.",
      );
    } finally {
      setCargando(false);
    }
  }

  function handleAplicar() {
    cargarTodo(filtros);
  }

  function handleLimpiar() {
    setFiltros(FILTROS_INICIALES);
    cargarTodo(FILTROS_INICIALES);
  }

  function handleValidacionGuardada(actualizada: Validacion) {
    setValidaciones((prev) =>
      prev.map((v) => (v.id === actualizada.id ? actualizada : v)),
    );
  }

  const pctAprobacion = useMemo(() => {
    if (!metricas || metricas.total === 0) return 0;
    return Math.round(
      ((metricas.por_estado["APROBADO"] ?? 0) / metricas.total) * 100,
    );
  }, [metricas]);

  const hayFiltros = Object.values(filtros).some(Boolean);

  return (
    <>
      <main className="px-3 py-4 sm:px-6 sm:py-8 space-y-8">
        <h2 className="text-base font-semibold">Historial</h2>

        {error && <p className="text-sm text-destructive">{error}</p>}

        {/* ── KPIs globales ────────────────────────────────────────────── */}
        {metricas && (
          <section className="space-y-3">
            {/* Trigger — solo mobile */}
            <div className="flex items-center justify-between md:hidden">
              <button
                onClick={() => setKpisAbiertos((v) => !v)}
                className="flex items-center gap-1.5 text-sm font-medium text-foreground"
              >
                Resumen
                {kpisAbiertos ? <ChevronUpIcon /> : <ChevronDownIcon />}
              </button>
              <span className="text-sm text-muted-foreground">
                {metricas.total} · {pctAprobacion}% aprobados
              </span>
            </div>

            {/* Contenido — siempre visible en desktop */}
            <div className={`${kpisAbiertos ? "block" : "hidden"} md:block space-y-5`}>
              <div className="space-y-2">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Estados
                </p>
                <div className="flex items-center gap-2 flex-wrap">
                  <div className="border rounded-lg px-5 py-3">
                    <div className="flex items-center gap-4">
                      <div className="text-center">
                        <p className="text-2xl font-bold">{metricas.total}</p>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          Totales
                        </p>
                      </div>
                      <div className="w-px h-10 bg-border" />
                      <div className="text-center">
                        <p className="text-2xl font-bold">{pctAprobacion}%</p>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          Aprobados
                        </p>
                      </div>
                    </div>
                  </div>
                  {ESTADOS_ORDEN.map((estado) => (
                    <div
                      key={estado}
                      className={`border rounded-lg px-4 py-3 text-center min-w-[90px] ${COLORES_ESTADO[estado]}`}
                    >
                      <p className="text-2xl font-bold">
                        {metricas.por_estado[estado] ?? 0}
                      </p>
                      <p className="text-xs mt-0.5">{LABEL_ESTADO[estado]}</p>
                    </div>
                  ))}
                </div>
              </div>

              {Object.keys(metricas.por_banco).length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    Bancos
                  </p>
                  <div className="flex items-center gap-2 flex-wrap">
                    {Object.entries(metricas.por_banco).map(([banco, cantidad]) => (
                      <span
                        key={banco}
                        className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium bg-slate-100 text-slate-700 border-slate-200"
                      >
                        {banco.replace(/_/g, " ")}: {cantidad}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div className="space-y-2">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Canales
                </p>
                <div className="flex items-center gap-2 flex-wrap">
                  {(["WhatsApp", "MANUAL"] as const).map((canal) => (
                    <span
                      key={canal}
                      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium ${COLORES_CANAL[canal] ?? ""}`}
                    >
                      {LABEL_CANAL[canal]}: {metricas.por_canal[canal] ?? 0}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </section>
        )}

        {/* ── Filtros ──────────────────────────────────────────────────── */}
        <section className="space-y-3">
          <FiltrosEstadisticas
            filtros={filtros}
            bancos={bancos}
            onChange={setFiltros}
            cargando={cargando}
            onAplicar={handleAplicar}
            onLimpiar={handleLimpiar}
            hayFiltros={hayFiltros}
          />
        </section>

        {/* ── Tabla ────────────────────────────────────────────────────── */}
        {!cargando && (
          <section className="space-y-3">
            <p className="text-sm text-muted-foreground">
              {validaciones.length} resultado
              {validaciones.length !== 1 ? "s" : ""}
              {hayFiltros ? " con los filtros aplicados" : ""}
            </p>
            {validaciones.length === 500 && (
              <p className="text-xs text-amber-600">
                Mostrando los primeros 500 resultados — aplicá filtros para acotar.
              </p>
            )}

            <TablaValidaciones
              validaciones={validaciones}
              mensajeVacio={
                hayFiltros
                  ? "Sin resultados para los filtros aplicados."
                  : "No hay validaciones aún."
              }
              onActualizada={handleValidacionGuardada}
              onEliminada={(id) => {
                setValidaciones((prev) => prev.filter((v) => v.id !== id));
                obtenerMetricas().then(setMetricas).catch(() => {});
              }}
              onError={setError}
            />
          </section>
        )}
      </main>
    </>
  );
}
