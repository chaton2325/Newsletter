import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'mirletter-secret-key-12345'
    
    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///mirletter.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session and CSRF configuration.
    # SameSite=None + Secure cookies are required for the public /subscription/iframe/*
    # pages to work when embedded cross-site, but Secure cookies are silently dropped
    # by browsers over plain HTTP — which breaks the *entire* session (including the
    # CSRF secret) and causes "The CSRF session token is missing" on every login.
    # Default to dev-safe values; set these two env vars once the site is served over
    # HTTPS in production so the iframe embedding keeps working there.
    SESSION_COOKIE_SAMESITE = os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax')
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    WTF_CSRF_ENABLED = True
    
    # Security: Key for encrypting SMTP passwords
    # Use a 32-byte base64 encoded string for Fernet encryption
    ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY') or '36lFeN6BodRNJLR-n3ZPQwzU1Zw4c55pPPzpGk5iaOw='
    
    # Mail configuration (for system notifications if needed)
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') is not None
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    
    # Uploads
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'app/static/uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

    # Stripe configuration
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_PUBLIC_KEY = os.environ.get('STRIPE_PUBLIC_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')

    # Telegram bot configuration
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    TELEGRAM_BOT_USERNAME = os.environ.get('TELEGRAM_BOT_USERNAME')

    # Mistral AI configuration (HTML content generation)
    MISTRAL_API_KEY = os.environ.get('MISTRAL_API_KEY')
    MISTRAL_MODEL = os.environ.get('MISTRAL_MODEL') or 'mistral-large-latest'

    # Public base URL used by the Telegram bot to build preview links
    SITE_BASE_URL = os.environ.get('SITE_BASE_URL') or 'http://127.0.0.1:9060'
