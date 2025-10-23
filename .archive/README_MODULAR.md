# Hack Club Dashboard - Modular Structure

## Quick Start

The application has been modularized to improve code organization while maintaining full backward compatibility.

### Current Status

- ✅ **Models** - Organized in `app/models/` by domain
- ✅ **Utilities** - Common functions in `app/utils/`
- ✅ **Services** - External integrations in `app/services/`
- ✅ **Decorators** - Auth/permissions in `app/decorators/`
- ✅ **Configuration** - Centralized in `config.py` and `extensions.py`
- 🚧 **Routes** - Still in `main.py` (86 routes ready to migrate)

## File Structure

```
.
├── app/
│   ├── __init__.py              # Application factory
│   ├── decorators/              # Route decorators
│   ├── models/                  # Database models
│   ├── routes/                  # Blueprints (to be populated)
│   ├── services/                # External APIs
│   └── utils/                   # Helper functions
├── config.py                    # Configuration
├── extensions.py                # Flask extensions
├── main.py                      # Original (16K lines)
├── main_refactored.py           # Modular template
└── MODULARIZATION.md            # Detailed guide
```

## Using the Modular Code

### Option 1: Keep Original (No Changes)

Your current `main.py` works as-is. No action required.

### Option 2: Use Modular Components (Recommended)

Replace imports in `main.py`:

```python
# Instead of defining functions in main.py:
def sanitize_string(value):
    # ... code ...

# Import from utils:
from app.utils.sanitization import sanitize_string
```

### Option 3: Full Refactor (Future)

When ready to migrate routes to blueprints, see `MODULARIZATION.md`.

## Key Modules

### Models (`app/models/`)

All database models organized by domain:

```python
from app.models.user import User, Role
from app.models.club import Club, ClubMembership
from app.models.economy import ClubTransaction
```

### Utilities (`app/utils/`)

Common helper functions:

```python
from app.utils.sanitization import sanitize_string, sanitize_url
from app.utils.security import get_real_ip, add_security_headers
from app.utils.auth_helpers import get_current_user
from app.utils.economy_helpers import create_club_transaction
```

### Decorators (`app/decorators/`)

Route protection:

```python
from app.decorators.auth import login_required, admin_required
from app.decorators.economy import economy_required

@app.route('/admin')
@admin_required
def admin_panel():
    pass
```

### Services (`app/services/`)

External API integrations:

```python
from app.services.airtable import AirtableService
from app.services.identity import HackClubIdentityService
```

## Benefits

1. **Organized Code** - Find functions easily
2. **Reusable Components** - Import what you need
3. **Easier Testing** - Test individual modules
4. **Better Collaboration** - Less merge conflicts
5. **Clearer Dependencies** - See what imports what

## Migration Path

### Immediate (No Risk)

1. Review `main_refactored.py`
2. Copy your routes into it
3. Test locally
4. Deploy when ready

### Gradual (Recommended)

1. Pick one route group (e.g., auth)
2. Move to `app/routes/auth.py` as a blueprint
3. Test thoroughly
4. Repeat for other groups

### Full (Future)

1. All routes in blueprints
2. Use `app/__init__.py` application factory
3. Slim down `main.py` to entry point only

## Important Files

- `app/__init__.py` - Application factory (ready for blueprints)
- `config.py` - All configuration settings
- `extensions.py` - Database and rate limiter
- `app/models/__init__.py` - Imports all models
- `MODULARIZATION.md` - Detailed migration guide

## Common Imports

Instead of having everything in one file, import as needed:

```python
# Configuration
from config import Config

# Database
from extensions import db, limiter

# Models
from app.models.user import User
from app.models.club import Club

# Utilities
from app.utils.sanitization import sanitize_string
from app.utils.security import get_real_ip
from app.utils.auth_helpers import get_current_user

# Decorators
from app.decorators.auth import login_required

# Services
from app.services.airtable import AirtableService
```

## Testing

To test the modular structure:

```bash
# Ensure all models are importable
python -c "from app.models import User, Club; print('OK')"

# Ensure utilities work
python -c "from app.utils.sanitization import sanitize_string; print(sanitize_string('<script>test</script>'))"

# Run the app
python main.py
```

## Development Workflow

### Adding a New Feature

1. **Model** - Add to `app/models/your_domain.py`
2. **Utility** - Add helpers to `app/utils/your_helpers.py`
3. **Route** - Add to `main.py` (or blueprint when ready)
4. **Template** - Add to `templates/`

### Modifying Existing Feature

1. Find the relevant module
2. Make changes
3. Ensure imports still work
4. Test functionality

## Troubleshooting

### Import Error

```
ImportError: cannot import name 'User' from 'app.models'
```

**Fix:** Check `app/models/__init__.py` includes the import

### Circular Import

```
ImportError: circular import
```

**Fix:** Use `from flask import current_app` instead of global `app`

### Database Not Initialized

```
RuntimeError: working outside of application context
```

**Fix:** Ensure `db.init_app(app)` is called

## Next Steps

1. ✅ Review the modular structure
2. ✅ Read `MODULARIZATION.md` for details
3. 🔄 Test `main_refactored.py` locally
4. 🔄 Plan route migration to blueprints
5. ⏳ Gradually migrate routes
6. ⏳ Adopt full application factory pattern

## Questions?

- Check `MODULARIZATION.md` for detailed guide
- Review Flask blueprints documentation
- Look at similar modules in `app/` for examples
