from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from models.contact import Contact, Group, Subscription
from models.smtp import SMTPConfig
from models.history import SentEmail
from services.mail_service import MailService
from routes.subscription import generate_unsubscribe_link
from __init__ import db
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
    group_recipients = SelectMultipleField('Destinataires (Groupes)', coerce=int)
    recipients = SelectMultipleField('Destinataires (Contacts)', coerce=int)
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
    form.group_recipients.choices = [(g.id, g.name) for g in user_groups]
    form.recipients.choices = [(c.id, f"{c.full_name} ({c.email})") for c in user_contacts]
    
    if form.validate_on_submit():
        smtp_config = SMTPConfig.query.get(form.smtp_id.data)
        if not smtp_config or smtp_config.user_id != current_user.id:
            flash('Configuration SMTP invalide.', 'danger')
            return redirect(url_for('newsletter.compose'))
        
        to_send = {}
        
        # 1. From groups
        selected_groups = [Group.query.get(gid) for gid in form.group_recipients.data]
        for group in selected_groups:
            for sub in group.subscriptions:
                to_send[sub.contact.email] = (sub.contact.id, group.id)
        
        # 2. From individuals
        for cid in form.recipients.data:
            contact = Contact.query.get(cid)
            if contact:
                to_send[contact.email] = (contact.id, 0)
        
        if not to_send:
            flash('Veuillez sélectionner au moins un destinataire.', 'danger')
            return render_template('newsletter/compose.html', form=form)

        # Handle attachments
        attachment_paths = []
        files = request.files.getlist('attachments')
        for file in files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                attachment_paths.append(file_path)

        total_sent = 0
        for email, (contact_id, group_id) in to_send.items():
            unsub_url = generate_unsubscribe_link(contact_id, group_id)
            
            group_name = "our mailing list"
            if group_id > 0:
                g = Group.query.get(group_id)
                if g: group_name = g.name

            # English footer
            footer = f'<br><hr><p style="font-size: 12px; color: #999;">You are receiving this email because you are subscribed to {group_name}. <a href="{unsub_url}">Unsubscribe</a></p>'
            personalized_content = form.content.data + footer
            
            success, results = MailService.send_email(
                current_user,
                smtp_config,
                form.subject.data,
                personalized_content,
                [email],
                attachment_paths
            )
            if success: total_sent += 1

        flash(f'Newsletter envoyée à {total_sent} abonnés.', 'success')
        return redirect(url_for('newsletter.history'))
            
    return render_template('newsletter/compose.html', form=form, title='Composer une newsletter')

@newsletter.route('/history')
@login_required
def history():
    history = SentEmail.query.filter_by(user_id=current_user.id).order_by(SentEmail.timestamp.desc()).all()
    return render_template('newsletter/history.html', title='Historique des envois', history=history)

@newsletter.route('/upload_image', methods=['POST'])
@login_required
def upload_image():
    file = request.files.get('upload')
    if file:
        filename = secure_filename(file.filename)
        import time
        filename = f"{int(time.time())}_{filename}"
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        url = url_for('static', filename=f'uploads/{filename}', _external=True)
        return jsonify({'url': url})
    return jsonify({'error': {'message': 'Erreur lors de l\'envoi du fichier.'}}), 400
