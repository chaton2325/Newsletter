from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models.contact import Contact
from app.models.history import SentEmail

main = Blueprint('main', __name__)

@main.route('/')
@main.route('/dashboard')
@login_required
def dashboard():
    contact_count = Contact.query.filter_by(user_id=current_user.id).count()
    sent_count = SentEmail.query.filter_by(user_id=current_user.id, status='success').count()
    failed_count = SentEmail.query.filter_by(user_id=current_user.id, status='failed').count()
    
    recent_history = SentEmail.query.filter_by(user_id=current_user.id)\
        .order_by(SentEmail.timestamp.desc()).limit(5).all()
        
    return render_template('dashboard.html', 
                           title='Dashboard',
                           contact_count=contact_count,
                           sent_count=sent_count,
                           failed_count=failed_count,
                           recent_history=recent_history)
