from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from models.contact import Contact, Group
from models.smtp import SMTPConfig
from models.history import SentEmail
from models.telegram import TelegramDraft
from models.schedule import ScheduledNewsletter
from services.newsletter_service import send_newsletter
from services.mistral_service import MistralService
from __init__ import db
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectMultipleField, SubmitField, FileField, SelectField
from wtforms.validators import DataRequired
from werkzeug.utils import secure_filename
import os

newsletter = Blueprint('newsletter', __name__)

RECURRENCE_LABELS = {
    None: 'Une fois',
    '': 'Une fois',
    'daily': 'Tous les jours',
    'weekly': 'Toutes les semaines',
    'monthly': 'Tous les mois',
}


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

        group_ids = list(form.group_recipients.data)
        contact_ids = list(form.recipients.data)

        if not group_ids and not contact_ids:
            flash('Veuillez sélectionner au moins un destinataire.', 'danger')
            return render_template('newsletter/compose.html', form=form)

        send_mode = request.form.get('send_mode', 'now')

        if send_mode == 'schedule':
            scheduled_at_raw = request.form.get('scheduled_at')
            recurrence = request.form.get('recurrence') or None
            if recurrence not in (None, 'daily', 'weekly', 'monthly'):
                recurrence = None
            try:
                scheduled_at = datetime.fromisoformat(scheduled_at_raw)
            except (TypeError, ValueError):
                flash("Date/heure de programmation invalide.", 'danger')
                return render_template('newsletter/compose.html', form=form)

            scheduled = ScheduledNewsletter(
                user_id=current_user.id,
                source='web',
                subject=form.subject.data,
                content=form.content.data,
                ai_generate=False,
                smtp_config_id=smtp_config.id,
                group_ids=','.join(str(i) for i in group_ids),
                contact_ids=','.join(str(i) for i in contact_ids),
                scheduled_at=scheduled_at,
                recurrence=recurrence,
            )
            db.session.add(scheduled)
            db.session.commit()
            flash(f"Newsletter programmée pour le {scheduled_at.strftime('%d/%m/%Y %H:%M')}.", 'success')
            return redirect(url_for('newsletter.scheduled'))

        # Handle attachments (immediate send only)
        attachment_paths = []
        files = request.files.getlist('attachments')
        for file in files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                attachment_paths.append(file_path)

        total_sent, total_targeted = send_newsletter(
            current_user, smtp_config, form.subject.data, form.content.data,
            group_ids=group_ids, contact_ids=contact_ids, attachments=attachment_paths
        )

        if total_targeted == 0:
            flash('Aucun destinataire trouvé pour cette sélection.', 'warning')
        else:
            flash(f'Newsletter envoyée à {total_sent} abonnés.', 'success')
        return redirect(url_for('newsletter.history'))

    return render_template('newsletter/compose.html', form=form, title='Composer une newsletter')


@newsletter.route('/generate_ai', methods=['POST'])
@login_required
def generate_ai():
    data = request.get_json(silent=True) or {}
    prompt = (data.get('prompt') or '').strip()
    if not prompt:
        return jsonify({'error': 'Veuillez décrire le contenu à générer.'}), 400

    success, html_or_error = MistralService.generate_html(prompt)
    if not success:
        return jsonify({'error': html_or_error}), 400

    return jsonify({'html': html_or_error})


@newsletter.route('/scheduled')
@login_required
def scheduled():
    items = ScheduledNewsletter.query.filter_by(user_id=current_user.id) \
        .order_by(ScheduledNewsletter.scheduled_at.asc()).all()
    return render_template(
        'newsletter/scheduled.html',
        title='Newsletters programmées',
        items=items,
        recurrence_labels=RECURRENCE_LABELS,
    )


@newsletter.route('/scheduled/<int:id>/cancel', methods=['POST'])
@login_required
def cancel_scheduled(id):
    item = ScheduledNewsletter.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    item.status = 'cancelled'
    db.session.commit()
    flash('Envoi programmé annulé.', 'info')
    return redirect(url_for('newsletter.scheduled'))


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


@newsletter.route('/telegram_preview/<token>')
def telegram_preview(token):
    """
    Public preview page for a newsletter draft generated via the Telegram bot.
    The token is an unguessable UUID stored on the draft, so no login is required.
    """
    draft = TelegramDraft.query.filter_by(preview_token=token).first_or_404()
    return render_template(
        'newsletter/telegram_preview.html',
        title='Aperçu Telegram',
        draft=draft
    )
