"""
Script de setup: crea el primer admin en la DB.

Uso:
    cd backend
    python scripts/crear_admin.py --email admin@empresa.com --nombre "Juan Pérez" --password "miClave123"

    # O sin argumentos para que pregunte interactivamente:
    python scripts/crear_admin.py

Por qué es un script y no un endpoint HTTP:
  Crear un admin es una operación de bootstrap que solo hace un operador
  técnico una vez (o pocas veces). Un endpoint HTTP requeriría proteger
  "crear primer admin cuando no hay ninguno" con lógica especial y sería
  una superficie de ataque potencial. Un script CLI que corre localmente
  con acceso a la DB es más seguro y simple.
"""
import argparse
import getpass
import sys
import os

# Agregar backend/ al path para poder importar los módulos del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import config
from db.queries_admins import crear_admin, obtener_admin_por_email
import psycopg2
import psycopg2.pool
from services.auth_service import hash_password, validar_fortaleza_password


def main() -> None:
    parser = argparse.ArgumentParser(description="Crear un admin en la DB")
    parser.add_argument("--email",  help="Email del admin")
    parser.add_argument("--nombre", help="Nombre completo del admin")
    parser.add_argument("--password", help="Contraseña (si no se pasa, se pide interactivamente)")
    parser.add_argument("--superadmin", action="store_true", help="Crear como superadmin")
    args = parser.parse_args()

    email  = args.email  or input("Email:  ").strip()
    nombre = args.nombre or input("Nombre: ").strip()

    if args.password:
        password = args.password
    else:
        # getpass oculta la contraseña mientras se escribe (no aparece en pantalla)
        password  = getpass.getpass("Contraseña: ")
        password2 = getpass.getpass("Repetir contraseña: ")
        if password != password2:
            print("ERROR: las contraseñas no coinciden.")
            sys.exit(1)

    if not email or not nombre or not password:
        print("ERROR: email, nombre y contraseña son obligatorios.")
        sys.exit(1)

    try:
        validar_fortaleza_password(password)
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # Crear pool directo (sin FastAPI)
    url = config.database_url_sync.replace("postgresql+psycopg2://", "postgresql://")
    pool = psycopg2.pool.ThreadedConnectionPool(minconn=1, maxconn=2, dsn=url)

    # Verificar si ya existe
    existente = obtener_admin_por_email(pool, config.tenant_id, email)
    if existente:
        print(f"Ya existe un admin con email '{email}' en el tenant '{config.tenant_id}'.")
        sys.exit(1)

    password_hash = hash_password(password)
    admin_id = crear_admin(pool, config.tenant_id, email, nombre, password_hash, es_superadmin=args.superadmin)

    pool.closeall()
    print(f"Admin creado con ID: {admin_id}")
    print(f"  Email:      {email}")
    print(f"  Nombre:     {nombre}")
    print(f"  Tenant:     {config.tenant_id}")
    print(f"  Superadmin: {'sí' if args.superadmin else 'no'}")


if __name__ == "__main__":
    main()
