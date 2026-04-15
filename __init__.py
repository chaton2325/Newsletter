from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_bootstrap import Bootstrap5
from config import Config
import os

# Initialize Flask extensions
db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'
csrf = CSRFProtect()
bootstrap = Bootstrap5()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    bootstrap.init_app(app)

    # Register Blueprints
    from routes.auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint)

    from routes.main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from routes.admin import admin as admin_blueprint
    app.register_blueprint(admin_blueprint, url_prefix='/admin')

    from routes.contacts import contacts as contacts_blueprint
    app.register_blueprint(contacts_blueprint, url_prefix='/contacts')

    from routes.newsletter import newsletter as newsletter_blueprint
    app.register_blueprint(newsletter_blueprint, url_prefix='/newsletter')

    from routes.settings import settings as settings_blueprint
    app.register_blueprint(settings_blueprint, url_prefix='/settings')

    # Ensure upload directory exists
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    return app
