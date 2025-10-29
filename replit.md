# Hack Club Dashboard

## Overview

The Hack Club Dashboard is a comprehensive web application built with Flask that enables Hack Club leaders to manage their clubs, track member attendance, showcase projects, and engage with their community. The application has been fully modularized from a monolithic codebase into a clean, maintainable architecture with proper separation of concerns across models, routes, services, and utilities.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Application Framework
- **Backend**: Flask web framework with SQLAlchemy ORM
- **Application Factory Pattern**: The app uses `create_app()` factory function for initialization and configuration
- **Extension Management**: Flask extensions (SQLAlchemy, Flask-Limiter) are initialized centrally in `extensions.py` and bound to the app during creation
- **Configuration**: Environment-based configuration using `python-dotenv` with fallback mechanisms for secret key generation

### Database Architecture
- **ORM**: SQLAlchemy for database abstraction
- **Database Type**: PostgreSQL (with URL conversion handling for legacy `postgres://` schemes)
- **Model Organization**: Domain-driven model separation across 13 model files:
  - User management (users, roles, permissions, audit logs)
  - Authentication (API keys, OAuth)
  - Club management (clubs, memberships, cosmetics)
  - Content (posts, assignments, meetings, resources)
  - Social features (chat, attendance, gallery)
  - Economy system (transactions, quests, projects)
  - System configuration (settings, status pages)

### Route Structure (Blueprint Pattern)
The application organizes routes into 10 functional blueprints:
- **Main Routes**: Home, dashboard, gallery, leaderboard
- **Auth Routes**: Login/signup, password reset, OAuth integrations (Slack, Hack Club Identity)
- **Clubs Routes**: Club-specific features (shop, orders, projects, poster editor)
- **Blog Routes**: Blog creation and viewing
- **Admin Routes**: Administrative dashboard, user/club management, review systems
- **API Routes**: RESTful API endpoints with OAuth2 support
- **Status Routes**: System health monitoring
- **Shop Routes**: Token-based shop system
- **OAuth Routes**: Third-party application authorization
- **Chat Routes**: Real-time club messaging

### Security & Access Control
- **RBAC System**: Role-Based Access Control with permissions and roles
- **Custom Decorators**: Authentication (`login_required`, `admin_required`), authorization (`permission_required`, `role_required`), and feature protection (`economy_required`)
- **Rate Limiting**: Flask-Limiter for API and route protection (memory-based storage)
- **Input Sanitization**: Comprehensive XSS prevention and profanity filtering using `better-profanity`
- **Audit Logging**: User action tracking for administrative oversight
- **IP Tracking**: Registration and login IP monitoring

### Frontend Architecture
- **Template Engine**: Jinja2 templates with inheritance from `base.html`
- **Responsive Design**: Mobile-first approach with dedicated mobile templates
- **PWA Support**: Progressive Web App capabilities with service worker and manifest
- **Asset Management**: Static files organized in `/static` directory
- **Client-Side Features**: QR code generation, fabric.js for poster editor, markdown rendering

### Content Processing
- **Markdown Support**: Server-side markdown conversion with `markdown` library
- **Content Sanitization**: HTML sanitization using `bleach` library
- **Image Handling**: Pillow (PIL) for image processing and manipulation

### Economy System
- **Token-Based**: Club and user token management
- **Transactions**: Complete transaction history and balance tracking
- **Quests & Projects**: Gamification features for member engagement
- **Shop System**: Virtual items purchasable with tokens
- **Order Management**: Order submission and administrative review workflow

## External Dependencies

### Third-Party OAuth Providers
- **Slack OAuth**: Member authentication and workspace integration
- **Hack Club Identity**: Official Hack Club authentication system for leader verification

### External APIs & Services
- **Airtable Integration**: Pizza grant application management
- **Hackatime API**: Coding time tracking integration for members

### Infrastructure Services
- **Gunicorn**: Production WSGI server with 4 workers, sync worker class
- **Service Worker**: Offline-first caching strategy for static assets

### Python Package Dependencies
- Flask ecosystem: `flask`, `flask-login`, `flask-sqlalchemy`, `flask-limiter`, `Flask-WTF`
- Database: `psycopg2-binary` (PostgreSQL adapter)
- Security: `werkzeug` (password hashing), `better-profanity`
- Utilities: `requests`, `python-dotenv`, `Pillow`, `markdown`, `bleach`
- Production: `gunicorn`

### Database Schema Considerations
The application uses SQLAlchemy's declarative base for ORM models but does not explicitly commit to a specific database backend in code - PostgreSQL is configured via `DATABASE_URL` environment variable. The schema supports:
- User authentication and authorization (multi-role, multi-permission)
- Club hierarchies with leaders, co-leaders, and members
- Content management (posts, assignments, meetings, resources)
- Social features (chat, attendance, gallery posts)
- Economic transactions and gamification
- System administration and monitoring