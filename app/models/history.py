from app import db
from datetime import datetime

class SentEmail(db.Model):
    __tablename__ = 'sent_emails'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject = db.Column(db.String(256), nullable=False)
    recipient = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(20), nullable=False) # 'success', 'failed'
    error_message = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)

    def __repr__(self):
        return f'<SentEmail to {self.recipient} status {self.status}>'
