from fastapi import FastAPI, Depends, HTTPException, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
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

# =========================
# Datenbank (Supabase / PG)
# =========================
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")

# Falls jemand +psycopg in der URL hat -> auf +psycopg2 umbiegen
if SQLALCHEMY_DATABASE_URL.startswith("postgresql+psycopg://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace(
        "postgresql+psycopg://", "postgresql+psycopg2://"
    )

if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
else:
    # Serverless-freundliche Einstellungen
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=0,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# =========
# FastAPI
# =========
app = FastAPI(title="Maschinenhandbuch", description="Machine Manual Web Application")

# DB-Ping beim Start (loggt nur, crasht nicht)
@app.on_event("startup")
def _startup_check():
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
    except Exception as e:
        print("DB startup check failed:", repr(e))

# Statische Dateien & Templates (Ordner müssen existieren)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==========
# Security
# ==========
security = HTTPBasic()

def verify_admin_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    user_ok = secrets.compare_digest(credentials.username, "admin")
    pw_ok = secrets.compare_digest(credentials.password, "admin123")
    if not (user_ok and pw_ok):
        raise HTTPException(
            status_code=401,
            detail="Invalid admin credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# ================
# Health / Setup
# ================
@app.get("/healthz")
def healthz():
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": repr(e)}

# Einmalig Tabellen anlegen. Nach Ausführung wieder entfernen.
@app.get("/__init_db_once")
def __init_db_once():
    try:
        models.Base.metadata.create_all(bind=engine)
        return {"ok": True, "msg": "tables created"}
    except Exception as e:
        return {"ok": False, "error": repr(e)}

# =========================
# QR-Codes (ohne Dateisystem)
# =========================
def generate_machine_qr_path(slug: str, base_url: str) -> str:
    return f"/qr/{slug}.png"

@app.get("/qr/{slug}.png")
async def qr_png(slug: str, request: Request):
    base_url = str(request.base_url).rstrip("/")
    qr_url = f"{base_url}/m/{slug}"
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(qr_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")

# =========
# Routes
# =========
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, search: Optional[str] = None, db: Session = Depends(get_db)):
    machines = crud.search_machines_with_open_issues(db, search) if search \
        else crud.get_machines_with_open_issues(db, limit=10)
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "machines": machines,
        "search_query": search or ""
    })

# Machine management
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
        serial_number=serial_number or None,
        location=location or None,
        description=description or None
    )
    machine = crud.create_machine(db, machine_data)
    base_url = str(request.base_url).rstrip("/")
    qr_path = generate_machine_qr_path(str(machine.public_slug), base_url)
    return templates.TemplateResponse("machine_created.html", {
        "request": request,
        "machine": machine,
        "qr_path": qr_path
    })

@app.get("/machines/{machine_id}", response_class=HTMLResponse)
async def machine_detail(request: Request, machine_id: int, db: Session = Depends(get_db)):
    machine = crud.get_machine(db, machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")
    open_issues = crud.get_open_issues(db, int(machine.id))
    closed_issues = crud.get_closed_issues(db, int(machine.id), limit=10)
    maintenance = crud.get_maintenance_records(db, int(machine.id))
    base_url = str(request.base_url).rstrip("/")
    qr_path = generate_machine_qr_path(str(machine.public_slug), base_url)
    return templates.TemplateResponse("machine_detail.html", {
        "request": request,
        "machine": machine,
        "open_issues": open_issues,
        "closed_issues": closed_issues,
        "maintenance": maintenance,
        "qr_path": qr_path
    })

# Public machine view
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

# Issues
@app.get("/issues/new", response_class=HTMLResponse)
async def new_issue_form(request: Request, machine: Optional[str] = None, db: Session = Depends(get_db)):
    machine_obj = None
    if machine:
        machine_obj = crud.get_machine(db, int(machine)) if machine.isdigit() \
            else crud.get_machine_by_slug(db, machine)
    if not machine_obj:
        raise HTTPException(status_code=404, detail="Machine not found")
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
    reported_datetime = None
    if reported_at:
        try:
            reported_datetime = datetime.fromisoformat(reported_at.replace('T', ' '))
        except ValueError:
            reported_datetime = datetime.utcnow()
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

# Maintenance
@app.get("/maintenance/new", response_class=HTMLResponse)
async def new_maintenance_form(request: Request, machine: Optional[str] = None, db: Session = Depends(get_db)):
    machine_obj = None
    if machine:
        machine_obj = crud.get_machine(db, int(machine)) if machine.isdigit() \
            else crud.get_machine_by_slug(db, machine)
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

# Exporte
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
            issue.description or '',
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
    records = crud.get_all_maintenance_records(db, machine_id)
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['ID', 'Titel', 'Beschreibung', 'Durchgeführt von', 'Durchgeführt am', 'Nächste Wartung'])
    for r in records:
        writer.writerow([
            r.id,
            r.title,
            r.description or '',
            r.performed_by,
            r.performed_at.strftime('%Y-%m-%d %H:%M:%S'),
            r.next_due_at.strftime('%Y-%m-%d %H:%M:%S') if r.next_due_at else ''
        ])
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=wartungen_{machine.name}_{datetime.now().strftime('%Y%m%d')}.csv"}
    )

# API
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
