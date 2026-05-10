"""Diagnostica la conectividad con Neo4j y los nombres de base de datos.

Uso:
    python -m test.scripts.diagnose_neo4j
"""

import asyncio

from neo4j import AsyncGraphDatabase


URI = "neo4j+s://6396cf17.databases.neo4j.io"
USER = "6396cf17"
PASS = "_Q07Zm2X1WykUftlEErLjamIn_KuhRSlalivtuppRH0"


async def try_db(name: str) -> bool:
    driver = AsyncGraphDatabase.driver(URI, auth=(USER, PASS))
    try:
        await driver.execute_query("RETURN 1 AS n", database_=name)
        print(f"  DB '{name}' -> OK")
        return True
    except Exception as exc:
        print(f"  DB '{name}' -> {type(exc).__name__}: {exc}")
        return False
    finally:
        await driver.close()


async def show_databases() -> None:
    driver = AsyncGraphDatabase.driver(URI, auth=(USER, PASS))
    try:
        records, _, _ = await driver.execute_query(
            "SHOW DATABASES", database_="system"
        )
        print("Bases de datos disponibles:")
        for record in records:
            print(f"  - {record['name']} (status={record.get('currentStatus', '?')})")
    except Exception as exc:
        print(f"SHOW DATABASES (system): {type(exc).__name__}: {exc}")
    finally:
        await driver.close()


async def main() -> None:
    print("=== Probando conectividad ===")
    driver = AsyncGraphDatabase.driver(URI, auth=(USER, PASS))
    try:
        await driver.verify_connectivity()
        print("Conectividad SSL OK\n")
    except Exception as exc:
        print(f"Conectividad FALLO: {exc}\n")
    finally:
        await driver.close()

    print("=== Probando nombres de DB ===")
    for db_name in ["neo4j", "6396cf17", "system"]:
        await try_db(db_name)

    print("\n=== Listando DBs desde system ===")
    await show_databases()


if __name__ == "__main__":
    asyncio.run(main())