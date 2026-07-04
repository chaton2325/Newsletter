from __init__ import db
from datetime import datetime


class ScheduledNewsletter(db.Model):
    """
    A newsletter scheduled to be sent later, optionally on a recurring basis.
    Created either from the web compose page or from the Telegram bot.
    """
    __tablename__ = 'scheduled_newsletters'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    source = db.Column(db.String(20), default='web')  # 'web' or 'telegram'

    subject = db.Column(db.String(256), nullable=False)
    content = db.Column(db.Text)  # fixed HTML, or last AI-generated version
    prompt = db.Column(db.Text)  # AI prompt, re-used at each run when ai_generate=True
    ai_generate = db.Column(db.Boolean, default=False)

    smtp_config_id = db.Column(db.Integer, db.ForeignKey('smtp_configs.id'), nullable=True)
    group_ids = db.Column(db.String(256), default='')
    contact_ids = db.Column(db.String(256), default='')

    scheduled_at = db.Column(db.DateTime, nullable=False)
    recurrence = db.Column(db.String(20))  # None (one-time), 'daily', 'weekly', 'monthly'

    status = db.Column(db.String(20), default='pending')  # pending, sent, cancelled, failed
    last_run_at = db.Column(db.DateTime)
    last_error = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    smtp_config = db.relationship('SMTPConfig')

    def get_group_ids(self):
        return [int(g) for g in self.group_ids.split(',') if g]

    def get_contact_ids(self):
        return [int(c) for c in self.contact_ids.split(',') if c]

    def __repr__(self):
        return f'<ScheduledNewsletter {self.id} "{self.subject}" at={self.scheduled_at} recurrence={self.recurrence}>'
