from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from app.models.contact import Contact, Group
from app.models.smtp import SMTPConfig
from app.models.history import SentEmail
from app.services.mail_service import MailService
from app import db
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectMultipleField, SubmitField, FileField, SelectField
from wtforms.validators import DataRequired
from werkzeug.utils import secure_filename
import os

newsletter = Blueprint('newsletter', __name__)

class NewsletterForm(FlaskForm):
    subject = StringField('Objet de l\'email', validators=[DataRequired()])
    content = TextAreaField('Contenu (Rich Text)', validators=[DataRequired()])
    smtp_id = SelectField('Envoyer via', coerce=int, validators=[DataRequired()])
    recipients = SelectMultipleField('Destinataires (Contacts)', coerce=int)
    group_recipients = SelectMultipleField('Destinataires (Groupes)', coerce=int)
    attachments = FileField('Pièces jointes')
    submit = SubmitField('Envoyer la newsletter')

@newsletter.route('/compose', methods=['GET', 'POST'])
@login_required
def compose():
    user_contacts = Contact.query.filter_by(user_id=current_user.id).all()
    user_groups = Group.query.filter_by(user_id=current_user.id).all()
    user_smtps = SMTPConfig.query.filter_by(user_id=current_user.id).all()
    
    form = NewsletterForm()
    form.smtp_id.choices = [(s.id, s.alias) for s in user_smtps]
    form.recipients.choices = [(c.id, f"{c.full_name} ({c.email})") for c in user_contacts]
    form.group_recipients.choices = [(g.id, g.name) for g in user_groups]
    
    if form.validate_on_submit():
        # Check SMTP config
        smtp_config = SMTPConfig.query.get(form.smtp_id.data)
        if not smtp_config or smtp_config.user_id != current_user.id:
            flash('Configuration SMTP invalide.', 'danger')
            return redirect(url_for('newsletter.compose'))
        
        # Collect recipients from selection
        final_recipients = set()
        
        # From individuals
        for cid in form.recipients.data:
            c = Contact.query.get(cid)
            if c: final_recipients.add(c.email)
            
        # From groups
        for gid in form.group_recipients.data:
            g = Group.query.get(gid)
            if g:
                for c in g.contacts:
                    final_recipients.add(c.email)
        
        if not final_recipients:
            flash('Veuillez sélectionner au moins un destinataire.', 'danger')
            return render_template('newsletter/compose.html', form=form, title='Composer une newsletter')
            
        # Handle attachments
        attachment_paths = []
        files = request.files.getlist('attachments')
        for file in files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                attachment_paths.append(file_path)
        
        # Send
        success, results = MailService.send_email(
            current_user,
            smtp_config,
            form.subject.data,
            form.content.data,
            list(final_recipients),
            attachment_paths
        )
        
        if success:
            flash(f'Newsletter envoyée à {len(final_recipients)} contacts.', 'success')
            return redirect(url_for('newsletter.history'))
        else:
            flash(f'Erreur lors de l\'envoi : {results}', 'danger')
            
    return render_template('newsletter/compose.html', form=form, title='Composer une newsletter')

@newsletter.route('/history')
@login_required
def history():
    history = SentEmail.query.filter_by(user_id=current_user.id).order_by(SentEmail.timestamp.desc()).all()
    return render_template('newsletter/history.html', title='Historique des envois', history=history)

@newsletter.route('/upload_image', methods=['POST'])
@login_required
def upload_image():
    """Gère l'upload d'images depuis CKEditor"""
    file = request.files.get('upload')
    if file:
        filename = secure_filename(file.filename)
        # Ajout d'un timestamp pour éviter les doublons de noms
        import time
        filename = f"{int(time.time())}_{filename}"
        
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Retourne l'URL au format attendu par CKEditor
        url = url_for('static', filename=f'uploads/{filename}', _external=True)
        return jsonify({
            'url': url
        })
    return jsonify({'error': {'message': 'Erreur lors de l\'envoi du fichier.'}}), 400
