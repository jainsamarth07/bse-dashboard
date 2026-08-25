"""
Monitor rules CRUD routes.

Manages the rules that control which BSE announcements the monitor will analyse.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_current_user, get_pg
from api.schemas import (
    MonitorRuleCreate,
    MonitorRuleResponse,
    MonitorRuleUpdate,
    MonitorStatusResponse,
)
from app.db.models import MonitorRuleStore, MonitorStatusStore

router = APIRouter()

VALID_FIELDS = {"group", "subject", "market_cap", "scrip_code"}
VALID_OPERATORS = {"equals", "contains", "gt", "lt", "in", "not_in"}


def _to_response(doc: dict) -> MonitorRuleResponse:
    return MonitorRuleResponse(
        id=doc.get("_id", ""),
        name=doc.get("name", ""),
        field=doc.get("field", ""),
        operator=doc.get("operator", ""),
        value=doc.get("value"),
        enabled=doc.get("enabled", True),
        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at"),
    )


@router.get("/rules", response_model=list[MonitorRuleResponse])
async def list_rules(user=Depends(get_current_user)):
    """List all monitor rules."""
    docs = MonitorRuleStore.get_all()
    return [_to_response(d) for d in docs]


@router.post("/rules", response_model=MonitorRuleResponse, status_code=201)
async def create_rule(body: MonitorRuleCreate, user=Depends(get_current_user)):
    """Create a new monitor rule."""
    if body.field not in VALID_FIELDS:
        raise HTTPException(400, f"Invalid field: {body.field}. Must be one of {VALID_FIELDS}")
    if body.operator not in VALID_OPERATORS:
        raise HTTPException(400, f"Invalid operator: {body.operator}. Must be one of {VALID_OPERATORS}")

    doc = MonitorRuleStore.create({
        "name": body.name,
        "field": body.field,
        "operator": body.operator,
        "value": body.value,
        "enabled": body.enabled,
    })
    return _to_response(doc)


@router.patch("/rules/{rule_id}", response_model=MonitorRuleResponse)
async def update_rule(
    rule_id: str,
    body: MonitorRuleUpdate,
    user=Depends(get_current_user),
):
    """Update an existing monitor rule."""
    update = body.model_dump(exclude_none=True)
    if not update:
        raise HTTPException(400, "No fields to update")

    if "field" in update and update["field"] not in VALID_FIELDS:
        raise HTTPException(400, f"Invalid field: {update['field']}")
    if "operator" in update and update["operator"] not in VALID_OPERATORS:
        raise HTTPException(400, f"Invalid operator: {update['operator']}")

    doc = MonitorRuleStore.update(rule_id, update)
    if not doc:
        raise HTTPException(404, "Rule not found")
    return _to_response(doc)


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str, user=Depends(get_current_user)):
    """Delete a monitor rule."""
    ok = MonitorRuleStore.delete(rule_id)
    if not ok:
        raise HTTPException(404, "Rule not found")
    return {"ok": True}


@router.post("/reload")
async def reload_monitor(
    user=Depends(get_current_user),
    pg=Depends(get_pg),
):
    """Signal the monitor to reload rules.

    Sets a flag in monitor_status that the monitor checks on each poll.
    Requires admin role.
    """
    row = await pg.fetchrow("SELECT role FROM users WHERE id=$1", int(user["sub"]))
    if not row or row["role"] != "admin":
        raise HTTPException(403, "Monitor reload requires admin role")

    MonitorStatusStore.set_reload_flag()
    rules_count = MonitorRuleStore.count_enabled()
    return {"ok": True, "rules_count": rules_count}


@router.get("/status", response_model=MonitorStatusResponse)
async def monitor_status(user=Depends(get_current_user)):
    """Get current monitor status: last poll, counters, active rules."""
    return MonitorStatusStore.get_status()
