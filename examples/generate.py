"""Reproducible synthetic examples; CSV needs only Python's standard library."""
from __future__ import annotations

import argparse
import csv
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
import random


def sales_rows():
    rng = random.Random(2025)
    rows = []
    for month in range(1, 13):
        for region in ("华东", "华南", "华北", "西部"):
            for product, price in (("基础版", 99), ("专业版", 299), ("企业版", 899)):
                for channel in ("线上", "合作伙伴"):
                    units = rng.randint(15, 70) + month * 3
                    revenue = units * price
                    cost = (Decimal(revenue) * Decimal("0.62")).quantize(Decimal("0.01"))
                    spend = "" if len(rows) % 17 == 0 else rng.randint(100, 1500)
                    rows.append({"date": f"2025-{month:02d}-01", "region": region,
                                 "product": product, "channel": channel, "units": units,
                                 "unit_price": price, "revenue": revenue, "cost": str(cost),
                                 "profit": str(Decimal(revenue) - cost), "marketing_spend": spend})
    return rows


def financial_rows():
    rng = random.Random(2026)
    prices = {"SYNTH_A": Decimal("100.00"), "SYNTH_B": Decimal("80.00")}
    rows = []
    day = date(2025, 1, 1)
    while day.year == 2025:
        if day.weekday() < 5:
            for symbol, previous in prices.items():
                change = Decimal(rng.randint(-180, 200)) / Decimal(10000)
                close = (previous * (1 + change)).quantize(Decimal("0.01"))
                rows.append({"date": day.isoformat(), "symbol": symbol,
                             "close": str(close), "volume": rng.randint(10000, 100000),
                             "currency": "SYNTH"})
                prices[symbol] = close
        day += timedelta(days=1)
    return rows


def generate(output: Path, file_format: str = "csv") -> list[Path]:
    datasets = {"sales": sales_rows(), "financial_timeseries": financial_rows()}
    extensions = ("csv", "xlsx", "parquet") if file_format == "all" else ("csv",)
    paths = [output / f"{name}.{ext}" for name in datasets for ext in extensions]
    if any(path.exists() for path in paths):
        raise FileExistsError("Example files already exist. Choose a new --output directory; no files were overwritten.")
    pd = None
    if file_format == "all":
        # Resolve optional dependencies before producing any partial output.
        import pandas as pd
        import openpyxl  # noqa: F401
        import pyarrow  # noqa: F401
    output.mkdir(parents=True, exist_ok=True)
    for name, rows in datasets.items():
        csv_path = output / f"{name}.csv"
        with csv_path.open("x", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        if pd is not None:
            frame = pd.read_csv(csv_path)
            frame.to_excel(output / f"{name}.xlsx", index=False)
            frame.to_parquet(output / f"{name}.parquet", index=False)
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "generated")
    parser.add_argument("--format", choices=("csv", "all"), default="csv")
    args = parser.parse_args()
    try:
        for path in generate(args.output, args.format):
            print(path)
    except (FileExistsError, ImportError) as error:
        parser.exit(1, f"{error}\nFor XLSX/Parquet install backend/requirements.txt in a virtual environment.\n")


if __name__ == "__main__":
    main()
