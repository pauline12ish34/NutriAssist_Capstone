"""Turn the WHO Child Growth Standards expanded tables into the one CSV the screening code reads.

    python scripts/build_who_tables.py

Input: the eight z-score "expanded tables" downloaded from
https://www.who.int/tools/child-growth-standards/standards (data/raw/who_growth_standards/):
weight-for-age and length/height-for-age by age in days (0-1856), weight-for-length (45-110 cm,
children under 2) and weight-for-height (65-120 cm, from 2 years) in 0.1 cm steps, for boys and girls.

Output: data/reference/who_growth_lms.csv with one row per indicator, sex and age/length:
the L, M, S parameters, plus WHO's printed -3, -2, +2 and +3 SD values, which the tests use to
check the z-score code against WHO's own numbers.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

RAW = Path("data/raw/who_growth_standards")
OUT = Path("data/reference/who_growth_lms.csv")
FILES = {   # indicator -> file name pattern ({sex} = boys / girls)
    "wfa": "wfa-{sex}-zscore-expanded-tables.xlsx",
    "hfa": "lhfa-{sex}-zscore-expanded-tables.xlsx",
    "wfl": "wfl-{sex}-zscore-expanded-table.xlsx",
    "wfh": "wfh-{sex}-zscore-expanded-tables.xlsx",
}
SEXES = {"boys": "male", "girls": "female"}
KEEP = {"L": "L", "M": "M", "S": "S", "SD3neg": "sd3neg", "SD2neg": "sd2neg", "SD2": "sd2", "SD3": "sd3"}


def main() -> None:
    tables = []
    for indicator, pattern in FILES.items():
        for file_sex, sex in SEXES.items():
            table = pd.read_excel(RAW / pattern.format(sex=file_sex))
            x = table.columns[0]                     # Day, Length or Height
            table = table.rename(columns={x: "x", **KEEP})[["x", *KEEP.values()]]
            table.insert(0, "sex", sex)
            table.insert(0, "indicator", indicator)
            tables.append(table)
    result = pd.concat(tables, ignore_index=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT, index=False)
    print(f"{len(result)} rows -> {OUT}")
    print(result.groupby(["indicator", "sex"])["x"].agg(["min", "max", "count"]))


if __name__ == "__main__":
    main()
