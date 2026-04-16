from __init__ import db
from datetime import datetime

class Contact(db.Model):
    __tablename__ = 'contacts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    first_name = db.Column(db.String(64), nullable=False)
    last_name = db.Column(db.String(64), nullable=False)
    email = db.Column(db.String(120), nullable=False, index=True)
    phone = db.Column(db.String(20))
    tags = db.Column(db.String(128)) 
    
    # Relationships
    subscriptions = db.relationship('Subscription', back_populates='contact', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Contact {self.email}>'

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

class Group(db.Model):
    __tablename__ = 'groups'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    is_paid = db.Column(db.Boolean, default=False)
    price = db.Column(db.Float, default=0.0)
    currency = db.Column(db.String(3), default='eur')
    stripe_price_id = db.Column(db.String(128))
    description = db.Column(db.Text)
    
    welcome_email_subject = db.Column(db.String(128))
    welcome_email_body = db.Column(db.Text)
    
    smtp_config_id = db.Column(db.Integer, db.ForeignKey('smtp_configs.id'), nullable=True)
    smtp_config = db.relationship('SMTPConfig')
    
    # Relationships
    subscriptions = db.relationship('Subscription', back_populates='group', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Group {self.name}>'

class Subscription(db.Model):
    __tablename__ = 'subscriptions'
    
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), primary_key=True)
    
    # Metadata
    subscribed_at = db.Column(db.DateTime, default=datetime.utcnow)
    stripe_subscription_id = db.Column(db.String(128)) # ID de l'abonnement Stripe pour annulation
    
    # Back-relationships
    contact = db.relationship('Contact', back_populates='subscriptions')
    group = db.relationship('Group', back_populates='subscriptions')
