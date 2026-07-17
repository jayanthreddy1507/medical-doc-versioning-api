"""Utility script to inspect the contents of the local SQLite database (affine.db)."""

import sqlite3

DB_PATH = "data/affine.db"


def inspect():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        print("=" * 80)
        print("DATABASE SUMMARY")
        print("=" * 80)

        # 1. Show table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in cursor.fetchall()]
        print(f"Tables in Database: {', '.join(tables)}")

        # 2. Print row counts
        for table in ["documents", "versions", "nodes", "selections", "generations"]:
            if table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table};")
                count = cursor.fetchone()[0]
                print(f" - {table}: {count} records")

        # 3. Print documents & versions details
        if "documents" in tables:
            print("\n" + "=" * 80)
            print("INGESTED DOCUMENTS & VERSIONS")
            print("=" * 80)
            cursor.execute(
                """
                SELECT d.id, d.filename, v.version_number, v.node_count, v.created_at
                FROM documents d
                JOIN versions v ON d.id = v.document_id
                ORDER BY d.id, v.version_number;
            """
            )
            rows = cursor.fetchall()
            print(
                f"{'Doc ID':<8} | {'Filename':<25} | {'Version':<8} | {'Node Count':<10} | {'Ingested At':<20}"
            )
            print("-" * 80)
            for row in rows:
                print(
                    f"{row[0]:<8} | {row[1]:<25} | {row[2]:<8} | {row[3]:<10} | {row[4]:<20}"
                )

        # 4. Print selections details
        if "selections" in tables:
            print("\n" + "=" * 80)
            print("SELECTIONS")
            print("=" * 80)
            cursor.execute("SELECT id, name, created_at FROM selections;")
            rows = cursor.fetchall()
            print(f"{'Sel ID':<8} | {'Selection Name':<30} | {'Created At':<20}")
            print("-" * 80)
            for row in rows:
                print(f"{row[0]:<8} | {row[1]:<30} | {row[2]:<20}")

        # 5. Print generations details
        if "generations" in tables:
            print("\n" + "=" * 80)
            print("GENERATED QA TEST CASES PREVIEW")
            print("=" * 80)
            cursor.execute(
                """
                SELECT g.id, s.name, g.test_cases, g.created_at
                FROM generations g
                JOIN selections s ON g.selection_id = s.id
                LIMIT 3;
            """
            )
            rows = cursor.fetchall()
            for row in rows:
                print(f"Generation ID: {row[0]}")
                print(f"Selection Name: {row[1]}")
                print(f"Generated At: {row[3]}")
                try:
                    import json

                    cases = json.loads(row[2])
                    print("Test Cases:")
                    for tc in cases.get("test_cases", [])[:2]:
                        print(f"  - [{tc['id']}] {tc['name']}")
                        print(f"    Expected: {tc['expected_result']}")
                except Exception:
                    print(f"  Raw: {row[2][:200]}...")
                print("-" * 80)

        conn.close()

    except sqlite3.OperationalError as e:
        print(f"❌ Database error: {e}")
        print("   Make sure the database file 'data/affine.db' exists.")


if __name__ == "__main__":
    inspect()
