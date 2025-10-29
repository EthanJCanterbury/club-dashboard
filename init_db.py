#!/usr/bin/env python3
"""
Database initialization script for Hack Club Dashboard
"""

import os
import sys
from datetime import datetime, timezone

# Add the current directory to the Python path if running from Docker
if os.path.exists('/app'):
    sys.path.insert(0, '/app')

from app import create_app
from extensions import db
from app.models.user import User
from werkzeug.security import generate_password_hash

def init_database():
    """Initialize the database with tables and test data"""
    print("🔧 Initializing database...")
    
    app = create_app()
    with app.app_context():
        try:
            # Create all tables
            db.create_all()
            print("✅ Database tables created successfully")
            
            # Check if admin user exists
            admin_user = User.query.filter_by(email='admin@hackclub.local').first()
            if not admin_user:
                # Import RBAC models
                from app.models.user import Role, initialize_rbac_system
                
                # Initialize RBAC system first
                initialize_rbac_system()
                
                # Create admin user
                admin_user = User(
                    username='admin',
                    email='admin@hackclub.local',
                    first_name='Admin',
                    last_name='User',
                    created_at=datetime.now(timezone.utc),
                    registration_ip='127.0.0.1'
                )
                admin_user.set_password('AdminPass123!')
                admin_user.add_ip('127.0.0.1')
                db.session.add(admin_user)
                db.session.flush()  # Get the user ID
                
                # Assign admin role
                admin_role = Role.query.filter_by(name='admin').first()
                if admin_role:
                    admin_user.assign_role(admin_role)
                
                # Create test user
                test_user = User(
                    username='testuser',
                    email='test@hackclub.local',
                    first_name='Test',
                    last_name='User',
                    created_at=datetime.now(timezone.utc),
                    registration_ip='127.0.0.1'
                )
                test_user.set_password('TestPass123!')
                test_user.add_ip('127.0.0.1')
                db.session.add(test_user)
                
                db.session.commit()
                print("✅ Test users created:")
                print("   Admin: admin@hackclub.local / AdminPass123!")
                print("   User:  test@hackclub.local / TestPass123!")
            else:
                print("ℹ️  Database already initialized")
                
        except Exception as e:
            print(f"❌ Error initializing database: {str(e)}")
            sys.exit(1)

if __name__ == '__main__':
    init_database()
