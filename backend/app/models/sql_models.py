from sqlalchemy import Column, String, Text, JSON, DateTime, Boolean
from sqlalchemy.sql import func
from app.core.database import Base

class Job(Base):
    __tablename__ = "jobs"

    job_id = Column(String, primary_key=True, index=True)
    chat_id = Column(String, index=True)
    status = Column(String, default="PENDING")
    original_query = Column(Text)
    is_agentic = Column(Boolean, default=False)
    sub_queries = Column(JSON, default=[])
    memory = Column(JSON, default=[])
    sources = Column(JSON, default=[])
    final_answer = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Chat(Base):
    __tablename__ = "chats"

    chat_id = Column(String, primary_key=True, index=True)
    summary = Column(Text, nullable=True)
    recent_convo = Column(JSON, default=[])
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())



