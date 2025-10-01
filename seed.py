#!/usr/bin/env python3
"""
Seed script for Machine Manual application
Creates sample machines, issues, and maintenance records for testing
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import os
import sys

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import models
import crud
import schemas
from main import generate_machine_qr_code

# Database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./app.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_sample_data():
    """Create sample machines with issues and maintenance records"""
    
    # Create all tables
    models.Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        print("Creating sample machines...")
        
        # Create Machine 1: Production Line A
        machine1_data = schemas.MachineCreate(
            name="Produktionslinie A",
            serial_number="PL-A-2023-001",
            location="Halle 1, Platz 5",
            description="Hauptproduktionslinie für Komponenten"
        )
        machine1 = crud.create_machine(db, machine1_data)
        print(f"Created machine: {machine1.name} (slug: {machine1.public_slug})")
        
        # Generate QR code for machine 1
        generate_machine_qr_code(machine1.public_slug, "http://localhost:5000")
        
        # Create Machine 2: CNC Fräsmaschine
        machine2_data = schemas.MachineCreate(
            name="CNC Fräsmaschine DMU 50",
            serial_number="DMU50-2022-003",
            location="Halle 2, Platz 12",
            description="Hochpräzisions-CNC-Fräsmaschine für Prototypen"
        )
        machine2 = crud.create_machine(db, machine2_data)
        print(f"Created machine: {machine2.name} (slug: {machine2.public_slug})")
        
        # Generate QR code for machine 2
        generate_machine_qr_code(machine2.public_slug, "http://localhost:5000")
        
        print("Creating sample issues...")
        
        # Create issues for Machine 1
        # Open issue 1
        issue1_data = schemas.IssueCreate(
            machine_id=machine1.id,
            title="Hydraulikdruck zu niedrig",
            description="Die Maschine zeigt einen Hydraulikdruckfehler an. Druck liegt bei 45 bar statt der erforderlichen 60 bar.",
            reported_by="Hans Müller",
            reported_at=datetime.utcnow() - timedelta(hours=3)
        )
        issue1 = crud.create_issue(db, issue1_data)
        
        # Open issue 2
        issue2_data = schemas.IssueCreate(
            machine_id=machine1.id,
            title="Ungewöhnliche Geräusche aus Getriebe",
            description="Seit heute Morgen sind klackende Geräusche aus dem Hauptgetriebe zu hören.",
            reported_by="Maria Schmidt",
            reported_at=datetime.utcnow() - timedelta(hours=1, minutes=30)
        )
        issue2 = crud.create_issue(db, issue2_data)
        
        # Closed issue
        issue3_data = schemas.IssueCreate(
            machine_id=machine1.id,
            title="Temperatursensor defekt",
            description="Temperatursensor T1 zeigt unrealistische Werte an.",
            reported_by="Klaus Weber",
            reported_at=datetime.utcnow() - timedelta(days=2)
        )
        issue3 = crud.create_issue(db, issue3_data)
        crud.update_issue_status(db, issue3.id, models.IssueStatus.closed)
        
        # Create issues for Machine 2
        # In progress issue
        issue4_data = schemas.IssueCreate(
            machine_id=machine2.id,
            title="Spindel vibriert bei hohen Drehzahlen",
            description="Ab 8000 U/min entstehen starke Vibrationen an der Hauptspindel.",
            reported_by="Stefan Fischer",
            reported_at=datetime.utcnow() - timedelta(hours=6)
        )
        issue4 = crud.create_issue(db, issue4_data)
        crud.update_issue_status(db, issue4.id, models.IssueStatus.in_progress)
        
        # Closed issue for machine 2
        issue5_data = schemas.IssueCreate(
            machine_id=machine2.id,
            title="Kühlmittelmangel",
            description="Kühlmitteltank war leer, Produktion gestoppt.",
            reported_by="Anna Kramer",
            reported_at=datetime.utcnow() - timedelta(days=1)
        )
        issue5 = crud.create_issue(db, issue5_data)
        crud.update_issue_status(db, issue5.id, models.IssueStatus.closed)
        
        print("Creating issue updates...")
        
        # Add updates to some issues
        update1_data = schemas.IssueUpdateCreate(
            issue_id=issue1.id,
            note="Hydraulikfilter wurde überprüft - ist sauber. Problem liegt vermutlich an der Pumpe.",
            author="Servicetechniker Tom",
            status_change=models.IssueStatus.in_progress
        )
        crud.create_issue_update(db, update1_data)
        
        update2_data = schemas.IssueUpdateCreate(
            issue_id=issue4.id,
            note="Spindellager wurden untersucht. Lager 2 zeigt Verschleißspuren. Ersatzteil bestellt.",
            author="Mechaniker Paul"
        )
        crud.create_issue_update(db, update2_data)
        
        print("Creating maintenance records...")
        
        # Create maintenance records
        maintenance1_data = schemas.MaintenanceCreate(
            machine_id=machine1.id,
            title="Quartalsinspektion Q3/2024",
            description="Routine-Quartalsinspektion: Ölwechsel, Filter getauscht, Verschleißteile geprüft",
            performed_by="Wartungsteam Alpha",
            performed_at=datetime.utcnow() - timedelta(days=7),
            next_due_at=datetime.utcnow() + timedelta(days=83)  # ~3 months
        )
        crud.create_maintenance(db, maintenance1_data)
        
        maintenance2_data = schemas.MaintenanceCreate(
            machine_id=machine1.id,
            title="Hydrauliköl-Wechsel",
            description="Hydrauliköl ISO VG 46 gewechselt, Filters erneuert",
            performed_by="Hydraulik-Service GmbH",
            performed_at=datetime.utcnow() - timedelta(days=14)
        )
        crud.create_maintenance(db, maintenance2_data)
        
        maintenance3_data = schemas.MaintenanceCreate(
            machine_id=machine2.id,
            title="Spindel-Justierung",
            description="Spindel ausgerichtet und neu kalibriert nach Vibrationsproblemen",
            performed_by="CNC-Spezialist Meyer",
            performed_at=datetime.utcnow() - timedelta(days=3),
            next_due_at=datetime.utcnow() + timedelta(days=180)  # 6 months
        )
        crud.create_maintenance(db, maintenance3_data)
        
        maintenance4_data = schemas.MaintenanceCreate(
            machine_id=machine2.id,
            title="Werkzeugwechsler kalibriert",
            description="Automatischen Werkzeugwechsler neu kalibriert und getestet",
            performed_by="Automatisierungstechnik Nord",
            performed_at=datetime.utcnow() - timedelta(days=21)
        )
        crud.create_maintenance(db, maintenance4_data)
        
        print("✅ Sample data created successfully!")
        print(f"Created 2 machines:")
        print(f"  - {machine1.name} (Public: /m/{machine1.public_slug})")
        print(f"  - {machine2.name} (Public: /m/{machine2.public_slug})")
        print(f"Created 5 issues (2 open, 1 in progress, 2 closed)")
        print(f"Created 4 maintenance records")
        print(f"QR codes generated in static/qrcodes/")
        
    except Exception as e:
        print(f"❌ Error creating sample data: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("🔧 Machine Manual - Seed Script")
    print("===============================")
    create_sample_data()
    print("Script completed!")