import { useState, useEffect, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { ChevronLeftIcon, ChevronRightIcon, ChevronDownIcon, ChevronUpIcon } from "@/components/icons";
import {
  listarValidaciones,
  listarBancos,
  type Validacion,
  type EstadoValidacion,
  type CanalValidacion,
} from "@/api/validaciones";
import AnalizarModal from "@/components/AnalizarModal";
import FiltrosDashboard from "@/components/FiltrosDashboard";
import {
  FILTROS_INICIALES,
  type FiltrosDashboardValues,
} from "@/lib/filtros-dashboard";
import TablaValidaciones from "@/components/TablaValidaciones";
import { type ResultadoAnalisis } from "@/api/analizar";
import {
  formatearFecha,
  COLORES_ESTADO,
  COLORES_CANAL,
  LABEL_CANAL,
  ESTADOS_ORDEN,
  LABEL_ESTADO,
} from "@/lib/validaciones-ui";

// ---------------------------------------------------------------------------
// Helpers locales
// ---------------------------------------------------------------------------

const PAGE_SIZE = 100;

function hoyLocal(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// ---------------------------------------------------------------------------
// Componente
// ---------------------------------------------------------------------------

export default function Dashboard() {
  // todasLasValidaciones: lista completa, fuente de verdad.
  const [todasLasValidaciones, setTodasLasValidaciones] = useState<Validacion[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [filtros, setFiltros] = useState(FILTROS_INICIALES);
  const [mostrarAnalizarModal, setMostrarAnalizarModal] = useState(false);
  const [paginaActual, setPaginaActual] = useState(1);
  const [bancos, setBancos] = useState<string[]>([]);
  const [kpisAbiertos, setKpisAbiertos] = useState(false);

  function handleFiltroChange(cambio: Partial<FiltrosDashboardValues>) {
    setFiltros((f) => ({ ...f, ...cambio }));
    setPaginaActual(1);
  }

  function handleLimpiarFiltros() {
    setFiltros(FILTROS_INICIALES);
    setPaginaActual(1);
  }

  // validacionesMostradas: derivado de todasLasValidaciones + filtros.
  const validacionesMostradas = useMemo(() => {
    return todasLasValidaciones.filter((v) => {
      if (filtros.estado && v.estado !== filtros.estado) return false;
      if (filtros.canal && v.canal !== filtros.canal) return false;
      if (filtros.cliente) {
        const term = filtros.cliente.toLowerCase();
        if (!v.codigo_cliente?.toLowerCase().includes(term)) return false;
      }
      if (filtros.numero_operacion) {
        const term = filtros.numero_operacion.toLowerCase();
        if (!v.identificador_pago?.toLowerCase().includes(term)) return false;
      }
      if (filtros.usuario) {
        const term = filtros.usuario.toLowerCase();
        const usuario =
          v.canal === "MANUAL" ? v.creado_por_nombre : v.codigo_vendedor;
        if (!usuario?.toLowerCase().includes(term)) return false;
      }
      if (filtros.banco && v.entidad_emisora !== filtros.banco) return false;
      return true;
    });
  }, [todasLasValidaciones, filtros]);

  const kpiEstado = useMemo(() => {
    const conteo: Partial<Record<EstadoValidacion, number>> = {};
    for (const v of todasLasValidaciones) {
      conteo[v.estado] = (conteo[v.estado] ?? 0) + 1;
    }
    return conteo;
  }, [todasLasValidaciones]);

  const kpiBanco = useMemo(() => {
    const conteo: Record<string, number> = {};
    for (const v of todasLasValidaciones) {
      if (v.entidad_emisora) {
        conteo[v.entidad_emisora] = (conteo[v.entidad_emisora] ?? 0) + 1;
      }
    }
    return conteo;
  }, [todasLasValidaciones]);

  const kpiCanal = useMemo(() => {
    const conteo: Partial<Record<CanalValidacion, number>> = {};
    for (const v of todasLasValidaciones) {
      conteo[v.canal] = (conteo[v.canal] ?? 0) + 1;
    }
    return conteo;
  }, [todasLasValidaciones]);

  const pctAprobacion = useMemo(() => {
    if (todasLasValidaciones.length === 0) return 0;
    return Math.round(
      ((kpiEstado["APROBADO"] ?? 0) / todasLasValidaciones.length) * 100,
    );
  }, [todasLasValidaciones, kpiEstado]);

  const ultimaActividad = useMemo(() => {
    return todasLasValidaciones.reduce<string | null>((max, v) => {
      if (!v.procesado_en) return max;
      return !max || v.procesado_en > max ? v.procesado_en : max;
    }, null);
  }, [todasLasValidaciones]);

  // ── Efecto 1: carga inicial — solo validaciones de hoy ─────────────────
  useEffect(() => {
    const hoy = hoyLocal();
    listarValidaciones({ fecha_desde: hoy, fecha_hasta: hoy, limit: 2500 })
      .then((v) => setTodasLasValidaciones(v))
      .catch((e) =>
        console.error("[Dashboard] Error al cargar validaciones:", e),
      );

    listarBancos()
      .then(setBancos)
      .catch((e) => console.error("[Dashboard] Error al cargar bancos:", e));
  }, []);

  // ── Efecto 2: SSE — recibe eventos tipados del servidor vía Redis Pub/Sub ──
  // "validacion": cualquier validación guardada (WhatsApp o manual) → recarga tabla.
  useEffect(() => {
    const source = new EventSource("/api/eventos");

    source.addEventListener("validacion", async () => {
      try {
        const hoy = hoyLocal();
        const validaciones = await listarValidaciones({
          fecha_desde: hoy,
          fecha_hasta: hoy,
          limit: 2500,
        });
        setTodasLasValidaciones(validaciones);
      } catch {
        // error transitorio de red
      }
    });

    return () => source.close();
  }, []);

  // ── Handlers ────────────────────────────────────────────────────────────

  function handleAnalizado(resultado: ResultadoAnalisis) {
    const nueva: Validacion = {
      id: resultado.id,
      run_id: null,
      respuesta_id: null,
      codigo_cliente: resultado.codigo_cliente,
      codigo_vendedor: null,
      canal: resultado.canal as CanalValidacion,
      estado: resultado.estado as EstadoValidacion,
      identificador_pago: resultado.identificador_pago,
      monto_detectado: resultado.monto_detectado,
      cuit_destinatario_detectado: resultado.cuit_destinatario_detectado,
      es_comprobante_valido: resultado.es_comprobante_valido,
      mp_status_code: resultado.mp_status_code,
      error: resultado.error,
      procesado_en: resultado.procesado_en,
      fecha_modificacion: null,
      modificado_por_nombre: null,
      creado_por_nombre: resultado.creado_por_nombre,
      imagen_path: resultado.imagen_path,
      observaciones: resultado.observaciones,
      estado_inicial: resultado.estado_inicial,
      entidad_emisora: resultado.entidad_emisora,
    };
    setTodasLasValidaciones((prev) => [nueva, ...prev]);
  }

  function handleValidacionGuardada(actualizada: Validacion) {
    setTodasLasValidaciones((prev) =>
      prev.map((v) => (v.id === actualizada.id ? actualizada : v)),
    );
  }

  // ── Valores derivados ───────────────────────────────────────────────────
  const hayResultados = todasLasValidaciones.length > 0;
  const hayFiltros = Object.values(filtros).some(Boolean);

  const totalPaginas = Math.max(
    1,
    Math.ceil(validacionesMostradas.length / PAGE_SIZE),
  );
  const paginaClamped = Math.min(paginaActual, totalPaginas);
  const validacionesPagina = validacionesMostradas.slice(
    (paginaClamped - 1) * PAGE_SIZE,
    paginaClamped * PAGE_SIZE,
  );

  // ── Render ──────────────────────────────────────────────────────────────
  return (
    <>
      <main className="px-3 py-4 sm:px-6 sm:py-8 space-y-8">
        <h2 className="text-base font-semibold">Gestión del día</h2>

        {/* ── Panel de acción ──────────────────────────────────────────── */}
        <section className="space-y-3">
          <div className="space-y-2">
            <Button
              variant="outline"
              onClick={() => setMostrarAnalizarModal(true)}
            >
              Análisis manual
            </Button>
          </div>

          <p className="text-xs text-muted-foreground">
            Los comprobantes recibidos por WhatsApp se procesan automáticamente.
            Usá "Análisis manual" para cargar un comprobante individual.
          </p>

          {error && <p className="text-sm text-destructive">{error}</p>}
        </section>

        {/* ── KPIs del día ─────────────────────────────────────────────── */}
        <section className="space-y-3">
          {/* Trigger — solo mobile */}
          <div className="flex items-center justify-between md:hidden">
            <button
              onClick={() => setKpisAbiertos((v) => !v)}
              className="flex items-center gap-1.5 text-sm font-medium text-foreground"
            >
              Resumen del día
              {kpisAbiertos ? <ChevronUpIcon /> : <ChevronDownIcon />}
            </button>
            <span className="text-sm text-muted-foreground">
              {todasLasValidaciones.length} · {pctAprobacion}% aprobados
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
                      <p className="text-2xl font-bold">
                        {todasLasValidaciones.length}
                      </p>
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
                    <p className="text-2xl font-bold">{kpiEstado[estado] ?? 0}</p>
                    <p className="text-xs mt-0.5">{LABEL_ESTADO[estado]}</p>
                  </div>
                ))}
              </div>
            </div>

            {Object.keys(kpiBanco).length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Bancos
                </p>
                <div className="flex items-center gap-2 flex-wrap">
                  {Object.entries(kpiBanco).map(([banco, cantidad]) => (
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
                    {LABEL_CANAL[canal]}: {kpiCanal[canal] ?? 0}
                  </span>
                ))}
              </div>
            </div>

            {ultimaActividad && (
              <p className="text-xs text-muted-foreground">
                Último comprobante: {formatearFecha(ultimaActividad)}
              </p>
            )}
          </div>
        </section>

        {/* ── Tabla de resultados ──────────────────────────────────────── */}
        {hayResultados && (
          <section className="space-y-4">
            <FiltrosDashboard
              filtros={filtros}
              bancos={bancos}
              onChange={handleFiltroChange}
              onLimpiar={handleLimpiarFiltros}
              totalMostrados={validacionesMostradas.length}
              totalTodos={todasLasValidaciones.length}
              hayFiltros={hayFiltros}
            />

            <TablaValidaciones
              validaciones={validacionesPagina}
              mensajeVacio="Sin resultados para los filtros aplicados."
              mostrarProcesado={false}
              onActualizada={handleValidacionGuardada}
              onEliminada={(id) =>
                setTodasLasValidaciones((prev) =>
                  prev.filter((v) => v.id !== id),
                )
              }
              onError={setError}
            />

            {/* ── Paginación ───────────────────────────────────────────── */}
            {totalPaginas > 1 && (
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">
                  Página {paginaClamped} de {totalPaginas}
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
          </section>
        )}

        {/* ── Estado vacío ─────────────────────────────────────────────── */}
        {!hayResultados && (
          <p className="text-center text-muted-foreground py-16">
            Sin comprobantes procesados hoy. Los mensajes de WhatsApp se procesan
            automáticamente, o usá "Análisis manual" para subir uno.
          </p>
        )}
      </main>

      {/* ── Modal de análisis manual ──────────────────────────────────────── */}
      {mostrarAnalizarModal && (
        <AnalizarModal
          onAnalizado={handleAnalizado}
          onCerrar={() => setMostrarAnalizarModal(false)}
        />
      )}
    </>
  );
}
