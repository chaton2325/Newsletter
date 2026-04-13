from app import db

# Association Table for Many-to-Many relationship between Contacts and Groups
contacts_groups = db.Table('contacts_groups',
    db.Column('contact_id', db.Integer, db.ForeignKey('contacts.id'), primary_key=True),
    db.Column('group_id', db.Integer, db.ForeignKey('groups.id'), primary_key=True)
)

class Contact(db.Model):
    __tablename__ = 'contacts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    first_name = db.Column(db.String(64), nullable=False)
    last_name = db.Column(db.String(64), nullable=False)
    email = db.Column(db.String(120), nullable=False, index=True)
    phone = db.Column(db.String(20))
    tags = db.Column(db.String(128)) 
    
    # Relationship to groups
    # 'groups' is handled by backref in Group model

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
    
    contacts = db.relationship('Contact', secondary=contacts_groups, backref=db.backref('groups', lazy='dynamic'))

    def __repr__(self):
        return f'<Group {self.name}>'
