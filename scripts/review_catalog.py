"""Exporta borradores o verifica un catálogo revisado, sin red ni activación implícita."""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.db.database import get_db
from src.domain.recommendations import KnowledgeBase, rule_fingerprint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["draft", "check"])
    parser.add_argument("file", type=Path)
    args = parser.parse_args()
    with get_db() as conn:
        if args.action == "draft":
            entries = []
            for row in conn.execute("SELECT regla_id FROM reglas_botanicas ORDER BY regla_id"):
                entries.append(dict(rule_id=row[0], fingerprint=rule_fingerprint(conn, row[0]),
                    status="draft", reviewed_by="PENDIENTE", reviewed_on=str(date.today()),
                    valid_until=str(date.today()), sources=["PENDIENTE"],
                    explanation="PENDIENTE", precautions="PENDIENTE"))
            with args.file.open("x", encoding="utf-8") as output:
                json.dump(dict(version="borrador", rules=entries), output, ensure_ascii=False, indent=2)
        else:
            kb = KnowledgeBase.model_validate_json(args.file.read_text(encoding="utf-8"))
            ids = [r.rule_id for r in kb.rules]
            if len(ids) != len(set(ids)):
                raise ValueError("Identificadores duplicados")
            for rule in kb.rules:
                if rule.fingerprint != rule_fingerprint(conn, rule.rule_id):
                    raise ValueError(f"Regla {rule.rule_id}: revisión no corresponde al código o criterios actuales")
                if rule.status == "approved" and not rule.reviewed_on <= date.today() <= rule.valid_until:
                    raise ValueError(f"Regla {rule.rule_id}: revisión fuera de vigencia")
            print(f"Estructura y huellas válidas: {kb.version}, {len(kb.rules)} reglas. No acredita validez clínica.")


if __name__ == "__main__":
    main()
