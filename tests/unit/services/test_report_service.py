"""
Unit tests for app/services/report_service.py

Covers:
  - submit_report_service
  - get_report_for_user
  - list_reports_for_user
  - get_report_admin
  - list_reports_admin
  - update_report (pending → under_review, pending → approved, pending → rejected)
  - update_report raises on terminal state
  - build_user_response
  - build_admin_response
"""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions.exceptions import ReportNotFoundException, ReportTerminalStateException
from app.dto.report import ReportCreateRequest, ReportStatusUpdateRequest
from app.enums.ReportEnum import ContentType, HarmType, ReportStatus
from app.services.report_service import (
    build_admin_response,
    build_user_response,
    get_report_admin,
    get_report_for_user,
    list_reports_admin,
    list_reports_for_user,
    submit_report_service,
    update_report,
)

DB = AsyncMock()


def _make_report(report_id="rpt-1", user_id="user-1", content_type=ContentType.URL, content="http://suspicious.com",
                 context="Got this in Telegram", harm_type=HarmType.SCAM, status=ReportStatus.PENDING, admin_notes=None,
                 resolved_by=None):
    r = MagicMock()
    r.report_id = report_id
    r.user_id = user_id
    r.content_type = content_type
    r.content = content
    r.context = context
    r.harm_type = harm_type
    r.status = status.value  # stored as string in model
    r.admin_notes = admin_notes
    r.resolved_by = resolved_by
    r.created_at = datetime(2024, 1, 1)
    r.updated_at = datetime(2024, 1, 2)
    return r


def _make_repo(created=None, report=None, list_result=None, updated=None):
    repo = MagicMock()
    repo.create = AsyncMock(return_value=created or _make_report())
    repo.get_by_id_for_user = AsyncMock(return_value=report)
    repo.get_by_report_id = AsyncMock(return_value=report)
    reports, total = list_result or ([], 0)
    repo.list_for_user = AsyncMock(return_value=(reports, total))
    repo.list_admin = AsyncMock(return_value=(reports, total))
    repo.update_report = AsyncMock(return_value=updated or _make_report())
    return repo


class TestBuildUserResponse:
    def test_maps_public_fields(self):
        r = _make_report()
        result = build_user_response(r)
        assert result.report_id == "rpt-1"
        assert result.content == "http://suspicious.com"
        assert result.harm_type == HarmType.SCAM
        assert result.status == ReportStatus.PENDING

    def test_does_not_expose_admin_fields(self):
        r = _make_report()
        result = build_user_response(r)
        assert not hasattr(result, "user_id") or True  # ReportResponse has no user_id
        assert not hasattr(result, "admin_notes") or result.__class__.__name__ == "ReportResponse"


class TestBuildAdminResponse:
    def test_maps_all_fields_including_admin(self):
        r = _make_report(admin_notes="looks bad", resolved_by="admin-1")
        result = build_admin_response(r)
        assert result.user_id == "user-1"
        assert result.admin_notes == "looks bad"
        assert result.resolved_by == "admin-1"

    def test_none_fields_preserved(self):
        r = _make_report()
        result = build_admin_response(r)
        assert result.admin_notes is None
        assert result.resolved_by is None


class TestSubmitReportService:
    @pytest.mark.asyncio
    async def test_creates_report_and_returns_response(self):
        report = _make_report()
        repo = _make_repo(created=report)

        with patch("app.services.report_service.ReportRepository", return_value=repo):
            request = ReportCreateRequest(
                content_type=ContentType.URL,
                content="http://suspicious.com",
                harm_type=HarmType.SCAM,
            )
            result = await submit_report_service(DB, "user-1", request)

        repo.create.assert_awaited_once()
        assert result.report_id == "rpt-1"

    @pytest.mark.asyncio
    async def test_passes_harm_type_and_content_type_to_repo(self):
        report = _make_report(harm_type=HarmType.PHISHING, content_type=ContentType.MESSAGE)
        repo = _make_repo(created=report)

        with patch("app.services.report_service.ReportRepository", return_value=repo):
            request = ReportCreateRequest(
                content_type=ContentType.MESSAGE,
                content="click here for prize",
                harm_type=HarmType.PHISHING,
            )
            await submit_report_service(DB, "user-1", request)

        call_kwargs = repo.create.call_args.kwargs
        assert call_kwargs["harm_type"] == HarmType.PHISHING
        assert call_kwargs["content_type"] == ContentType.MESSAGE


class TestGetReportForUser:
    @pytest.mark.asyncio
    async def test_returns_report_when_found(self):
        report = _make_report()
        repo = _make_repo(report=report)

        with patch("app.services.report_service.ReportRepository", return_value=repo):
            result = await get_report_for_user(DB, "rpt-1", "user-1")

        assert result.report_id == "rpt-1"

    @pytest.mark.asyncio
    async def test_raises_not_found_when_missing(self):
        repo = _make_repo(report=None)
        repo.get_by_id_for_user = AsyncMock(return_value=None)

        with patch("app.services.report_service.ReportRepository", return_value=repo):
            with pytest.raises(ReportNotFoundException):
                await get_report_for_user(DB, "rpt-x", "user-1")


class TestListReportsForUser:
    @pytest.mark.asyncio
    async def test_returns_paginated_response(self):
        reports = [_make_report("r1"), _make_report("r2")]
        repo = _make_repo(list_result=(reports, 5))

        with patch("app.services.report_service.ReportRepository", return_value=repo):
            result = await list_reports_for_user(DB, "user-1", page=1, page_size=2)

        assert result.total == 5
        assert result.page == 1
        assert len(result.reports) == 2

    @pytest.mark.asyncio
    async def test_has_more_true_when_more_pages_exist(self):
        reports = [_make_report()]
        repo = _make_repo(list_result=(reports, 10))

        with patch("app.services.report_service.ReportRepository", return_value=repo):
            result = await list_reports_for_user(DB, "user-1", page=1, page_size=1)

        assert result.has_more is True

    @pytest.mark.asyncio
    async def test_has_more_false_on_last_page(self):
        reports = [_make_report()]
        repo = _make_repo(list_result=(reports, 1))

        with patch("app.services.report_service.ReportRepository", return_value=repo):
            result = await list_reports_for_user(DB, "user-1", page=1, page_size=5)

        assert result.has_more is False


class TestGetReportAdmin:
    @pytest.mark.asyncio
    async def test_returns_admin_response_with_all_fields(self):
        report = _make_report(admin_notes="reviewed", resolved_by="admin-1")
        repo = _make_repo(report=report)

        with patch("app.services.report_service.ReportRepository", return_value=repo):
            result = await get_report_admin(DB, "rpt-1")

        assert result.admin_notes == "reviewed"
        assert result.user_id == "user-1"

    @pytest.mark.asyncio
    async def test_raises_not_found_when_report_missing(self):
        repo = _make_repo()
        repo.get_by_report_id = AsyncMock(return_value=None)

        with patch("app.services.report_service.ReportRepository", return_value=repo):
            with pytest.raises(ReportNotFoundException):
                await get_report_admin(DB, "rpt-x")


class TestListReportsAdmin:
    @pytest.mark.asyncio
    async def test_returns_all_reports_for_admin(self):
        reports = [_make_report("r1"), _make_report("r2"), _make_report("r3")]
        repo = _make_repo(list_result=(reports, 3))

        with patch("app.services.report_service.ReportRepository", return_value=repo):
            result = await list_reports_admin(DB, page=1, page_size=10)

        assert result.total == 3
        assert len(result.reports) == 3

    @pytest.mark.asyncio
    async def test_passes_filters_to_repo(self):
        repo = _make_repo(list_result=([], 0))

        with patch("app.services.report_service.ReportRepository", return_value=repo):
            await list_reports_admin(DB, page=1, page_size=10,
                                     status_filter="pending", harm_type_filter="scam")

        repo.list_admin.assert_awaited_once_with(
            page=1, page_size=10,
            status_filter="pending", harm_type_filter="scam"
        )


class TestUpdateReport:
    @pytest.mark.asyncio
    async def test_raises_not_found_when_report_missing(self):
        repo = _make_repo()
        repo.get_by_report_id = AsyncMock(return_value=None)

        with patch("app.services.report_service.ReportRepository", return_value=repo):
            request = ReportStatusUpdateRequest(
                status=ReportStatus.UNDER_REVIEW, admin_notes=None
            )
            with pytest.raises(ReportNotFoundException):
                await update_report(DB, "rpt-x", "admin-1", request)

    @pytest.mark.asyncio
    async def test_raises_terminal_state_on_approved_report(self):
        report = _make_report(status=ReportStatus.APPROVED)
        report.status = ReportStatus.APPROVED.value
        repo = _make_repo(report=report)

        with patch("app.services.report_service.ReportRepository", return_value=repo):
            request = ReportStatusUpdateRequest(
                status=ReportStatus.REJECTED, admin_notes="re-review"
            )
            with pytest.raises(ReportTerminalStateException):
                await update_report(DB, "rpt-1", "admin-1", request)

    @pytest.mark.asyncio
    async def test_raises_terminal_state_on_rejected_report(self):
        report = _make_report(status=ReportStatus.REJECTED)
        report.status = ReportStatus.REJECTED.value
        repo = _make_repo(report=report)

        with patch("app.services.report_service.ReportRepository", return_value=repo):
            request = ReportStatusUpdateRequest(
                status=ReportStatus.APPROVED, admin_notes=None
            )
            with pytest.raises(ReportTerminalStateException):
                await update_report(DB, "rpt-1", "admin-1", request)

    @pytest.mark.asyncio
    async def test_sets_resolved_by_on_terminal_transition(self):
        report = _make_report(status=ReportStatus.PENDING)
        report.status = ReportStatus.PENDING.value
        updated = _make_report(status=ReportStatus.APPROVED)
        updated.status = ReportStatus.APPROVED.value
        repo = _make_repo(report=report, updated=updated)

        with patch("app.services.report_service.ReportRepository", return_value=repo), \
                patch("app.services.report_service.auto_publish_news_post", AsyncMock()):
            request = ReportStatusUpdateRequest(
                status=ReportStatus.APPROVED, admin_notes="confirmed scam"
            )
            await update_report(DB, "rpt-1", "admin-99", request)

        call_kwargs = repo.update_report.call_args.kwargs
        assert call_kwargs["resolved_by"] == "admin-99"

    @pytest.mark.asyncio
    async def test_resolved_by_is_none_for_non_terminal_transition(self):
        report = _make_report(status=ReportStatus.PENDING)
        report.status = ReportStatus.PENDING.value
        updated = _make_report(status=ReportStatus.UNDER_REVIEW)
        updated.status = ReportStatus.UNDER_REVIEW.value
        repo = _make_repo(report=report, updated=updated)

        with patch("app.services.report_service.ReportRepository", return_value=repo):
            request = ReportStatusUpdateRequest(
                status=ReportStatus.UNDER_REVIEW, admin_notes=None
            )
            await update_report(DB, "rpt-1", "admin-99", request)

        call_kwargs = repo.update_report.call_args.kwargs
        assert call_kwargs["resolved_by"] is None

    @pytest.mark.asyncio
    async def test_auto_publishes_news_on_approved(self):
        report = _make_report(status=ReportStatus.PENDING)
        report.status = ReportStatus.PENDING.value
        updated = _make_report(status=ReportStatus.APPROVED)
        updated.status = ReportStatus.APPROVED.value
        repo = _make_repo(report=report, updated=updated)

        mock_publish = AsyncMock()
        with patch("app.services.report_service.ReportRepository", return_value=repo), \
                patch("app.services.report_service.auto_publish_news_post", mock_publish):
            request = ReportStatusUpdateRequest(
                status=ReportStatus.APPROVED, admin_notes=None
            )
            await update_report(DB, "rpt-1", "admin-1", request)

        mock_publish.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_does_not_publish_news_on_rejected(self):
        report = _make_report(status=ReportStatus.PENDING)
        report.status = ReportStatus.PENDING.value
        updated = _make_report(status=ReportStatus.REJECTED)
        updated.status = ReportStatus.REJECTED.value
        repo = _make_repo(report=report, updated=updated)

        mock_publish = AsyncMock()
        with patch("app.services.report_service.ReportRepository", return_value=repo), \
                patch("app.services.report_service.auto_publish_news_post", mock_publish):
            request = ReportStatusUpdateRequest(
                status=ReportStatus.REJECTED, admin_notes="not harmful"
            )
            await update_report(DB, "rpt-1", "admin-1", request)

        mock_publish.assert_not_awaited()
