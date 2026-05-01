"""Script temporal para diagnosticar la conexión Neo4j."""
import asyncio
from neo4j import AsyncGraphDatabase

URI = "neo4j+s://6396cf17.databases.neo4j.io"
USER = "6396cf17"
PASS = "_Q07Zm2X1WykUftlEErLjamIn_KuhRSlalivtuppRH0"

async def try_db(name):
    driver = AsyncGraphDatabase.driver(URI, auth=(USER, PASS))
    try:
        records, _, _ = await driver.execute_query(
            "RETURN 1 AS n", database_=name
        )
        print(f"  DB '{name}' -> OK")
        return True
    except Exception as e:
        print(f"  DB '{name}' -> {type(e).__name__}: {e}")
        return False
    finally:
        await driver.close()

async def show_databases():
    driver = AsyncGraphDatabase.driver(URI, auth=(USER, PASS))
    try:
        # system DB suele existir siempre
        records, _, _ = await driver.execute_query(
            "SHOW DATABASES", database_="system"
        )
        print("Bases de datos disponibles:")
        for r in records:
            print(f"  - {r['name']} (status={r.get('currentStatus', '?')})")
    except Exception as e:
        print(f"SHOW DATABASES (system): {type(e).__name__}: {e}")
    finally:
        await driver.close()

async def main():
    print("=== Probando conectividad ===")
    driver = AsyncGraphDatabase.driver(URI, auth=(USER, PASS))
    try:
        await driver.verify_connectivity()
        print("Conectividad SSL OK\n")
    except Exception as e:
        print(f"Conectividad FALLO: {e}\n")
    finally:
        await driver.close()

    print("=== Probando nombres de DB ===")
    for db_name in ["neo4j", "6396cf17", "system"]:
        await try_db(db_name)

    print("\n=== Listando DBs desde system ===")
    await show_databases()

asyncio.run(main())
