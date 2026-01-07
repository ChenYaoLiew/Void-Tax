from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from datetime import datetime

from app.config import get_settings

Base = declarative_base()


class Fine(Base):
    """Fine database model."""
    __tablename__ = "fines"
    
    id = Column(Integer, primary_key=True, index=True)
    plate_number = Column(String(20), index=True, nullable=False)
    owner_name = Column(String(100), nullable=True)
    owner_id = Column(String(50), nullable=True)
    fine_type = Column(String(20), nullable=False)  # road_tax, insurance, both
    fine_amount = Column(Float, nullable=False)
    issued_at = Column(DateTime, default=datetime.now)
    paid = Column(Boolean, default=False)
    paid_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<Fine(id={self.id}, plate={self.plate_number}, amount={self.fine_amount})>"


class ScanLog(Base):
    """Log of all scans performed."""
    __tablename__ = "scan_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    plate_number = Column(String(20), index=True, nullable=False)
    scanned_at = Column(DateTime, default=datetime.now)
    confidence = Column(Float, nullable=False)
    road_tax_valid = Column(Boolean, nullable=True)
    insurance_valid = Column(Boolean, nullable=True)
    fine_issued = Column(Boolean, default=False)
    cached_result = Column(Boolean, default=False)


# Database engine and session
settings = get_settings()
engine = create_async_engine(settings.database_url, echo=settings.debug)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    """Dependency to get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

