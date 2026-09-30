"""Common immutable audit-history model and helpers for MXMN transactions."""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import BigInteger, Column, DateTime, String, Text
from sqlalchemy.sql import func

from database import Base


class AuditEvent(Base):
    """Append-only business audit event. Application code never updates/deletes rows."""

    __tablename__ = "tb_audit_event"

    audit_event_id = Column(BigInteger, primary_key=True, autoincrement=True)
    comp_code = Column(String(20), nullable=False, index=True)
    user_id = Column(String(50), nullable=False)
    menu_code = Column(String(50), nullable=False)
    action = Column(String(30), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(100), nullable=False)
    source = Column(String(200), nullable=False)
    before_json = Column(Text, nullable=True)
    after_json = Column(Text, nullable=True)
    reason = Column(String(1000), nullable=True)
    related_entity_type = Column(String(50), nullable=True)
    related_entity_id = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def _json_default(value: Any):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Unsupported audit value: {type(value)!r}")


def snapshot_json(value: Any) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=_json_default)


def record_audit_event(
    db,
    *,
    comp_code: str,
    user_id: str,
    menu_code: str,
    action: str,
    entity_type: str,
    entity_id: str,
    source: str,
    before: Any = None,
    after: Any = None,
    reason: Optional[str] = None,
    related_entity_type: Optional[str] = None,
    related_entity_id: Optional[str] = None,
):
    event = AuditEvent(
        comp_code=comp_code,
        user_id=user_id,
        menu_code=menu_code,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        source=source,
        before_json=snapshot_json(before),
        after_json=snapshot_json(after),
        reason=reason.strip() if reason else None,
        related_entity_type=related_entity_type,
        related_entity_id=str(related_entity_id) if related_entity_id is not None else None,
    )
    db.add(event)
    return event
