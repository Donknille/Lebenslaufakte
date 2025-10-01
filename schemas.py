from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, List
from models import IssueStatus

# Machine schemas
class MachineBase(BaseModel):
    name: str
    serial_number: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None

class MachineCreate(MachineBase):
    pass

class MachineUpdate(BaseModel):
    name: Optional[str] = None
    serial_number: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None

class Machine(MachineBase):
    id: int
    public_slug: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Issue schemas
class IssueBase(BaseModel):
    title: str
    description: Optional[str] = None
    reported_by: str
    reported_at: Optional[datetime] = None

class IssueCreate(IssueBase):
    machine_id: int

class IssueUpdate(BaseModel):
    status: Optional[IssueStatus] = None

class Issue(IssueBase):
    id: int
    machine_id: int
    status: IssueStatus
    closed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Issue Update schemas
class IssueUpdateBase(BaseModel):
    note: str
    author: str
    status_change: Optional[IssueStatus] = None

class IssueUpdateCreate(IssueUpdateBase):
    issue_id: int

class IssueUpdateResponse(IssueUpdateBase):
    id: int
    issue_id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Maintenance schemas
class MaintenanceBase(BaseModel):
    title: str
    description: Optional[str] = None
    performed_by: str
    performed_at: Optional[datetime] = None
    next_due_at: Optional[datetime] = None

class MaintenanceCreate(MaintenanceBase):
    machine_id: int

class Maintenance(MaintenanceBase):
    id: int
    machine_id: int

    class Config:
        from_attributes = True

# Employee schemas
class EmployeeBase(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    employee_id: str

class EmployeeCreate(EmployeeBase):
    is_active: Optional[int] = 1

class EmployeeUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    employee_id: Optional[str] = None
    is_active: Optional[int] = None

class Employee(EmployeeBase):
    id: int
    is_active: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Complex response schemas
class MachineWithIssues(Machine):
    issues: List[Issue] = []
    maintenance_records: List[Maintenance] = []

class IssueWithUpdates(Issue):
    updates: List[IssueUpdateResponse] = []