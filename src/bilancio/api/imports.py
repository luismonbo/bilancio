"""Imports API — file upload endpoint that triggers the import pipeline."""

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from bilancio.auth.dependencies import get_current_user
from bilancio.services.account_service import AccountService
from bilancio.services.import_service import ImportService
from bilancio.storage.database import get_db
from bilancio.storage.models import User

router = APIRouter(tags=["imports"])


# ------------------------------------------------------------------
# Pydantic schema
# ------------------------------------------------------------------


class ImportResultRead(BaseModel):
    added: int
    skipped: int
    needs_review: int


# ------------------------------------------------------------------
# Route
# ------------------------------------------------------------------


@router.post(
    "/accounts/{account_id}/import",
    response_model=ImportResultRead,
)
async def import_file(
    account_id: int,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportResultRead:
    """Upload a bank export file and import all transactions into the account.

    The correct parser is auto-detected from the file contents.
    Returns counts of added, skipped (duplicate), and needs_review rows.
    """
    # Verify the account belongs to the current user before touching the file.
    account_svc = AccountService(db)
    try:
        await account_svc.get(account_id=account_id, user_id=current_user.id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    # Save the upload to a temp file so the parser can use Path-based detection.
    suffix = Path(file.filename or "upload").suffix or ".bin"
    contents = await file.read()

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(contents)
        tmp_path = Path(tmp.name)

    try:
        svc = ImportService(db)
        summary = await svc.import_file(
            file_path=tmp_path,
            account_id=account_id,
            user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    return ImportResultRead(
        added=summary.added,
        skipped=summary.skipped,
        needs_review=summary.needs_review,
    )
