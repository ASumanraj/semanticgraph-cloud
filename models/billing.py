import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from semanticgraph.models.base import Base
from sqlalchemy import Column, Integer, String, ForeignKey

class Subscription(Base):
    __tablename__ = 'subscriptions'
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    plan = Column(String, nullable=False)

class QuotaUsage(Base):
    __tablename__ = 'quota_usage'
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    usage = Column(Integer, nullable=False)
