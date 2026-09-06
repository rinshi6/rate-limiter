from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class ClientConfig(Base):
    __tablename__ = "client_configs"

    client_key = Column(String(128), primary_key=True, index=True)
    rate_per_second = Column(Float, nullable=False, default=1.0)
    burst_size = Column(Integer, nullable=False, default=1)
    mode = Column(String(32), nullable=False, default="token_bucket")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class ClientState(Base):
    __tablename__ = "client_states"

    client_key = Column(String(128), primary_key=True, index=True)
    tokens = Column(Float, nullable=False, default=0.0)
    last_refill = Column(Float, nullable=False, default=0.0)
    window_start = Column(Float, nullable=False, default=0.0)
    request_count = Column(Integer, nullable=False, default=0)
    previous_request_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
