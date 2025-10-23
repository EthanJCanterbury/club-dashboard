"""
Application configuration.
"""
import os
import hashlib
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def get_database_url():
    """Get database URL from environment and convert old postgres:// to postgresql://"""
    url = os.getenv('DATABASE_URL')
    if url and url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    return url


def get_secret_key():
    """Get or generate secret key for Flask session management"""
    secret_key = os.getenv('SECRET_KEY')
    if not secret_key:
        # In production, this should be set via environment variable
        # For development/fallback, use a deterministic key based on database URL
        db_url = get_database_url()
        secret_key = hashlib.sha256(f"hackclub-dashboard-{db_url}".encode()).hexdigest()
    return secret_key


class Config:
    """Base configuration"""
    SECRET_KEY = get_secret_key()
    SQLALCHEMY_DATABASE_URI = get_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Add any other configuration variables here
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
