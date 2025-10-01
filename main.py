from fastapi import FastAPI, Depends, HTTPException, Request, Form, File, UploadFile
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
import os
import qrcode
import io
import csv
import secrets
from typing import Optional, List
import uvicorn

import models
import schemas
import crud

# Database setup (Supabase / Postgres)
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")

# Wenn Postgres (Supabase), KEINE connect_args verwenden
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Create tables
models.Base.metadata.create_all(bind=engine)

# FastAPI app
app = FastAPI(title="Maschinenhandbuch", description="Machine Manual Web Application")

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Create necessary directories
os.makedirs("static/qrcodes", exist_ok=True)
os.makedirs("templates", exist_ok=True)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Security for admin routes
security = HTTPBasic()

def verify_admin_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """Simple HTTP Basic authentication for admin access"""
    correct_username = secrets.compare_digest(credentials.username, "admin")
    correct_password = secrets.compare_digest(credentials.password, "admin123")
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=401,
            detail="Invalid admin credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

def generate_machine_qr_code(slug: str, base_url: str = "http://localhost:8000") -> str:
    """Generate QR code for machine public link"""
    qr_url = f"{base_url}/m/{slug}"
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(qr_url)
    qr.make(fit=True)
    
    qr_image = qr.make_image(fill_color="black", back_color="white")
    qr_path = f"static/qrcodes/{slug}.png"
    qr_image.save(qr_path)
    return qr_path

# Dashboard / Home page
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, search: Optional[str] = None, db: Session = Depends(get_db)):
    machines = []
    if search:
        machines = crud.search_machines_with_open_issues(db, search)
    else:
        machines = crud.get_machines_with_open_issues(db, limit=10)
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "machines": machines,
        "search_query": search or ""
    })

# Machine management routes
@app.get("/machines/new", response_class=HTMLResponse)
async def new_machine_form(request: Request):
    return templates.TemplateResponse("machine_new.html", {"request": request})

@app.post("/machines", response_class=HTMLResponse)
async def create_machine(
    request: Request,
    name: str = Form(...),
    serial_number: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    machine_data = schemas.MachineCreate(
        name=name,
        serial_number=serial_number if serial_number else None,
        location=location if location else None,
        description=description if description else None
    )
    
    machine = crud.create_machine(db, machine_data)
    
    # Generate QR code
    base_url = str(request.base_url).rstrip('/')
    generate_machine_qr_code(str(machine.public_slug), base_url)
    
    return templates.TemplateResponse("machine_created.html", {
        "request": request,
        "machine": machine,
        "qr_path": f"/static/qrcodes/{machine.public_slug}.png"
    })

@app.get("/machines/{machine_id}", response_class=HTMLResponse)
async def machine_detail(request: Request, machine_id: int, db: Session = Depends(get_db)):
    machine = crud.get_machine(db, machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")
    
    open_issues = crud.get_open_issues(db, int(machine.id))
    closed_issues = crud.get_closed_issues(db, int(machine.id), limit=10)
    maintenance = crud.get_maintenance_records(db, int(machine.id))
    
    return templates.TemplateResponse("machine_detail.html", {
        "request": request,
        "machine": machine,
        "open_issues": open_issues,
        "closed_issues": closed_issues,
        "maintenance": maintenance,
        "qr_path": f"/static/qrcodes/{machine.public_slug}.png"
    })

# Public machine access
@app.get("/m/{slug}", response_class=HTMLResponse)
async def public_machine(request: Request, slug: str, db: Session = Depends(get_db)):
    machine = crud.get_machine_by_slug(db, slug)
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")
    
    open_issues = crud.get_open_issues(db, int(machine.id))
    closed_issues = crud.get_closed_issues(db, int(machine.id), limit=5)
    maintenance = crud.get_maintenance_records(db, int(machine.id))
    
    return templates.TemplateResponse("public_machine.html", {
        "request": request,
        "machine": machine,
        "open_issues": open_issues,
        "closed_issues": closed_issues,
        "maintenance": maintenance
    })

# Issue management routes
@app.get("/issues/new", response_class=HTMLResponse)
async def new_issue_form(request: Request, machine: Optional[str] = None, db: Session = Depends(get_db)):
    machine_obj = None
    if machine:
        if machine.isdigit():
            machine_obj = crud.get_machine(db, int(machine))
        else:
            machine_obj = crud.get_machine_by_slug(db, machine)
    
    if not machine_obj:
        raise HTTPException(status_code=404, detail="Machine not found")
    
    # Get active employees for dropdown
    employees = crud.get_employees(db, limit=1000, include_inactive=False)
    
    return templates.TemplateResponse("issue_new.html", {
        "request": request,
        "machine": machine_obj,
        "employees": employees
    })

@app.post("/issues", response_class=HTMLResponse)
async def create_issue(
    request: Request,
    machine_id: int = Form(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    reported_by: int = Form(...),
    reported_at: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    # Parse datetime if provided
    reported_datetime = None
    if reported_at:
        try:
            reported_datetime = datetime.fromisoformat(reported_at.replace('T', ' '))
        except ValueError:
            reported_datetime = datetime.utcnow()
    
    # Get employee info for the reported_by field
    employee = crud.get_employee(db, reported_by)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    issue_data = schemas.IssueCreate(
        machine_id=machine_id,
        title=title,
        description=description,
        reported_by=f"{employee.first_name} {employee.last_name}",
        reported_at=reported_datetime
    )
    
    issue = crud.create_issue(db, issue_data)
    machine = crud.get_machine(db, machine_id)
    
    # Redirect to public machine page
    return templates.TemplateResponse("issue_created.html", {
        "request": request,
        "issue": issue,
        "machine": machine
    })

@app.get("/issues/{issue_id}", response_class=HTMLResponse)
async def issue_detail(request: Request, issue_id: int, db: Session = Depends(get_db)):
    issue = crud.get_issue(db, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    
    updates = crud.get_issue_updates(db, issue_id)
    machine = crud.get_machine(db, int(issue.machine_id))
    
    # Get active employees for dropdown
    employees = crud.get_employees(db, limit=1000, include_inactive=False)
    
    return templates.TemplateResponse("issue_detail.html", {
        "request": request,
        "issue": issue,
        "updates": updates,
        "machine": machine,
        "employees": employees
    })

@app.post("/issues/{issue_id}/updates")
async def create_issue_update(
    issue_id: int,
    note: str = Form(...),
    author: int = Form(...),
    status_change: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    status_enum = None
    if status_change and status_change in [s.value for s in models.IssueStatus]:
        status_enum = models.IssueStatus(status_change)
    
    # Get employee info for the author field
    employee = crud.get_employee(db, author)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    update_data = schemas.IssueUpdateCreate(
        issue_id=issue_id,
        note=note,
        author=f"{employee.first_name} {employee.last_name}",
        status_change=status_enum
    )
    
    crud.create_issue_update(db, update_data)
    return {"success": True}

@app.post("/issues/{issue_id}/close")
async def close_issue(issue_id: int, db: Session = Depends(get_db)):
    crud.update_issue_status(db, issue_id, models.IssueStatus.closed)
    return {"success": True}

# Maintenance routes
@app.get("/maintenance/new", response_class=HTMLResponse)
async def new_maintenance_form(request: Request, machine: Optional[str] = None, db: Session = Depends(get_db)):
    machine_obj = None
    if machine:
        if machine.isdigit():
            machine_obj = crud.get_machine(db, int(machine))
        else:
            machine_obj = crud.get_machine_by_slug(db, machine)
    
    if not machine_obj:
        raise HTTPException(status_code=404, detail="Machine not found")
    
    return templates.TemplateResponse("maintenance_new.html", {
        "request": request,
        "machine": machine_obj
    })

@app.post("/maintenance", response_class=HTMLResponse)
async def create_maintenance(
    request: Request,
    machine_id: int = Form(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    performed_by: str = Form(...),
    performed_at: Optional[str] = Form(None),
    next_due_at: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    # Parse datetimes if provided
    performed_datetime = None
    if performed_at:
        try:
            performed_datetime = datetime.fromisoformat(performed_at.replace('T', ' '))
        except ValueError:
            performed_datetime = datetime.utcnow()
    
    next_due_datetime = None
    if next_due_at:
        try:
            next_due_datetime = datetime.fromisoformat(next_due_at.replace('T', ' '))
        except ValueError:
            pass
    
    maintenance_data = schemas.MaintenanceCreate(
        machine_id=machine_id,
        title=title,
        description=description,
        performed_by=performed_by,
        performed_at=performed_datetime,
        next_due_at=next_due_datetime
    )
    
    maintenance = crud.create_maintenance(db, maintenance_data)
    machine = crud.get_machine(db, machine_id)
    
    return templates.TemplateResponse("maintenance_created.html", {
        "request": request,
        "maintenance": maintenance,
        "machine": machine
    })

# Export routes
@app.get("/machines/{machine_id}/export/issues")
async def export_issues_csv(machine_id: int, db: Session = Depends(get_db)):
    machine = crud.get_machine(db, machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")
    
    issues = crud.get_machine_issues(db, machine_id)
    
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['ID', 'Titel', 'Beschreibung', 'Gemeldet von', 'Gemeldet am', 'Status', 'Geschlossen am'])
    
    for issue in issues:
        writer.writerow([
            issue.id,
            issue.title,
            issue.description if issue.description else '',
            issue.reported_by,
            issue.reported_at.strftime('%Y-%m-%d %H:%M:%S'),
            issue.status.value,
            issue.closed_at.strftime('%Y-%m-%d %H:%M:%S') if issue.closed_at else ''
        ])
    
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=stoerungen_{machine.name}_{datetime.now().strftime('%Y%m%d')}.csv"}
    )

@app.get("/machines/{machine_id}/export/maintenance")
async def export_maintenance_csv(machine_id: int, db: Session = Depends(get_db)):
    machine = crud.get_machine(db, machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")
    
    maintenance_records = crud.get_all_maintenance_records(db, machine_id)
    
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['ID', 'Titel', 'Beschreibung', 'Durchgeführt von', 'Durchgeführt am', 'Nächste Wartung'])
    
    for record in maintenance_records:
        writer.writerow([
            record.id,
            record.title,
            record.description if record.description else '',
            record.performed_by,
            record.performed_at.strftime('%Y-%m-%d %H:%M:%S'),
            record.next_due_at.strftime('%Y-%m-%d %H:%M:%S') if record.next_due_at else ''
        ])
    
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=wartungen_{machine.name}_{datetime.now().strftime('%Y%m%d')}.csv"}
    )

# Admin Routes
@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: Session = Depends(get_db), admin_user: str = Depends(verify_admin_credentials)):
    # Get overview statistics
    total_machines = len(crud.get_machines(db, limit=1000))
    total_employees = len(crud.get_employees(db, limit=1000))
    open_issues_count = len([issue for machine in crud.get_machines_with_open_issues(db, limit=1000) for issue in machine.open_issues])
    
    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request,
        "total_machines": total_machines,
        "total_employees": total_employees,
        "open_issues_count": open_issues_count
    })

# Employee management routes
@app.get("/admin/employees", response_class=HTMLResponse)
async def admin_employees_list(request: Request, search: Optional[str] = None, include_inactive: bool = False, db: Session = Depends(get_db), admin_user: str = Depends(verify_admin_credentials)):
    employees = []
    if search:
        employees = crud.search_employees(db, search, include_inactive=include_inactive)
    else:
        employees = crud.get_employees(db, limit=100, include_inactive=include_inactive)
    
    return templates.TemplateResponse("admin_employees.html", {
        "request": request,
        "employees": employees,
        "search_query": search or "",
        "include_inactive": include_inactive
    })

@app.get("/admin/employees/new", response_class=HTMLResponse)
async def admin_new_employee_form(request: Request, admin_user: str = Depends(verify_admin_credentials)):
    return templates.TemplateResponse("admin_employee_form.html", {
        "request": request,
        "employee": None,
        "action": "create"
    })

@app.post("/admin/employees", response_class=HTMLResponse)
async def admin_create_employee(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    phone: Optional[str] = Form(None),
    department: Optional[str] = Form(None),
    position: Optional[str] = Form(None),
    employee_id: str = Form(...),
    is_active: int = Form(1),
    db: Session = Depends(get_db),
    admin_user: str = Depends(verify_admin_credentials)
):
    try:
        employee_data = schemas.EmployeeCreate(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone if phone else None,
            department=department if department else None,
            position=position if position else None,
            employee_id=employee_id,
            is_active=is_active
        )
        
        employee = crud.create_employee(db, employee_data)
        
        # Redirect to employees list with success message
        employees = crud.get_employees(db, limit=100)
        return templates.TemplateResponse("admin_employees.html", {
            "request": request,
            "employees": employees,
            "search_query": "",
            "include_inactive": False,
            "success_message": f"Mitarbeiter {employee.first_name} {employee.last_name} wurde erfolgreich erstellt."
        })
        
    except ValueError as e:
        return templates.TemplateResponse("admin_employee_form.html", {
            "request": request,
            "employee": None,
            "action": "create",
            "error_message": str(e),
            "form_data": {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "phone": phone,
                "department": department,
                "position": position,
                "employee_id": employee_id,
                "is_active": is_active
            }
        })

@app.get("/admin/employees/{employee_id}", response_class=HTMLResponse)
async def admin_edit_employee_form(request: Request, employee_id: int, db: Session = Depends(get_db), admin_user: str = Depends(verify_admin_credentials)):
    employee = crud.get_employee(db, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    return templates.TemplateResponse("admin_employee_form.html", {
        "request": request,
        "employee": employee,
        "action": "edit"
    })

@app.post("/admin/employees/{employee_id}")
async def admin_update_employee(
    request: Request,
    employee_id: int,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    phone: Optional[str] = Form(None),
    department: Optional[str] = Form(None),
    position: Optional[str] = Form(None),
    employee_id_field: str = Form(...),
    is_active: int = Form(1),
    db: Session = Depends(get_db),
    admin_user: str = Depends(verify_admin_credentials)
):
    try:
        employee_update = schemas.EmployeeUpdate(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone if phone else None,
            department=department if department else None,
            position=position if position else None,
            employee_id=employee_id_field,
            is_active=is_active
        )
        
        employee = crud.update_employee(db, employee_id, employee_update)
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        # Redirect to employees list with success message
        employees = crud.get_employees(db, limit=100)
        return templates.TemplateResponse("admin_employees.html", {
            "request": request,
            "employees": employees,
            "search_query": "",
            "include_inactive": False,
            "success_message": f"Mitarbeiter {employee.first_name} {employee.last_name} wurde erfolgreich aktualisiert."
        })
        
    except ValueError as e:
        employee = crud.get_employee(db, employee_id)
        return templates.TemplateResponse("admin_employee_form.html", {
            "request": request,
            "employee": employee,
            "action": "edit",
            "error_message": str(e),
            "form_data": {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "phone": phone,
                "department": department,
                "position": position,
                "employee_id": employee_id_field,
                "is_active": is_active
            }
        })

@app.post("/admin/employees/{employee_id}/delete")
async def admin_delete_employee(employee_id: int, db: Session = Depends(get_db), admin_user: str = Depends(verify_admin_credentials)):
    employee = crud.get_employee(db, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    success = crud.delete_employee(db, employee_id)
    if success:
        return JSONResponse({"success": True, "message": f"Mitarbeiter {employee.first_name} {employee.last_name} wurde deaktiviert."})
    else:
        return JSONResponse({"success": False, "message": "Fehler beim Löschen des Mitarbeiters."})

@app.post("/admin/employees/{employee_id}/reactivate")
async def admin_reactivate_employee(employee_id: int, db: Session = Depends(get_db), admin_user: str = Depends(verify_admin_credentials)):
    employee = crud.get_employee(db, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    success = crud.reactivate_employee(db, employee_id)
    if success:
        return JSONResponse({"success": True, "message": f"Mitarbeiter {employee.first_name} {employee.last_name} wurde reaktiviert."})
    else:
        return JSONResponse({"success": False, "message": "Fehler beim Reaktivieren des Mitarbeiters."})

# Machine deletion route
@app.post("/admin/machines/{machine_id}/delete")
async def admin_delete_machine(machine_id: int, db: Session = Depends(get_db), admin_user: str = Depends(verify_admin_credentials)):
    machine = crud.get_machine(db, machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")
    
    success = crud.delete_machine(db, machine_id)
    if success:
        return JSONResponse({"success": True, "message": f"Maschine {machine.name} wurde erfolgreich gelöscht."})
    else:
        return JSONResponse({"success": False, "message": "Fehler beim Löschen der Maschine."})

# API Routes
@app.get("/api/machines", response_model=List[schemas.Machine])
async def api_get_machines(db: Session = Depends(get_db)):
    return crud.get_machines(db)

@app.post("/api/machines", response_model=schemas.Machine)
async def api_create_machine(machine: schemas.MachineCreate, db: Session = Depends(get_db)):
    return crud.create_machine(db, machine)

@app.get("/api/machines/{machine_id}/issues", response_model=List[schemas.Issue])
async def api_get_machine_issues(machine_id: int, db: Session = Depends(get_db)):
    return crud.get_machine_issues(db, machine_id)

@app.post("/api/machines/{machine_id}/issues", response_model=schemas.Issue)
async def api_create_issue(machine_id: int, issue: schemas.IssueCreate, db: Session = Depends(get_db)):
    issue.machine_id = machine_id
    return crud.create_issue(db, issue)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)
