from __init__ import db
from cryptography.fernet import Fernet
from flask import current_app

class SMTPConfig(db.Model):
    __tablename__ = 'smtp_configs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    alias = db.Column(db.String(64), nullable=False) # Nom pour l'utilisateur
    server = db.Column(db.String(128), nullable=False)
    port = db.Column(db.Integer, nullable=False, default=587)
    email = db.Column(db.String(128), nullable=False)
    encrypted_password = db.Column(db.String(256), nullable=False)
    use_tls = db.Column(db.Boolean, default=True)

    def set_smtp_password(self, password):
        f = Fernet(current_app.config['ENCRYPTION_KEY'].encode())
        self.encrypted_password = f.encrypt(password.encode()).decode()

    def get_smtp_password(self):
        f = Fernet(current_app.config['ENCRYPTION_KEY'].encode())
        return f.decrypt(self.encrypted_password.encode()).decode()

    def __repr__(self):
        return f'<SMTPConfig {self.alias} ({self.email})>'
