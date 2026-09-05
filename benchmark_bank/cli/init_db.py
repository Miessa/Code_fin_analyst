"""Initialize or migrate the local ARSEL benchmark-bank database."""

import argparse

from benchmark_bank.storage import BenchmarkRepository


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default="benchmark_bank/data/benchmark_bank.duckdb")
    args = parser.parse_args(argv)
    with BenchmarkRepository(args.database) as repository:
        versions = repository.connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()
        print(f"Database: {args.database}")
        print(f"Migrations: {', '.join(str(row[0]) for row in versions)}")
        print(f"Current records: {repository.counts()}")


if __name__ == "__main__":
    main()
