"""导出下载接口：复用与列表完全相同的筛选参数。"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.api.v1.deps import pokemon_filters, stmt_from_filters
from app.services import export_service

router = APIRouter(prefix="/export", tags=["export"])


@router.get("")
async def export(
    filters: dict = Depends(pokemon_filters),
    format: str = Query("csv", pattern="^(csv|json)$"),
):
    stmt = stmt_from_filters(filters)
    name = export_service.filename(format)

    if format == "json":
        return StreamingResponse(
            export_service.iter_json(stmt),
            media_type="application/json; charset=utf-8",
            headers={
                "Content-Disposition": (
                    f"attachment; filename={name}; filename*=UTF-8''{quote(name)}"
                )
            },
        )

    return StreamingResponse(
        export_service.iter_csv(stmt),
        media_type="text/csv; charset=utf-8-sig",
        headers={
            "Content-Disposition": (
                f"attachment; filename={name}; filename*=UTF-8''{quote(name)}"
            )
        },
    )
