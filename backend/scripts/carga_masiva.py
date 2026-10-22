"""
Carga masiva de comprobantes contra /api/analizar.
Mide tiempos y efectividad del pipeline OCR (Gemini + fallback Tesseract).

Uso:
    cd backend
    python scripts/carga_masiva.py --carpeta /ruta/a/imagenes --usuario admin@mail.com

Las validaciones creadas quedan en DB con codigo_cliente='CARGA_MASIVA'.
Para limpiarlas después:
    DELETE FROM auditoria  WHERE validacion_id IN (SELECT id FROM validaciones WHERE codigo_cliente = 'CARGA_MASIVA');
    DELETE FROM validaciones WHERE codigo_cliente = 'CARGA_MASIVA';
"""
import argparse
import getpass
import sys
import time
from pathlib import Path

import httpx

_BASE_URL          = "http://localhost:8000"
_CODIGO_CLIENTE    = "CARGA_MASIVA"
_EXTENSIONES       = {".jpg", ".jpeg", ".png", ".webp"}
_TIMEOUT_SEGUNDOS  = 90   # 30s LLM × 2 reintentos + Tesseract + margen


def _login(client: httpx.Client, usuario: str, password: str) -> None:
    resp = client.post("/auth/login", json={"email": usuario, "password": password})
    if resp.status_code != 200:
        print(f"Login fallido ({resp.status_code}): {resp.text}")
        sys.exit(1)
    print(f"Login OK como {usuario}\n")


def _analizar(client: httpx.Client, ruta: Path) -> tuple[dict, float]:
    mime_por_ext = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png",  ".webp": "image/webp",
    }
    mime = mime_por_ext.get(ruta.suffix.lower(), "image/jpeg")

    inicio = time.monotonic()
    try:
        with ruta.open("rb") as f:
            resp = client.post(
                "/api/analizar",
                data={"codigo_cliente": _CODIGO_CLIENTE},
                files={"archivo": (ruta.name, f, mime)},
                timeout=_TIMEOUT_SEGUNDOS,
            )
        elapsed = time.monotonic() - inicio
        if resp.status_code == 200:
            return resp.json(), elapsed
        return {"_error": f"HTTP {resp.status_code}: {resp.text[:120]}"}, elapsed
    except Exception as e:
        return {"_error": str(e)}, time.monotonic() - inicio


def _truncar(texto: str, largo: int) -> str:
    return texto[:largo - 2] + ".." if len(texto) > largo else texto


def main() -> None:
    parser = argparse.ArgumentParser(description="Carga masiva de comprobantes")
    parser.add_argument("--carpeta", required=True, help="Ruta a la carpeta de imágenes")
    parser.add_argument("--usuario", required=True, help="Email del admin")
    args = parser.parse_args()

    carpeta = Path(args.carpeta)
    if not carpeta.is_dir():
        print(f"Carpeta no encontrada: {carpeta}")
        sys.exit(1)

    imagenes = sorted(p for p in carpeta.iterdir() if p.suffix.lower() in _EXTENSIONES)
    if not imagenes:
        print("No hay imágenes válidas en la carpeta (JPG, PNG, WebP).")
        sys.exit(1)

    import os
    password = os.getenv("CARGA_PASSWORD") or getpass.getpass(f"Contraseña para {args.usuario}: ")

    resultados: list[dict] = []

    COL = (4, 36, 26, 20, 11, 8)
    encabezado = f"{'#':<{COL[0]}} {'Archivo':<{COL[1]}} {'Estado':<{COL[2]}} {'Banco':<{COL[3]}} {'Monto':>{COL[4]}} {'Tiempo':>{COL[5]}}"
    separador  = "-" * len(encabezado)

    with httpx.Client(base_url=_BASE_URL) as client:
        _login(client, args.usuario, password)
        print(f"Procesando {len(imagenes)} imágenes desde '{carpeta}'\n")
        print(encabezado)
        print(separador)

        for i, ruta in enumerate(imagenes, 1):
            datos, elapsed = _analizar(client, ruta)

            if "_error" in datos:
                estado = "ERROR_SCRIPT"
                banco  = "—"
                monto  = "—"
            else:
                estado = datos.get("estado") or "—"
                banco  = (datos.get("entidad_emisora") or "-").replace("_", " ")
                monto_val = datos.get("monto_detectado")
                monto  = f"${monto_val:,.0f}" if monto_val is not None else "-"

            nombre = _truncar(ruta.name, COL[1])
            print(
                f"{i:<{COL[0]}} {nombre:<{COL[1]}} {_truncar(estado, COL[2]):<{COL[2]}} "
                f"{_truncar(banco, COL[3]):<{COL[3]}} {monto:>{COL[4]}} {elapsed:>{COL[5] - 1}.1f}s"
            )

            resultados.append({
                "archivo": ruta.name,
                "estado":  estado,
                "banco":   banco,
                "monto":   monto,
                "tiempo":  elapsed,
                "error":   datos.get("_error"),
            })

    # ── Resumen ───────────────────────────────────────────────────────────────
    print(f"\n{'=' * len(separador)}")
    print("RESUMEN")
    print(f"{'=' * len(separador)}\n")

    tiempos = [r["tiempo"] for r in resultados]
    errores = [r for r in resultados if r["error"]]

    print(f"Total procesadas  : {len(resultados)}")
    print(f"Errores de script : {len(errores)}") 
    print(f"\nTiempos (segundos)")
    print(f"  Promedio : {sum(tiempos) / len(tiempos):.1f}s")
    print(f"  Mínimo   : {min(tiempos):.1f}s")
    print(f"  Máximo   : {max(tiempos):.1f}s")

    print("\nEstados:")
    estados: dict[str, int] = {}
    for r in resultados:
        estados[r["estado"]] = estados.get(r["estado"], 0) + 1
    for estado, count in sorted(estados.items(), key=lambda x: -x[1]):
        barra = "#" * count
        print(f"  {estado:<28} {count:>3}  ({count / len(resultados) * 100:.0f}%)  {barra}")

    print("\nBancos detectados:")
    bancos: dict[str, int] = {}
    for r in resultados:
        bancos[r["banco"]] = bancos.get(r["banco"], 0) + 1
    for banco, count in sorted(bancos.items(), key=lambda x: -x[1]):
        barra = "#" * count
        print(f"  {banco:<25} {count:>3}  ({count / len(resultados) * 100:.0f}%)  {barra}")

    if errores:
        print("\nErrores:")
        for r in errores:
            print(f"  {r['archivo']}: {r['error']}")

    print(f"\nValidaciones guardadas con codigo_cliente='{_CODIGO_CLIENTE}'")
    print("Para limpiar después:")
    print("  DELETE FROM auditoria WHERE validacion_id IN (SELECT id FROM validaciones WHERE codigo_cliente = 'CARGA_MASIVA');")
    print("  DELETE FROM validaciones WHERE codigo_cliente = 'CARGA_MASIVA';")
    print()


if __name__ == "__main__":
    main()
