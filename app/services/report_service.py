from typing import Optional

from app.core.exceptions.exceptions import ReportNotFoundException, ReportTerminalStateException
from app.dto.report import (
    ReportAdminListResponse,
    ReportAdminResponse,
    ReportCreateRequest,
    ReportListResponse,
    ReportResponse,
    ReportStatusUpdateRequest,
)
from app.enums.ReportEnum import ReportStatus
from app.models.report import Report
from app.repositories.report_repo import ReportRepository
from app.services.news_service import auto_publish_news_post

TERMINAL_STATUSES = {ReportStatus.APPROVED, ReportStatus.REJECTED}


async def submit_report_service(database, user_id: str, request: ReportCreateRequest) -> ReportResponse:
    repo = ReportRepository(database)
    report = await repo.create(
        user_id=user_id,
        content_type=request.content_type,
        content=request.content,
        context=request.context,
        harm_type=request.harm_type,
    )
    return build_user_response(report)


async def get_report_for_user(database, report_id: str, user_id: str) -> ReportResponse:
    repo = ReportRepository(database)
    report = await repo.get_by_id_for_user(report_id=report_id, user_id=user_id)
    if report is None:
        raise ReportNotFoundException()

    return build_user_response(report)


async def list_reports_for_user(database, user_id: str, page: int, page_size: int) -> ReportListResponse:
    repo = ReportRepository(database)
    reports, total = await repo.list_for_user(
        user_id=user_id, page=page, page_size=page_size
    )
    return ReportListResponse(
        reports=[build_user_response(r) for r in reports],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


async def get_report_admin(database, report_id: str) -> ReportAdminResponse:
    repo = ReportRepository(database)
    report = await repo.get_by_report_id(report_id=report_id)
    if report is None:
        raise ReportNotFoundException()
    return build_admin_response(report)


async def list_reports_admin(database, page: int, page_size: int, status_filter: Optional[str] = None,
                             harm_type_filter: Optional[str] = None) -> ReportAdminListResponse:
    repo = ReportRepository(database)
    reports, total = await repo.list_admin(
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        harm_type_filter=harm_type_filter,
    )
    return ReportAdminListResponse(
        reports=[build_admin_response(r) for r in reports],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


async def update_report(database, report_id: str, admin_user_id: str,
                        request: ReportStatusUpdateRequest) -> ReportAdminResponse:
    repo = ReportRepository(database)
    report = await repo.get_by_report_id(report_id=report_id)
    if report is None:
        raise ReportNotFoundException()

    if ReportStatus(report.status) in TERMINAL_STATUSES:
        raise ReportTerminalStateException()

    resolved_by = (
        admin_user_id
        if ReportStatus(request.status) in TERMINAL_STATUSES
        else None
    )

    updated_report = await repo.update_report(
        report_id=report_id,
        status=ReportStatus(request.status),
        admin_notes=request.admin_notes,
        resolved_by=resolved_by,
    )

    if ReportStatus(request.status) == ReportStatus.APPROVED:
        await auto_publish_news_post(report_id, report.harm_type, report.content, report.context, database)

    return build_admin_response(updated_report)


def build_user_response(report: Report) -> ReportResponse:
    return ReportResponse(
        report_id=report.report_id,
        content_type=report.content_type,
        content=report.content,
        context=report.context,
        harm_type=report.harm_type,
        status=report.status,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


def build_admin_response(report: Report) -> ReportAdminResponse:
    return ReportAdminResponse(
        report_id=report.report_id,
        user_id=report.user_id,
        content_type=report.content_type,
        content=report.content,
        context=report.context,
        harm_type=report.harm_type,
        status=report.status,
        admin_notes=report.admin_notes,
        resolved_by=report.resolved_by,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )
