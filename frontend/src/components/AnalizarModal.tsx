import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { analizarImagen, type ResultadoAnalisis } from "@/api/analizar";
import { COLORES_ESTADO, formatearMonto } from "@/lib/validaciones-ui";
import type { EstadoValidacion } from "@/api/validaciones";
import { buscarClientes, type ClienteResumen } from "@/api/clientes";

interface Props {
  onAnalizado: (resultado: ResultadoAnalisis) => void;
  onCerrar: () => void;
}

export default function AnalizarModal({ onAnalizado, onCerrar }: Props) {
  const [busquedaCliente, setBusquedaCliente] = useState("");
  const [sugerencias, setSugerencias] = useState<ClienteResumen[]>([]);
  const [clienteSeleccionado, setClienteSeleccionado] = useState<ClienteResumen | null>(null);
  const [mostrarSugerencias, setMostrarSugerencias] = useState(false);
  const [archivo, setArchivo] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [analizando, setAnalizando] = useState(false);
  const [resultado, setResultado] = useState<ResultadoAnalisis | null>(null);
  const [error, setError] = useState<string | null>(null);

  const inputRef = useRef<HTMLInputElement>(null);
  const controladorRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (busquedaCliente.trim().length < 2) return;

    let cancelado = false;
    const timer = setTimeout(async () => {
      try {
        const resultados = await buscarClientes(busquedaCliente.trim());
        if (!cancelado) setSugerencias(resultados);
      } catch {
        if (!cancelado) setSugerencias([]);
      }
    }, 300);

    return () => {
      cancelado = true;
      clearTimeout(timer);
    };
  }, [busquedaCliente]);

  // Revoca la blob URL al cambiar la selección o al cerrar el modal
  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  function handleSeleccionarCliente(cliente: ClienteResumen) {
    setClienteSeleccionado(cliente);
    setBusquedaCliente("");
    setSugerencias([]);
    setMostrarSugerencias(false);
  }

  function handleLimpiarCliente() {
    setClienteSeleccionado(null);
    setBusquedaCliente("");
    setSugerencias([]);
  }

  function handleArchivoSeleccionado(file: File | null) {
    if (!file) return;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setArchivo(file);
    setPreviewUrl(URL.createObjectURL(file));
    setResultado(null);
    setError(null);
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    handleArchivoSeleccionado(e.dataTransfer.files?.[0] ?? null);
  }

  async function handleAnalizar() {
    if (!archivo) return;

    const codigoLimpio = clienteSeleccionado?.codigo_cliente ?? "";
    if (!codigoLimpio) {
      setError("Seleccioná un cliente antes de analizar.");
      return;
    }

    const controlador = new AbortController();
    controladorRef.current = controlador;
    const idTimeout = setTimeout(() => controlador.abort(), 90_000);

    setAnalizando(true);
    setError(null);
    setResultado(null);

    try {
      const datos = await analizarImagen(
        archivo,
        codigoLimpio,
        controlador.signal,
      );
      setResultado(datos);
      onAnalizado(datos);
    } catch (e) {
      if (e instanceof Error && e.name === "AbortError") {
        setError(
          "El análisis tardó demasiado o fue cancelado. Si ya lo enviaste, el resultado puede aparecer en el dashboard en unos segundos.",
        );
      } else {
        setError(
          e instanceof Error ? e.message : "Error al analizar la imagen.",
        );
      }
    } finally {
      clearTimeout(idTimeout);
      controladorRef.current = null;
      setAnalizando(false);
    }
  }

  function handleCancelar() {
    controladorRef.current?.abort();
  }

  function handleNuevoAnalisis() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setClienteSeleccionado(null);
    setBusquedaCliente("");
    setSugerencias([]);
    setArchivo(null);
    setPreviewUrl(null);
    setResultado(null);
    setError(null);
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/50 overflow-y-auto">
      <div
        className="flex min-h-full items-center justify-center p-4"
        onClick={(e) => {
          if (e.target === e.currentTarget) onCerrar();
        }}
      >
        <div className="bg-background rounded-lg border shadow-lg w-full max-w-lg">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-base font-semibold">Análisis manual</h2>
          <button
            onClick={onCerrar}
            className="text-muted-foreground hover:text-foreground transition-colors cursor-pointer text-lg leading-none"
            aria-label="Cerrar"
          >
            ✕
          </button>
        </div>

        <div className="px-6 py-5 space-y-5">
          {/* Formulario — solo si no hay resultado */}
          {!resultado && (
            <>
              {/* Selector de cliente */}
              <div className="space-y-1.5">
                <label className="text-sm font-medium">
                  Cliente <span className="text-destructive">*</span>
                </label>

                {clienteSeleccionado ? (
                  <div className="flex items-center justify-between px-3 py-2 border rounded-md bg-muted/30">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-sm font-medium truncate">
                        {clienteSeleccionado.razon_social}
                      </span>
                      <span className="text-xs text-muted-foreground font-mono shrink-0">
                        {clienteSeleccionado.codigo_cliente}
                      </span>
                    </div>
                    <button
                      onClick={handleLimpiarCliente}
                      disabled={analizando}
                      className="ml-2 text-muted-foreground hover:text-foreground transition-colors shrink-0 disabled:opacity-40"
                      aria-label="Limpiar selección"
                    >
                      ✕
                    </button>
                  </div>
                ) : (
                  <div className="relative">
                    <input
                      type="text"
                      value={busquedaCliente}
                      onChange={(e) => {
                        const valor = e.target.value;
                        setBusquedaCliente(valor);
                        setMostrarSugerencias(true);
                        if (valor.trim().length < 2) setSugerencias([]);
                      }}
                      onFocus={() => setMostrarSugerencias(true)}
                      onBlur={() =>
                        setTimeout(() => setMostrarSugerencias(false), 150)
                      }
                      placeholder="Buscar por código o razón social..."
                      disabled={analizando}
                      className="flex h-9 w-full rounded-md border border-input bg-background
                                 px-3 py-2 text-sm placeholder:text-muted-foreground
                                 focus-visible:outline-none focus-visible:ring-2
                                 focus-visible:ring-ring disabled:opacity-50"
                    />
                    {mostrarSugerencias && sugerencias.length > 0 && (
                      <ul className="absolute z-10 w-full bg-background border rounded-md shadow-md mt-1 max-h-48 overflow-y-auto">
                        {sugerencias.map((c) => (
                          <li
                            key={c.id}
                            onMouseDown={() => handleSeleccionarCliente(c)}
                            className="flex items-center justify-between px-3 py-2 text-sm cursor-pointer hover:bg-muted/50 transition-colors"
                          >
                            <span className="truncate">{c.razon_social}</span>
                            <span className="ml-2 font-mono text-xs text-muted-foreground shrink-0">
                              {c.codigo_cliente}
                            </span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </div>

              {/* Zona de drop */}
              <div
                onClick={() => !analizando && inputRef.current?.click()}
                onDrop={handleDrop}
                onDragOver={(e) => e.preventDefault()}
                className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors select-none
                  ${analizando ? "opacity-50" : "cursor-pointer hover:border-primary/50 hover:bg-muted/30"}`}
              >
                {previewUrl ? (
                  <img
                    src={previewUrl}
                    alt="Preview del comprobante"
                    className="max-h-48 mx-auto rounded object-contain"
                  />
                ) : (
                  <div className="space-y-1">
                    <p className="text-sm text-muted-foreground">
                      Arrastrá una imagen acá o hacé click para seleccionar
                    </p>
                    <p className="text-xs text-muted-foreground">
                      JPEG, PNG o WebP · máximo 10 MB
                    </p>
                  </div>
                )}
              </div>

              <input
                ref={inputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="hidden"
                onChange={(e) =>
                  handleArchivoSeleccionado(e.target.files?.[0] ?? null)
                }
              />

              {error && <p className="text-sm text-destructive">{error}</p>}

              {/* Acciones */}
              <div className="flex items-center gap-3">
                <Button
                  onClick={handleAnalizar}
                  disabled={!archivo || analizando}
                >
                  {analizando ? "Analizando..." : "Analizar"}
                </Button>
                {analizando && (
                  <Button variant="outline" size="sm" onClick={handleCancelar}>
                    Cancelar
                  </Button>
                )}
                {archivo && !analizando && (
                  <span className="text-xs text-muted-foreground">
                    {archivo.name} · {(archivo.size / 1024).toFixed(0)} KB
                  </span>
                )}
              </div>
            </>
          )}

          {/* Resultado */}
          {resultado && (
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <span
                  className={`inline-flex items-center rounded-full border px-3 py-1 text-sm font-medium ${COLORES_ESTADO[resultado.estado as EstadoValidacion] ?? "bg-gray-100 text-gray-700"}`}
                >
                  {resultado.estado.replace(/_/g, " ")}
                </span>
                {resultado.mp_status_code && (
                  <span className="text-xs text-muted-foreground">
                    MP {resultado.mp_status_code}
                  </span>
                )}
              </div>

              <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm border rounded-lg p-4">
                <dt className="text-muted-foreground">Código cliente</dt>
                <dd className="font-mono">{resultado.codigo_cliente}</dd>

                <dt className="text-muted-foreground">Nro. operación</dt>
                <dd className="font-mono">
                  {resultado.identificador_pago ?? "No detectado"}
                </dd>

                <dt className="text-muted-foreground">Monto</dt>
                <dd>{formatearMonto(resultado.monto_detectado)}</dd>

                <dt className="text-muted-foreground">CUIT destinatario</dt>
                <dd className="font-mono">
                  {resultado.cuit_destinatario_detectado ?? "No detectado"}
                </dd>

                {resultado.error && (
                  <>
                    <dt className="text-muted-foreground">Error</dt>
                    <dd className="text-destructive text-xs">
                      {resultado.error}
                    </dd>
                  </>
                )}
              </dl>

              <div className="flex gap-3">
                <Button variant="outline" onClick={handleNuevoAnalisis}>
                  Analizar otro
                </Button>
                <Button onClick={onCerrar}>Listo</Button>
              </div>
            </div>
          )}
        </div>
        </div>
      </div>
    </div>
  );
}
