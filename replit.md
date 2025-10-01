# Maschinenhandbuch

## Overview

Maschinenhandbuch is a production-ready full-stack web application for machine manual management in industrial environments. The system enables organizations to track machines, report issues, manage maintenance records, and provide public access through QR codes. Users can report machine problems, track issue resolution progress, and maintain comprehensive maintenance logs through both administrative and public interfaces.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Application Framework
- **Backend Framework**: FastAPI with Python 3.11 for high-performance API development
- **Template Engine**: Jinja2 for server-side rendering with dynamic content
- **Frontend Enhancement**: HTMX for seamless form interactions without full page reloads
- **Styling**: TailwindCSS via CDN for responsive, utility-first styling

### Data Layer
- **Database**: SQLite with file-based storage (app.db) for simplicity and portability
- **ORM**: SQLAlchemy for database operations and schema management
- **Data Validation**: Pydantic schemas for request/response validation and serialization
- **Migration Strategy**: Simple create_all() approach for table creation

### Core Data Models
- **Machine**: Central entity with unique public slugs for QR code access
- **Issue**: Problem tracking with status workflow (open → in_progress → closed)
- **IssueUpdate**: Status change history and progress tracking
- **Maintenance**: Service records with scheduling capabilities
- **Employee**: Staff management with soft-delete functionality and email validation

### Authentication & Access Control
- **Public Access**: Anonymous machine access via unique slug URLs (/m/<slug>)
- **Administrative Access**: HTTP Basic Authentication protected admin interface
- **Admin Credentials**: Username: `admin`, Password: `admin123`
- **Admin Features**: Employee management, machine deletion, system statistics

### Unique Features
- **QR Code Generation**: Automatic QR code creation for machine public links
- **Real-time Countdown**: JavaScript-based issue duration tracking
- **Slug-based URLs**: Human-friendly public machine access
- **Responsive Design**: Mobile-optimized interface for shop floor use
- **Admin Dashboard**: Comprehensive management interface with statistics
- **Employee Management**: Full CRUD operations with soft-delete and email validation
- **Enhanced Dashboard**: Live issue tracking with visual indicators and countdown timers

### File Organization
- Modular architecture with separated concerns (models, schemas, CRUD operations)
- Template-based rendering with shared base template
- Static asset management for QR codes and styling
- Seed script for development data population

## External Dependencies

### Python Packages
- **FastAPI**: Web framework for API development
- **SQLAlchemy**: Database ORM and query builder
- **Pydantic**: Data validation and serialization
- **Uvicorn**: ASGI server for production deployment
- **qrcode[pil]**: QR code generation with image support
- **Jinja2**: Template engine for HTML rendering
- **email-validator**: Email validation for Pydantic EmailStr fields

### Frontend Libraries
- **HTMX**: Dynamic HTML interactions via CDN
- **TailwindCSS**: Utility-first CSS framework via CDN

### File Storage
- **Local filesystem**: QR code image storage in static/qrcodes directory
- **SQLite database**: Single-file database storage for portability

### Deployment
- **Development server**: Built-in Uvicorn server on port 8000
- **Static files**: FastAPI static file serving for assets and QR codes