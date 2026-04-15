from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models.smtp import SMTPConfig
from services.mail_service import MailService
from __init__ import db
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, IntegerField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, NumberRange

settings = Blueprint('settings', __name__)

class SMTPForm(FlaskForm):
    alias = StringField('Nom de la configuration', validators=[DataRequired()], render_kw={"placeholder": "Ex: Gmail Pro"})
    server = StringField('Serveur SMTP', validators=[DataRequired()], render_kw={"placeholder": "smtp.gmail.com"})
    port = IntegerField('Port', validators=[DataRequired(), NumberRange(min=1, max=65535)], default=587)
    email = StringField('Email expéditeur', validators=[DataRequired(), Email()])
    password = PasswordField('Mot de passe SMTP', validators=[DataRequired()])
    use_tls = BooleanField('Utiliser TLS', default=True)
    submit = SubmitField('Enregistrer la configuration')

@settings.route('/smtp/test', methods=['POST'])
@login_required
def test_smtp():
    data = request.json
    server = data.get('server')
    port = data.get('port')
    email = data.get('email')
    password = data.get('password')
    use_tls = data.get('use_tls')

    if not all([server, port, email, password]):
        return jsonify({'success': False, 'message': 'Veuillez remplir tous les champs avant de tester.'})

    success, message = MailService.test_connection(server, int(port), email, password, use_tls)
    return jsonify({'success': success, 'message': message})

@settings.route('/smtp')
@login_required
def list_smtp():
    configs = SMTPConfig.query.filter_by(user_id=current_user.id).all()
    return render_template('settings/list_smtp.html', title='Mes configurations SMTP', configs=configs)

@settings.route('/smtp/add', methods=['GET', 'POST'])
@login_required
def add_smtp():
    form = SMTPForm()
    if form.validate_on_submit():
        config = SMTPConfig(
            user_id=current_user.id,
            alias=form.alias.data,
            server=form.server.data,
            port=form.port.data,
            email=form.email.data,
            use_tls=form.use_tls.data
        )
        config.set_smtp_password(form.password.data)
        db.session.add(config)
        db.session.commit()
        flash('Nouvelle configuration SMTP ajoutée.', 'success')
        return redirect(url_for('settings.list_smtp'))
    
    return render_template('settings/smtp_form.html', title='Ajouter un SMTP', form=form)

@settings.route('/smtp/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_smtp(id):
    config = SMTPConfig.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    form = SMTPForm()
    
    if form.validate_on_submit():
        config.alias = form.alias.data
        config.server = form.server.data
        config.port = form.port.data
        config.email = form.email.data
        config.use_tls = form.use_tls.data
        if form.password.data:
            config.set_smtp_password(form.password.data)
        
        db.session.commit()
        flash('Configuration SMTP mise à jour.', 'success')
        return redirect(url_for('settings.list_smtp'))
    
    elif request.method == 'GET':
        form.alias.data = config.alias
        form.server.data = config.server
        form.port.data = config.port
        form.email.data = config.email
        form.use_tls.data = config.use_tls
        
    return render_template('settings/smtp_form.html', title='Modifier le SMTP', form=form, config=config)

@settings.route('/smtp/delete/<int:id>')
@login_required
def delete_smtp(id):
    config = SMTPConfig.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    db.session.delete(config)
    db.session.commit()
    flash('Configuration SMTP supprimée.', 'info')
    return redirect(url_for('settings.list_smtp'))
