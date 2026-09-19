import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from sqlalchemy import create_engine
from semanticgraph.models.base import Base
from semanticgraph.models.tenant import Tenant, TenantMember, Invitation
from semanticgraph.models.user import User
from models.compliance import ApiKey, AuditLog
from models.billing import Subscription, QuotaUsage

engine = create_engine('sqlite:///:memory:')
Base.metadata.create_all(engine)
print("Models verified successfully!")
