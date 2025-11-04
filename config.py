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
        db_url = get_database_url()
        secret_key = hashlib.sha256(f"hackclub-dashboard-{db_url}".encode()).hexdigest()
    return secret_key


class Config:
    """Base configuration"""
    SECRET_KEY = get_secret_key()
    SQLALCHEMY_DATABASE_URI = get_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

    # Google Fonts API Key
    GOOGLE_FONTS_API_KEY = os.getenv('GOOGLE_FONTS_API_KEY', '')

    # Unsplash API Key (for image search)
    UNSPLASH_API_KEY = os.getenv('UNSPLASH_API_KEY', '')
