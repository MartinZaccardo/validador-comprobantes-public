"""
Entry point para correr el servidor.

Uso:
    python run.py          # desarrollo (reload activado, host localhost)
    python run.py --prod   # producción (sin reload, host 0.0.0.0)

En Railway el puerto lo asigna la plataforma via $PORT.
En desarrollo local se usa el puerto 8000 por defecto.
"""
import logging
import os
import sys

import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)

if __name__ == "__main__":
    prod = "--prod" in sys.argv
    port = int(os.environ.get("PORT", "8000"))
    host = "0.0.0.0" if prod else "127.0.0.1"  # nosec B104
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=not prod,
        log_level="info",
        proxy_headers=prod,
        forwarded_allow_ips="*",
    )
