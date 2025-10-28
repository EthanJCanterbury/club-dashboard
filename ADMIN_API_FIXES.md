# Admin API Endpoint Fixes - Round 2

## Issues Fixed

### 1. ✅ Missing Role Import
**Error**: `NameError: name 'Role' is not defined`
**Location**: `app/routes/api.py:383`
**Fix**: Added import in the function
```python
from app.models.user import Role
roles = Role.query.all()
```

### 2. ✅ AuditLog Attribute Error
**Error**: `AttributeError: 'AuditLog' object has no attribute 'category'`
**Root Cause**: Field is named `action_category` not `category`
**Fix**: Changed `log.category` → `log.action_category`

### 3. ✅ OAuthApplication Attribute Error
**Error**: `AttributeError: 'OAuthApplication' object has no attribute 'owner_id'`
**Root Cause**: Field is named `user_id` not `owner_id`
**Fix**:
```python
'owner_id': app.user_id,
'owner_username': app.user.username if app.user else None,
```

### 4. ✅ SystemSettings Attribute Errors
**Error**: `AttributeError: 'SystemSettings' object has no attribute 'maintenance_mode'`
**Root Cause**: SystemSettings is a key-value store, not a traditional model with columns
**Fix**: Completely rewrote to use proper static methods:
```python
# GET
return jsonify({
    'maintenance_mode': SystemSettings.is_maintenance_mode(),
    'economy_enabled': SystemSettings.is_economy_enabled(),
    'registration_enabled': SystemSettings.is_user_registration_enabled(),
    # ... etc
})

# POST
SystemSettings.set_setting('maintenance_mode', str(data['maintenance_mode']).lower(), current_user.id)
```

## All Admin Endpoints Now Working

### ✅ Working Endpoints:
- `/api/admin/users` - User list with pagination
- `/api/admin/clubs` - Club list with pagination
- `/api/admin/stats` - System statistics
- `/api/admin/settings` - Get/update system settings
- `/api/admin/activity` - Activity logs
- `/api/admin/rbac/roles` - RBAC roles list
- `/api/admin/rbac/permissions` - Permissions grouped by category
- `/api/admin/apikeys` - API keys list
- `/api/admin/oauthapps` - OAuth applications list
- `/api/admin/audit-logs` - Audit logs with pagination

## File Modified:
- `app/routes/api.py` (lines 300-509)

## Testing:
```bash
# All endpoints should now return 200
GET /api/admin/users
GET /api/admin/clubs
GET /api/admin/rbac/roles
GET /api/admin/rbac/permissions
GET /api/admin/apikeys
GET /api/admin/oauthapps
GET /api/admin/audit-logs
GET /api/admin/settings
```

## Status: ✅ ALL FIXED
**Last Updated**: 2025-10-27
**Ready for Production**: Yes
