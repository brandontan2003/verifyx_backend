from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from app.dependencies import RoleChecker, get_current_user, get_db
from app.dto.base import DataResponse
from app.dto.report import (
    ReportAdminListResponse,
    ReportAdminResponse,
    ReportCreateRequest,
    ReportListResponse,
    ReportResponse,
    ReportStatusUpdateRequest,
)
from app.enums.RoleEnum import RoleType
from app.services.report_service import (
    get_report_admin, get_report_for_user, list_reports_admin, list_reports_for_user, update_report,
    submit_report_service
)

router = APIRouter(prefix="/report", tags=["report"])


@router.post("/submit", response_model=DataResponse[ReportResponse], status_code=status.HTTP_201_CREATED)
async def submit_report(payload: ReportCreateRequest, user=Depends(get_current_user), database=Depends(get_db)):
    report = await submit_report_service(database, user_id=user["sub"], request=payload)
    return DataResponse(result=report)


@router.get("/me", response_model=DataResponse[ReportListResponse])
async def list_own_reports(user=Depends(get_current_user), database=Depends(get_db),
                           page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100)):
    result = await list_reports_for_user(database, user_id=user["sub"], page=page, page_size=page_size)
    return DataResponse(result=result)


@router.get("/me/{report_id}", response_model=DataResponse[ReportResponse])
async def get_own_report(report_id: str, user=Depends(get_current_user), database=Depends(get_db)):
    report = await get_report_for_user(database, report_id=report_id, user_id=user["sub"])
    return DataResponse(result=report)


@router.get("/internal", response_model=DataResponse[ReportAdminListResponse],
            dependencies=[Depends(RoleChecker([RoleType.ADMIN]))])
async def admin_list_reports(admin=Depends(get_current_user), database=Depends(get_db),
                             page: int = Query(default=1, ge=1),
                             page_size: int = Query(default=50, ge=1, le=200),
                             status_filter: Optional[str] = Query(default=None, alias="status"),
                             harm_type_filter: Optional[str] = Query(default=None, alias="harm_type")):
    result = await list_reports_admin(database, page=page, page_size=page_size, status_filter=status_filter,
                                      harm_type_filter=harm_type_filter)
    return DataResponse(result=result)


@router.get("/internal/{report_id}", response_model=DataResponse[ReportAdminResponse],
            dependencies=[Depends(RoleChecker([RoleType.ADMIN]))])
async def admin_get_report(report_id: str, admin=Depends(get_current_user), database=Depends(get_db)):
    report = await get_report_admin(database, report_id=report_id)
    return DataResponse(result=report)


@router.put("/internal/{report_id}", response_model=DataResponse[ReportAdminResponse],
            dependencies=[Depends(RoleChecker([RoleType.ADMIN]))])
async def admin_update_report(report_id: str, payload: ReportStatusUpdateRequest, admin=Depends(get_current_user),
                              database=Depends(get_db)):
    report = await update_report(database, report_id=report_id, admin_user_id=admin["sub"], request=payload)
    return DataResponse(result=report)
