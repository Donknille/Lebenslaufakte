from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
from typing import List, Optional
import models
import schemas
import secrets
import string
from datetime import datetime

def generate_slug() -> str:
    """Generate a random URL-safe slug for machine public links"""
    alphabet = string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(8))

def ensure_unique_slug(db: Session) -> str:
    """Generate a unique slug that doesn't exist in the database"""
    while True:
        slug = generate_slug()
        if not db.query(models.Machine).filter(models.Machine.public_slug == slug).first():
            return slug

# Machine CRUD operations
def get_machine(db: Session, machine_id: int) -> Optional[models.Machine]:
    return db.query(models.Machine).filter(models.Machine.id == machine_id).first()

def get_machine_by_slug(db: Session, slug: str) -> Optional[models.Machine]:
    return db.query(models.Machine).filter(models.Machine.public_slug == slug).first()

def get_machines(db: Session, skip: int = 0, limit: int = 100) -> List[models.Machine]:
    return db.query(models.Machine).order_by(desc(models.Machine.created_at)).offset(skip).limit(limit).all()

def search_machines(db: Session, query: str) -> List[models.Machine]:
    search_term = f"%{query}%"
    return db.query(models.Machine).filter(
        (models.Machine.name.ilike(search_term)) |
        (models.Machine.serial_number.ilike(search_term)) |
        (models.Machine.location.ilike(search_term))
    ).order_by(desc(models.Machine.created_at)).all()

def get_machines_with_open_issues(db: Session, skip: int = 0, limit: int = 100) -> List[models.Machine]:
    """Get machines with their open issues loaded for dashboard display"""
    machines = db.query(models.Machine).order_by(desc(models.Machine.created_at)).offset(skip).limit(limit).all()
    
    # Load open issues for each machine
    for machine in machines:
        machine.open_issues = db.query(models.Issue).filter(
            models.Issue.machine_id == machine.id,
            models.Issue.status.in_([models.IssueStatus.open, models.IssueStatus.in_progress])
        ).order_by(desc(models.Issue.reported_at)).all()
    
    return machines

def search_machines_with_open_issues(db: Session, query: str) -> List[models.Machine]:
    """Search machines with their open issues loaded for dashboard display"""
    search_term = f"%{query}%"
    machines = db.query(models.Machine).filter(
        (models.Machine.name.ilike(search_term)) |
        (models.Machine.serial_number.ilike(search_term)) |
        (models.Machine.location.ilike(search_term))
    ).order_by(desc(models.Machine.created_at)).all()
    
    # Load open issues for each machine
    for machine in machines:
        machine.open_issues = db.query(models.Issue).filter(
            models.Issue.machine_id == machine.id,
            models.Issue.status.in_([models.IssueStatus.open, models.IssueStatus.in_progress])
        ).order_by(desc(models.Issue.reported_at)).all()
    
    return machines

def create_machine(db: Session, machine: schemas.MachineCreate) -> models.Machine:
    db_machine = models.Machine(
        **machine.dict(),
        public_slug=ensure_unique_slug(db)
    )
    db.add(db_machine)
    db.commit()
    db.refresh(db_machine)
    return db_machine

def update_machine(db: Session, machine_id: int, machine_update: schemas.MachineUpdate) -> Optional[models.Machine]:
    db_machine = get_machine(db, machine_id)
    if db_machine:
        update_data = machine_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_machine, field, value)
        setattr(db_machine, 'updated_at', datetime.utcnow())
        db.commit()
        db.refresh(db_machine)
    return db_machine

def delete_machine(db: Session, machine_id: int) -> bool:
    db_machine = get_machine(db, machine_id)
    if db_machine:
        db.delete(db_machine)
        db.commit()
        return True
    return False

# Issue CRUD operations
def get_issue(db: Session, issue_id: int) -> Optional[models.Issue]:
    return db.query(models.Issue).filter(models.Issue.id == issue_id).first()

def get_machine_issues(db: Session, machine_id: int, status_filter: Optional[str] = None) -> List[models.Issue]:
    query = db.query(models.Issue).filter(models.Issue.machine_id == machine_id)
    
    if status_filter:
        query = query.filter(models.Issue.status == status_filter)
    
    return query.order_by(desc(models.Issue.reported_at)).all()

def get_open_issues(db: Session, machine_id: int) -> List[models.Issue]:
    return db.query(models.Issue).filter(
        models.Issue.machine_id == machine_id,
        models.Issue.status.in_([models.IssueStatus.open, models.IssueStatus.in_progress])
    ).order_by(desc(models.Issue.reported_at)).all()

def get_closed_issues(db: Session, machine_id: int, skip: int = 0, limit: int = 20) -> List[models.Issue]:
    return db.query(models.Issue).filter(
        models.Issue.machine_id == machine_id,
        models.Issue.status == models.IssueStatus.closed
    ).order_by(desc(models.Issue.closed_at)).offset(skip).limit(limit).all()

def create_issue(db: Session, issue: schemas.IssueCreate) -> models.Issue:
    issue_data = issue.dict()
    if not issue_data.get('reported_at'):
        issue_data['reported_at'] = datetime.utcnow()
    
    db_issue = models.Issue(**issue_data)
    db.add(db_issue)
    db.commit()
    db.refresh(db_issue)
    return db_issue

def update_issue_status(db: Session, issue_id: int, status: models.IssueStatus) -> Optional[models.Issue]:
    db_issue = get_issue(db, issue_id)
    if db_issue:
        setattr(db_issue, 'status', status)
        if status == models.IssueStatus.closed:
            setattr(db_issue, 'closed_at', datetime.utcnow())
        db.commit()
        db.refresh(db_issue)
    return db_issue

# Issue Update CRUD operations
def get_issue_updates(db: Session, issue_id: int) -> List[models.IssueUpdate]:
    return db.query(models.IssueUpdate).filter(
        models.IssueUpdate.issue_id == issue_id
    ).order_by(desc(models.IssueUpdate.created_at)).all()

def create_issue_update(db: Session, update: schemas.IssueUpdateCreate) -> models.IssueUpdate:
    db_update = models.IssueUpdate(**update.dict())
    db.add(db_update)
    
    # If status change is specified, update the issue status
    if update.status_change:
        update_issue_status(db, update.issue_id, update.status_change)
    
    db.commit()
    db.refresh(db_update)
    return db_update

# Maintenance CRUD operations
def get_maintenance_records(db: Session, machine_id: int, limit: int = 5) -> List[models.Maintenance]:
    return db.query(models.Maintenance).filter(
        models.Maintenance.machine_id == machine_id
    ).order_by(desc(models.Maintenance.performed_at)).limit(limit).all()

def get_all_maintenance_records(db: Session, machine_id: int) -> List[models.Maintenance]:
    return db.query(models.Maintenance).filter(
        models.Maintenance.machine_id == machine_id
    ).order_by(desc(models.Maintenance.performed_at)).all()

def create_maintenance(db: Session, maintenance: schemas.MaintenanceCreate) -> models.Maintenance:
    maintenance_data = maintenance.dict()
    if not maintenance_data.get('performed_at'):
        maintenance_data['performed_at'] = datetime.utcnow()
    
    db_maintenance = models.Maintenance(**maintenance_data)
    db.add(db_maintenance)
    db.commit()
    db.refresh(db_maintenance)
    return db_maintenance

# Employee CRUD operations
def get_employee(db: Session, employee_id: int) -> Optional[models.Employee]:
    return db.query(models.Employee).filter(models.Employee.id == employee_id).first()

def get_employee_by_email(db: Session, email: str) -> Optional[models.Employee]:
    return db.query(models.Employee).filter(models.Employee.email == email).first()

def get_employee_by_employee_id(db: Session, employee_id: str) -> Optional[models.Employee]:
    return db.query(models.Employee).filter(models.Employee.employee_id == employee_id).first()

def get_employees(db: Session, skip: int = 0, limit: int = 100, include_inactive: bool = False) -> List[models.Employee]:
    query = db.query(models.Employee)
    
    if not include_inactive:
        query = query.filter(models.Employee.is_active == 1)
    
    return query.order_by(desc(models.Employee.created_at)).offset(skip).limit(limit).all()

def search_employees(db: Session, query: str, include_inactive: bool = False) -> List[models.Employee]:
    search_term = f"%{query}%"
    db_query = db.query(models.Employee).filter(
        (models.Employee.first_name.ilike(search_term)) |
        (models.Employee.last_name.ilike(search_term)) |
        (models.Employee.email.ilike(search_term)) |
        (models.Employee.employee_id.ilike(search_term)) |
        (models.Employee.department.ilike(search_term)) |
        (models.Employee.position.ilike(search_term))
    )
    
    if not include_inactive:
        db_query = db_query.filter(models.Employee.is_active == 1)
    
    return db_query.order_by(desc(models.Employee.created_at)).all()

def create_employee(db: Session, employee: schemas.EmployeeCreate) -> models.Employee:
    # Check if email already exists
    existing_email = get_employee_by_email(db, employee.email)
    if existing_email:
        raise ValueError("Email already exists")
    
    # Check if employee_id already exists
    existing_employee_id = get_employee_by_employee_id(db, employee.employee_id)
    if existing_employee_id:
        raise ValueError("Employee ID already exists")
    
    db_employee = models.Employee(**employee.dict())
    db.add(db_employee)
    db.commit()
    db.refresh(db_employee)
    return db_employee

def update_employee(db: Session, employee_id: int, employee_update: schemas.EmployeeUpdate) -> Optional[models.Employee]:
    db_employee = get_employee(db, employee_id)
    if not db_employee:
        return None
    
    update_data = employee_update.dict(exclude_unset=True)
    
    # Check for email conflicts if email is being updated
    if 'email' in update_data and update_data['email'] != db_employee.email:
        existing_email = get_employee_by_email(db, update_data['email'])
        if existing_email:
            raise ValueError("Email already exists")
    
    # Check for employee_id conflicts if employee_id is being updated
    if 'employee_id' in update_data and update_data['employee_id'] != db_employee.employee_id:
        existing_employee_id = get_employee_by_employee_id(db, update_data['employee_id'])
        if existing_employee_id:
            raise ValueError("Employee ID already exists")
    
    for field, value in update_data.items():
        setattr(db_employee, field, value)
    
    setattr(db_employee, 'updated_at', datetime.utcnow())
    db.commit()
    db.refresh(db_employee)
    return db_employee

def delete_employee(db: Session, employee_id: int) -> bool:
    """Soft delete employee by setting is_active to 0"""
    db_employee = get_employee(db, employee_id)
    if db_employee:
        setattr(db_employee, 'is_active', 0)
        setattr(db_employee, 'updated_at', datetime.utcnow())
        db.commit()
        return True
    return False

def reactivate_employee(db: Session, employee_id: int) -> bool:
    """Reactivate employee by setting is_active to 1"""
    db_employee = get_employee(db, employee_id)
    if db_employee:
        setattr(db_employee, 'is_active', 1)
        setattr(db_employee, 'updated_at', datetime.utcnow())
        db.commit()
        return True
    return False