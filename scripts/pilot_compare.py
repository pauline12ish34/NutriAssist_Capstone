"""Compare the growth check with the CHW's own classification for real, anonymised pilot measurements.

Copy data/pilot/chw_measurements_template.csv to data/pilot/chw_measurements.csv (not committed) and add one row
per child, without names:

    child               Child 1, Child 2, ...
    age_months          0 to 59
    sex                 male or female
    weight_kg           for example 9.4
    height_cm           length or height, empty if not measured
    muac_cm             empty if not measured (MUAC is used from 6 months)
    oedema              yes or no (swelling of both feet)
    measured_lying      yes, no or empty (empty: lying under 2 years, standing from 2 years)
    chw_classification  what the CHW decided in the usual way: normal, moderate or severe
                        (green, yellow and red on the MUAC tape are accepted too)
    source              in_person (the CHW used the app with the researcher) or shared (the CHW shared her records)
    date                date of the measurement, YYYY-MM-DD

Run:  .venv312/Scripts/python.exe scripts/pilot_compare.py [path to the csv]

It prints one row per child (z-scores, the application's level, the CHW's classification and whether they agree)
and writes the same table to outputs/pilot/growth_check_vs_chw.csv for Table 4.10 and Appendix D.
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nutriassist.screening.screening import ScreeningInputError, ScreeningRequest, screen  # noqa: E402

CHW_LEVEL = {"normal": "normal", "green": "normal", "moderate": "moderate", "yellow": "moderate", "mam": "moderate",
             "follow-up": "moderate", "severe": "severe", "red": "severe", "sam": "severe"}
APP_NAME = {"normal": "normal", "moderate": "follow-up (moderate)", "severe": "severe", "check": "check measurements"}


def number(value):
    value = (value or "").strip().replace(",", ".")
    return float(value) if value else None


def yes(value):
    return (value or "").strip().lower() in ("yes", "y", "true", "1", "yego")


def main(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    if not rows:
        sys.exit(f"No children in {path}: add one row per child first.")
    out, agree, compared = [], 0, 0
    for r in rows:
        lying = (r.get("measured_lying") or "").strip()
        request = ScreeningRequest(age_months=int(number(r["age_months"])), sex=r["sex"].strip().lower(),
                                   weight_kg=number(r["weight_kg"]), height_cm=number(r.get("height_cm")),
                                   muac_cm=number(r.get("muac_cm")), oedema=yes(r.get("oedema")),
                                   measured_lying=None if not lying else yes(lying))
        try:
            result = screen(request)
        except ScreeningInputError as error:
            print(f"{r['child']}: not checked, {error.message('en')}")
            continue
        chw = CHW_LEVEL.get((r.get("chw_classification") or "").strip().lower())
        same = None if chw is None else chw == result.level
        if same is not None:
            compared += 1
            agree += same
        z = result.z
        fmt = lambda v: "" if v is None else f"{v:.2f}"
        out.append({"child": r["child"], "age_months": request.age_months, "sex": request.sex,
                    "weight_kg": request.weight_kg, "height_cm": request.height_cm or "", "muac_cm": request.muac_cm or "",
                    "oedema": "yes" if request.oedema else "no", "wfa_z": fmt(z.wfa), "hfa_z": fmt(z.hfa), "wfh_z": fmt(z.wfh),
                    "application": APP_NAME[result.level], "chw": r.get("chw_classification", ""),
                    "agree": "" if same is None else ("yes" if same else "no"), "source": r.get("source", "")})
    for o in out:
        print(f"{o['child']:<9} {o['age_months']:>3} mo {o['sex']:<6} WFA {o['wfa_z']:>6} HFA {o['hfa_z']:>6} "
              f"WFH {o['wfh_z']:>6} | app: {o['application']:<20} CHW: {o['chw']:<9} agree: {o['agree']}")
    if compared:
        print(f"\nAgreement: {agree} of {compared} children ({100 * agree / compared:.0f}%)")
    dest = ROOT / "outputs" / "pilot" / "growth_check_vs_chw.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(out[0]))
        writer.writeheader()
        writer.writerows(out)
    print("wrote", dest)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ROOT / "data" / "pilot" / "chw_measurements.csv")
