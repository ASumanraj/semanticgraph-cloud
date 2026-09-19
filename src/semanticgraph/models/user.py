from sqlalchemy import Boolean, Column, Integer, String

from .base import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    is_super_admin = Column(Boolean, default=False)
