import uuid

from sqlalchemy import Column, String, ForeignKey, DateTime, Enum
from sqlalchemy.sql import func

from app.enums.RoleEnum import RoleType
from app.enums.ScopeEnum import ScopeType
from app.models.base import Base


class Role(Base):
    __tablename__ = "roles"

    role_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(Enum(RoleType, values_callable=lambda obj: [e.value for e in obj]), unique=True, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Scope(Base):
    __tablename__ = "scopes"

    scope_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(Enum(ScopeType, values_callable=lambda obj: [e.value for e in obj]), unique=True, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RoleScope(Base):
    """Many-to-many: which scopes belong to which role."""
    __tablename__ = "role_scopes"

    role_id = Column(String, ForeignKey("roles.role_id"), primary_key=True)
    scope_id = Column(String, ForeignKey("scopes.scope_id"), primary_key=True)
