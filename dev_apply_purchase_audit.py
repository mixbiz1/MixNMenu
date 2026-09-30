"""One-time deterministic patch: connect common audit history to purchase API.

Run once on the work branch. Refuses to continue if expected source anchors differ.
"""
from pathlib import Path

path = Path("main.py")
s = path.read_text(encoding="utf-8")


def replace_once(old: str, new: str):
    global s
    count = s.count(old)
    if count != 1:
        raise SystemExit(f"Patch anchor mismatch: expected 1, found {count}: {old[:80]!r}")
    s = s.replace(old, new, 1)


replace_once(
    "from database import get_db, engine, Base, SessionLocal\n",
    "from database import get_db, engine, Base, SessionLocal\nfrom audit_service import record_audit_event\n",
)

# CREATE: capture final persisted representation after optional materialization/status transition.
replace_once(
    "        if data.finalize:\n            _materialize_purchase(db, row)\n            apply_status_transition(row, \"CONFIRMED\", request.state.user_id)\n        db.commit()",
    "        if data.finalize:\n            _materialize_purchase(db, row)\n            apply_status_transition(row, \"CONFIRMED\", request.state.user_id)\n        db.flush()\n        after = _purchase_result(row)\n        record_audit_event(\n            db, comp_code=comp_code, user_id=request.state.user_id, menu_code=\"PURCHASE_GENERAL\",\n            action=\"CREATE\", entity_type=\"PURCHASE\", entity_id=row.purchase_id,\n            source=\"POST /api/v1/companies/{comp_code}/purchases\", after=after,\n        )\n        if data.finalize:\n            record_audit_event(\n                db, comp_code=comp_code, user_id=request.state.user_id, menu_code=\"PURCHASE_GENERAL\",\n                action=\"CONFIRM\", entity_type=\"PURCHASE\", entity_id=row.purchase_id,\n                source=\"POST /api/v1/companies/{comp_code}/purchases (finalize)\", after=after,\n            )\n        db.commit()",
)

# UPDATE: snapshot before any dematerialization and after complete rematerialization.
replace_once(
    "    was_confirmed = row.document_status == \"CONFIRMED\"\n    old_purchase_no = row.purchase_no\n    try:",
    "    was_confirmed = row.document_status == \"CONFIRMED\"\n    old_purchase_no = row.purchase_no\n    before = _purchase_result(row)\n    try:",
)
replace_once(
    "        if data.finalize or was_confirmed:\n            _materialize_purchase(db, row)\n            if not was_confirmed:\n                apply_status_transition(row, \"CONFIRMED\", request.state.user_id)\n        db.commit()",
    "        if data.finalize or was_confirmed:\n            _materialize_purchase(db, row)\n            if not was_confirmed:\n                apply_status_transition(row, \"CONFIRMED\", request.state.user_id)\n        db.flush()\n        after = _purchase_result(row)\n        record_audit_event(\n            db, comp_code=comp_code, user_id=request.state.user_id, menu_code=\"PURCHASE_GENERAL\",\n            action=\"UPDATE\", entity_type=\"PURCHASE\", entity_id=row.purchase_id,\n            source=\"PUT /api/v1/companies/{comp_code}/purchases/{purchase_id}\",\n            before=before, after=after,\n        )\n        if data.finalize and not was_confirmed:\n            record_audit_event(\n                db, comp_code=comp_code, user_id=request.state.user_id, menu_code=\"PURCHASE_GENERAL\",\n                action=\"CONFIRM\", entity_type=\"PURCHASE\", entity_id=row.purchase_id,\n                source=\"PUT /api/v1/companies/{comp_code}/purchases/{purchase_id} (finalize)\",\n                before=before, after=after,\n            )\n        db.commit()",
)

# DRAFT DELETE: request is needed to identify actor; audit row remains after purchase deletion.
replace_once(
    "def delete_purchase(comp_code: str, purchase_id: int, db: Session = Depends(get_db)):\n    row = _purchase_or_404(db, comp_code, purchase_id); ensure_draft(row)\n    ensure_period_open(db, comp_code, row.purchase_date)\n    db.delete(row); db.commit(); return {\"message\": \"작성 중인 일반 매입전표가 삭제되었습니다.\"}",
    "def delete_purchase(comp_code: str, purchase_id: int, request: Request, db: Session = Depends(get_db)):\n    row = _purchase_or_404(db, comp_code, purchase_id); ensure_draft(row)\n    ensure_period_open(db, comp_code, row.purchase_date)\n    before = _purchase_result(row)\n    record_audit_event(\n        db, comp_code=comp_code, user_id=request.state.user_id, menu_code=\"PURCHASE_GENERAL\",\n        action=\"DELETE\", entity_type=\"PURCHASE\", entity_id=row.purchase_id,\n        source=\"DELETE /api/v1/companies/{comp_code}/purchases/{purchase_id}\", before=before,\n    )\n    db.delete(row); db.commit(); return {\"message\": \"작성 중인 일반 매입전표가 삭제되었습니다.\"}",
)

# Explicit CONFIRM.
replace_once(
    "    ensure_draft(row)\n    try:\n        _materialize_purchase(db, row)\n        apply_status_transition(row, \"CONFIRMED\", request.state.user_id)\n        db.commit()",
    "    ensure_draft(row)\n    before = _purchase_result(row)\n    try:\n        _materialize_purchase(db, row)\n        apply_status_transition(row, \"CONFIRMED\", request.state.user_id)\n        db.flush()\n        after = _purchase_result(row)\n        record_audit_event(\n            db, comp_code=comp_code, user_id=request.state.user_id, menu_code=\"PURCHASE_GENERAL\",\n            action=\"CONFIRM\", entity_type=\"PURCHASE\", entity_id=row.purchase_id,\n            source=\"POST /api/v1/companies/{comp_code}/purchases/{purchase_id}/confirm\",\n            before=before, after=after,\n        )\n        db.commit()",
)

# CANCEL.
replace_once(
    "    # 현재 출고 Vertical Slice 전이므로 매입확정이 만든 입고/LOT만 원자적으로 회수한다.\n    # 후속 출고 연결 뒤에는 취소출고 원장을 생성하는 방식으로 교체한다.\n    try:\n        _dematerialize_purchase(db, row)\n        apply_status_transition(row, \"CANCELLED\", request.state.user_id)\n        db.commit()",
    "    # 현재 출고 Vertical Slice 전이므로 매입확정이 만든 입고/LOT만 원자적으로 회수한다.\n    # 후속 출고 연결 뒤에는 취소출고 원장을 생성하는 방식으로 교체한다.\n    before = _purchase_result(row)\n    try:\n        _dematerialize_purchase(db, row)\n        apply_status_transition(row, \"CANCELLED\", request.state.user_id)\n        db.flush()\n        after = _purchase_result(row)\n        record_audit_event(\n            db, comp_code=comp_code, user_id=request.state.user_id, menu_code=\"PURCHASE_GENERAL\",\n            action=\"CANCEL\", entity_type=\"PURCHASE\", entity_id=row.purchase_id,\n            source=\"POST /api/v1/companies/{comp_code}/purchases/{purchase_id}/cancel\",\n            before=before, after=after,\n        )\n        db.commit()",
)

path.write_text(s, encoding="utf-8")
print("Purchase audit integration patch applied.")
