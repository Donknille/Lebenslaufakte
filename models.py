from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()

class IssueStatus(enum.Enum):
    open = "open"
    in_progress = "in_progress"
    closed = "closed"

class Machine(Base):
    __tablename__ = "machines"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    serial_number = Column(String(100), unique=True, nullable=True)
    location = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    public_slug = Column(String(20), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    issues = relationship("Issue", back_populates="machine", cascade="all, delete-orphan")
    maintenance_records = relationship("Maintenance", back_populates="machine", cascade="all, delete-orphan")

class Issue(Base):
    __tablename__ = "issues"
    
    id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    reported_by = Column(String(100), nullable=False)
    reported_at = Column(DateTime, default=datetime.utcnow)
    status = Column(Enum(IssueStatus), default=IssueStatus.open)
    closed_at = Column(DateTime, nullable=True)
    
    # Relationships
    machine = relationship("Machine", back_populates="issues")
    updates = relationship("IssueUpdate", back_populates="issue", cascade="all, delete-orphan")

class IssueUpdate(Base):
    __tablename__ = "issue_updates"
    
    id = Column(Integer, primary_key=True, index=True)
    issue_id = Column(Integer, ForeignKey("issues.id"), nullable=False)
    note = Column(Text, nullable=False)
    author = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    status_change = Column(Enum(IssueStatus), nullable=True)
    
    # Relationships
    issue = relationship("Issue", back_populates="updates")

class Maintenance(Base):
    __tablename__ = "maintenance"
    
    id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    performed_by = Column(String(100), nullable=False)
    performed_at = Column(DateTime, default=datetime.utcnow)
    next_due_at = Column(DateTime, nullable=True)
    
    # Relationships
    machine = relationship("Machine", back_populates="maintenance_records")

class Employee(Base):
    __tablename__ = "employees"
    
    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    phone = Column(String(50), nullable=True)
    department = Column(String(100), nullable=True)
    position = Column(String(100), nullable=True)
    employee_id = Column(String(50), unique=True, nullable=False)
    is_active = Column(Integer, default=1)  # 1 = active, 0 = inactive
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)