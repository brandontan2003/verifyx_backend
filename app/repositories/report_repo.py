from typing import Optional
from uuid import uuid4

from app.core.exceptions.exceptions import ReportNotFoundException
from app.models.report import Report
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.ReportEnum import ReportStatus


class ReportRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, user_id: str, content_type: str, content: str, context: Optional[str], harm_type: str) -> Report:
        report = Report(
            report_id=str(uuid4()),
            user_id=user_id,
            content_type=content_type,
            content=content,
            context=context,
            harm_type=harm_type,
            status=ReportStatus.PENDING,
        )
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def update_report(self, report_id: str, status: ReportStatus, admin_notes: Optional[str],
                            resolved_by: Optional[str]) -> Report:
        report = await self.get_by_report_id(report_id)
        if report is None:
            raise ReportNotFoundException()

        report.status = status
        if admin_notes is not None:
            report.admin_notes = admin_notes
        report.resolved_by = resolved_by  # None for pending/under_review, user_id for resolved/dismissed
        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def get_by_id_for_user(self, report_id: str, user_id: str) -> Report:
        result = await self.db.execute(
            select(Report)
            .where(Report.report_id == report_id)
            .where(Report.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: str, page: int, page_size: int) -> tuple[list[Report], int]:
        base = select(Report).where(Report.user_id == user_id)

        count_result = await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar_one()

        data_result = await self.db.execute(
            base.order_by(Report.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(data_result.scalars().all()), total

    async def get_by_report_id(self, report_id: str) -> Report:
        result = await self.db.execute(
            select(Report).where(Report.report_id == report_id)
        )
        return result.scalar_one_or_none()

    async def list_admin(self, page: int, page_size: int, status_filter: Optional[str] = None,
                         harm_type_filter: Optional[str] = None) -> tuple[list[Report], int]:
        base = select(Report)

        if status_filter:
            base = base.where(Report.status == status_filter)
        if harm_type_filter:
            base = base.where(Report.harm_type == harm_type_filter)

        count_result = await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar_one()

        data_result = await self.db.execute(
            base.order_by(Report.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(data_result.scalars().all()), total
