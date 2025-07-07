#!/usr/bin/env python3
"""Check if BIRD-CRITIC dataset contains golden SQL."""

try:
    from datasets import load_dataset

    print("Loading BIRD-CRITIC dataset...")
    ds = load_dataset(
        "birdsql/bird-critic-1.0-postgresql", split="pg", trust_remote_code=True
    )

    print(f"\nDataset size: {len(ds)} records")
    print(f"Fields in dataset: {list(ds[0].keys())}")

    # Check first few records for sol_sql
    print("\nChecking first 5 records for sol_sql field:")
    for i in range(min(5, len(ds))):
        record = ds[i]
        instance_id = record.get("instance_id", "Unknown")
        has_sol_sql = "sol_sql" in record
        sol_sql_value = record.get("sol_sql") if has_sol_sql else None
        sol_sql_present = sol_sql_value is not None and sol_sql_value != ""

        print(f"\nRecord {i} (ID: {instance_id}):")
        print(f"  - Has 'sol_sql' field: {has_sol_sql}")
        print(f"  - sol_sql value present: {sol_sql_present}")
        if sol_sql_present:
            print(f"  - sol_sql preview: {sol_sql_value[:100]}...")

    # Count how many records have sol_sql
    count_with_sol_sql = sum(1 for r in ds if r.get("sol_sql"))
    print(f"\nTotal records with sol_sql: {count_with_sol_sql}/{len(ds)}")

except ImportError:
    print("Error: 'datasets' package not installed.")
    print("Install it with: pip install datasets")
except Exception as e:
    print(f"Error loading dataset: {e}")
