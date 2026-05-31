from datetime import datetime
from typing import Optional

from pydantic import field_validator

from app.dto.base import BaseDTO
from app.enums.ReportEnum import ContentType, HarmType, ReportStatus


class ReportCreateRequest(BaseDTO):
    content_type: ContentType
    content: str
    context: Optional[str] = None
    harm_type: HarmType

    @field_validator("content")
    @classmethod
    def content_not_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("content must not be empty or whitespace")
        return v.strip()

    @field_validator("context")
    @classmethod
    def context_strip(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            return v if v else None
        return None


class ReportStatusUpdateRequest(BaseDTO):
    status: ReportStatus
    admin_notes: Optional[str]


class ReportResponse(BaseDTO):
    report_id: str
    content_type: ContentType
    content: str
    context: Optional[str]
    harm_type: HarmType
    status: ReportStatus
    created_at: datetime
    updated_at: datetime


class ReportAdminResponse(BaseDTO):
    report_id: str
    user_id: str
    content_type: ContentType
    content: str
    context: Optional[str]
    harm_type: HarmType
    status: ReportStatus
    admin_notes: Optional[str]
    resolved_by: Optional[str]
    created_at: datetime
    updated_at: datetime


class ReportListResponse(BaseDTO):
    reports: list[ReportResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class ReportAdminListResponse(BaseDTO):
    reports: list[ReportAdminResponse]
    total: int
    page: int
    page_size: int
    has_more: bool
