"""Evalúa un ajuste de sesgo facial en participantes separados del conjunto de prueba.

CSV de entrada: participant_id,age_real,age_model y opcional phototype.
No necesita ni lee imágenes. Varias lecturas de la misma persona se resumen
con su mediana antes de separar calibración y prueba.
"""
import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path


def read_participants(path):
    grouped = defaultdict(list)
    labels = {}
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        required = {"participant_id", "age_real", "age_model"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("El CSV requiere participant_id,age_real,age_model")
        for row in reader:
            pid = (row.get("participant_id") or "").strip()
            if not pid:
                raise ValueError("Cada lectura necesita un código anónimo de participante")
            real, estimated = float(row["age_real"]), float(row["age_model"])
            if not (math.isfinite(real) and math.isfinite(estimated) and 0 <= real <= 120 and 0 <= estimated <= 120):
                raise ValueError(f"Edad inválida para participante {pid}")
            if pid in labels and labels[pid][0] != real:
                raise ValueError(f"La edad real cambia entre lecturas de {pid}")
            labels[pid] = (real, (row.get("phototype") or "").strip())
            grouped[pid].append(estimated)
    return {pid: {"real": labels[pid][0], "estimated": statistics.median(values), "phototype": labels[pid][1]}
            for pid, values in grouped.items()}


def mae(rows, offset=0.0):
    return statistics.mean(abs(row["estimated"] + offset - row["real"]) for row in rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="CSV local de lecturas, sin nombres ni fotografías")
    parser.add_argument("--test-fraction", type=float, default=.25)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    if not .15 <= args.test_fraction <= .4:
        parser.error("--test-fraction debe estar entre 0.15 y 0.40")
    people = read_participants(args.csv)
    if len(people) < 20:
        raise SystemExit(f"Se necesitan al menos 20 participantes distintos; hay {len(people)}. Con menos, el ajuste se reporta como exploratorio y no se calcula un offset de prueba.")

    import random
    ids = sorted(people)
    random.Random(args.seed).shuffle(ids)
    test_count = max(5, round(len(ids) * args.test_fraction))
    test_ids, calibration_ids = ids[:test_count], ids[test_count:]
    calibration = [people[pid] for pid in calibration_ids]
    test = [people[pid] for pid in test_ids]
    # Mediana del residuo minimiza MAE y no deja que una edad extrema domine el ajuste.
    offset = statistics.median(row["real"] - row["estimated"] for row in calibration)
    before, after = mae(test), mae(test, offset)

    print(f"Participantes: {len(people)} ({len(calibration)} calibración, {len(test)} prueba independiente)")
    print(f"MAE prueba sin ajuste: {before:.2f} años")
    print(f"Offset candidato aprendido solo en calibración: {offset:+.2f} años")
    print(f"MAE prueba con offset: {after:.2f} años ({before-after:+.2f} años de cambio)")
    if after >= before:
        print("RESULTADO: no aplicar el offset; no mejoró en participantes de prueba.")
    else:
        print("RESULTADO: el offset mejora este grupo de prueba; repetir con una nueva cohorte antes de fijarlo en producción.")

    for label, predicate in (
        ("18–29", lambda r: 18 <= r["real"] <= 29),
        ("30–44", lambda r: 30 <= r["real"] <= 44),
        ("45–59", lambda r: 45 <= r["real"] <= 59),
        ("60+", lambda r: r["real"] >= 60),
    ):
        group = [row for row in test if predicate(row)]
        if len(group) >= 5:
            print(f"Edad {label} (n={len(group)}): MAE {mae(group):.2f} → {mae(group, offset):.2f} años")
    typed = [row for row in test if row["phototype"]]
    for phototype in sorted({row["phototype"] for row in typed}):
        group = [row for row in typed if row["phototype"] == phototype]
        if len(group) >= 5:
            print(f"Fototipo {phototype} (n={len(group)}): MAE {mae(group):.2f} → {mae(group, offset):.2f} años")
    print("Este ensayo mide concordancia con edad cronológica, no edad biológica clínica.")


if __name__ == "__main__":
    main()
