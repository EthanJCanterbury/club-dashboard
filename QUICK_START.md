# Quick Start Guide

## Run the Application

```bash
python main.py
```

That's it! The application will start on http://localhost:5000

## Structure Overview

```
app/
├── routes/          # 10 blueprints with all routes
├── models/          # 13 database models
├── utils/           # Helper functions
├── decorators/      # Auth & permissions
└── services/        # External API integrations
```

## Important Files

- `main.py` - Application entry point (start here)
- `config.py` - Configuration settings
- `extensions.py` - Flask extensions (db, limiter, etc.)
- `requirements.txt` - Python dependencies

## Configuration

Set these environment variables in `.env`:

```env
DATABASE_URL=postgresql://...
SECRET_KEY=your-secret-key
SLACK_CLIENT_ID=...
SLACK_CLIENT_SECRET=...
```

## Adding a New Feature

1. **New Route**: Add to existing blueprint in `app/routes/`
2. **New Model**: Create in `app/models/`
3. **New Utility**: Add to `app/utils/`
4. **New Blueprint**: Create file, register in `app/__init__.py`

## Need Help?

- Check `README.md` for full documentation
- Check `MIGRATION_COMPLETE.md` for architecture details
- All old files backed up in `.archive/`

---

**Ready to build!** 🚀
