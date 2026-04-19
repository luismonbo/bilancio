"""Rules API — CRUD + YAML import/export for categorization rules.

Route order matters: /rules/export must appear before /rules/{id} so that
FastAPI does not try to coerce "export" into an integer path parameter.
"""

from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from bilancio.auth.dependencies import get_current_user
from bilancio.services.rule_service import RuleService
from bilancio.storage.database import get_db
from bilancio.storage.models import User

router = APIRouter(prefix="/rules", tags=["rules"])

_VALID_PATTERN_TYPES = {"contains", "exact", "starts_with", "regex"}


# ------------------------------------------------------------------
# Pydantic schemas
# ------------------------------------------------------------------


class RuleCreate(BaseModel):
    pattern: str
    pattern_type: str
    category: str
    subcategory: str | None = None
    priority: int = 0
    enabled: bool = True

    @field_validator("pattern_type")
    @classmethod
    def validate_pattern_type(cls, v: str) -> str:
        if v not in _VALID_PATTERN_TYPES:
            raise ValueError(
                f"Invalid pattern_type {v!r}. Must be one of: {sorted(_VALID_PATTERN_TYPES)}"
            )
        return v


class RuleUpdate(BaseModel):
    pattern: str | None = None
    pattern_type: str | None = None
    category: str | None = None
    subcategory: str | None = None
    priority: int | None = None
    enabled: bool | None = None

    @field_validator("pattern_type")
    @classmethod
    def validate_pattern_type(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_PATTERN_TYPES:
            raise ValueError(
                f"Invalid pattern_type {v!r}. Must be one of: {sorted(_VALID_PATTERN_TYPES)}"
            )
        return v


class RuleRead(BaseModel):
    id: int
    user_id: int
    pattern: str
    pattern_type: str
    category: str
    subcategory: str | None
    priority: int
    enabled: bool
    created_at: datetime
    created_by: str | None

    model_config = {"from_attributes": True}


class RulesImportRead(BaseModel):
    imported: int


# ------------------------------------------------------------------
# Routes — static paths first, then parameterised
# ------------------------------------------------------------------


@router.get("/export", response_class=PlainTextResponse)
async def export_rules(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> str:
    """Export all rules for the current user as a YAML string."""
    svc = RuleService(db)
    return await svc.export_yaml(user_id=current_user.id)


@router.post("/import", response_model=RulesImportRead)
async def import_rules(
    yaml_text: str = Body(media_type="text/plain"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RulesImportRead:
    """Import rules from a YAML string. Returns the count of rules created."""
    svc = RuleService(db)
    try:
        count = await svc.import_yaml(user_id=current_user.id, yaml_text=yaml_text)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    return RulesImportRead(imported=count)


@router.get("", response_model=list[RuleRead])
async def list_rules(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[RuleRead]:
    svc = RuleService(db)
    return await svc.list_rules(user_id=current_user.id)  # type: ignore[return-value]


@router.post("", response_model=RuleRead, status_code=status.HTTP_201_CREATED)
async def create_rule(
    payload: RuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RuleRead:
    svc = RuleService(db)
    rule = await svc.create(
        user_id=current_user.id,
        pattern=payload.pattern,
        pattern_type=payload.pattern_type,
        category=payload.category,
        subcategory=payload.subcategory,
        priority=payload.priority,
        enabled=payload.enabled,
    )
    return RuleRead.model_validate(rule)


@router.get("/{rule_id}", response_model=RuleRead)
async def get_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RuleRead:
    svc = RuleService(db)
    try:
        rule = await svc.get(rule_id=rule_id, user_id=current_user.id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    return RuleRead.model_validate(rule)


@router.patch("/{rule_id}", response_model=RuleRead)
async def update_rule(
    rule_id: int,
    payload: RuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RuleRead:
    svc = RuleService(db)
    try:
        rule = await svc.update(
            rule_id=rule_id,
            user_id=current_user.id,
            pattern=payload.pattern,
            pattern_type=payload.pattern_type,
            category=payload.category,
            subcategory=payload.subcategory,
            priority=payload.priority,
            enabled=payload.enabled,
        )
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    return RuleRead.model_validate(rule)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    svc = RuleService(db)
    try:
        await svc.delete(rule_id=rule_id, user_id=current_user.id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
