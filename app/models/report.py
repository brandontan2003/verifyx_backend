import uuid

from sqlalchemy import Column, String, Text, DateTime, Enum
from sqlalchemy import ForeignKey
from sqlalchemy.sql import func

from app.enums.ReportEnum import ContentType, HarmType, ReportStatus
from app.models.base import Base


class Report(Base):
    __tablename__ = "reports"

    report_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    content_type = Column(Enum(ContentType, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    content = Column(Text, nullable=False)
    context = Column(Text, nullable=True)
    harm_type = Column(Enum(HarmType, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    status = Column(
        Enum(ReportStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        server_default=ReportStatus.PENDING.value,
    )
    # internal only, never returned to user
    admin_notes = Column(Text, nullable=True)
    # set when status → approved/rejected
    resolved_by = Column(String, ForeignKey("users.user_id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
