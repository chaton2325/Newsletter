from __init__ import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default='user') # 'superadmin' or 'user'
    
    # Relationships
    smtp_configs = db.relationship('SMTPConfig', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    contacts = db.relationship('Contact', backref='owner', lazy='dynamic', cascade='all, delete-orphan')
    groups = db.relationship('Group', backref='owner', lazy='dynamic', cascade='all, delete-orphan')
    sent_emails = db.relationship('SentEmail', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_superadmin(self):
        return self.role == 'superadmin'

    def __repr__(self):
        return f'<User {self.username}>'
