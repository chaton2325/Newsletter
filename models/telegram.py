from __init__ import db
from datetime import datetime
import uuid


class TelegramLinkCode(db.Model):
    """
    A single-use code a user can generate from Réglages > Bot Telegram and send
    as `/start <code>` from any Telegram account to link it to their mirletter account.
    Several codes can coexist for the same user, each linking one additional device/chat.
    """
    __tablename__ = 'telegram_link_codes'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    code = db.Column(db.String(32), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<TelegramLinkCode {self.code} user={self.user_id}>'


class TelegramLink(db.Model):
    """A Telegram chat linked to a mirletter account. A user can link several chats."""
    __tablename__ = 'telegram_links'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    chat_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    label = db.Column(db.String(128))
    linked_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<TelegramLink chat={self.chat_id} user={self.user_id}>'


class TelegramDraft(db.Model):
    __tablename__ = 'telegram_drafts'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    chat_id = db.Column(db.String(64), nullable=False, index=True)

    subject = db.Column(db.String(256))
    content = db.Column(db.Text)
    prompt = db.Column(db.Text)

    preview_token = db.Column(db.String(64), unique=True, nullable=False, default=lambda: uuid.uuid4().hex)

    smtp_config_id = db.Column(db.Integer, db.ForeignKey('smtp_configs.id'), nullable=True)
    group_ids = db.Column(db.String(256), default='')     # comma-separated group ids
    contact_ids = db.Column(db.String(256), default='')    # comma-separated contact ids

    status = db.Column(db.String(20), default='draft')  # draft, sent, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    smtp_config = db.relationship('SMTPConfig')

    def get_group_ids(self):
        return [int(g) for g in self.group_ids.split(',') if g]

    def get_contact_ids(self):
        return [int(c) for c in self.contact_ids.split(',') if c]

    def __repr__(self):
        return f'<TelegramDraft {self.id} chat={self.chat_id} status={self.status}>'
