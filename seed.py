from app import create_app, db
from app.models.user import User
import os

def seed():
    app = create_app()
    with app.app_context():
        # Create tables
        db.create_all()
        
        # Check if superadmin exists
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            print("Création du compte superadmin par défaut...")
            admin = User(username='admin', role='superadmin')
            admin.set_password('admin123')
            db.session.add(admin)
            
            # Create a regular user for testing
            user = User(username='user', role='user')
            user.set_password('user123')
            db.session.add(user)
            
            db.session.commit()
            print("Base de données initialisée avec succès !")
            print("Compte Superadmin : admin / admin123")
            print("Compte Utilisateur : user / user123")
        else:
            print("La base de données est déjà initialisée.")

if __name__ == '__main__':
    seed()
