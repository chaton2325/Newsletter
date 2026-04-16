from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models.contact import Contact, Group, Subscription
from models.smtp import SMTPConfig
from __init__ import db
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectMultipleField, BooleanField, FloatField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Email, Optional, NumberRange

contacts = Blueprint('contacts', __name__)

class ContactForm(FlaskForm):
    first_name = StringField('Prénom', validators=[DataRequired()])
    last_name = StringField('Nom', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Téléphone', validators=[Optional()])
    groups = SelectMultipleField('Groupes', coerce=int)
    submit = SubmitField('Enregistrer')

class GroupForm(FlaskForm):
    name = StringField('Nom du groupe', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[Optional()])
    welcome_email_subject = StringField('Sujet de l\'email de bienvenue', validators=[Optional()])
    welcome_email_body = TextAreaField('Contenu de l\'email (HTML autorisé)', validators=[Optional()])
    is_paid = BooleanField('Newsletter Payante')
    price = FloatField('Prix mensuel', validators=[Optional(), NumberRange(min=0)])
    currency = SelectField('Devise', choices=[('eur', 'EUR'), ('usd', 'USD')], default='eur')
    smtp_config_id = SelectField('Email SMTP de notification', coerce=int, validators=[Optional()])
    submit = SubmitField('Enregistrer le groupe')

@contacts.route('/')
@login_required
def list_contacts():
    user_contacts = Contact.query.filter_by(user_id=current_user.id).all()
    user_groups = Group.query.filter_by(user_id=current_user.id).all()
    return render_template('contacts/list_contacts.html', title='Mes Contacts', contacts=user_contacts, groups=user_groups)

@contacts.route('/add', methods=['GET', 'POST'])
@login_required
def add_contact():
    form = ContactForm()
    user_groups = Group.query.filter_by(user_id=current_user.id).all()
    form.groups.choices = [(g.id, g.name) for g in user_groups]
    
    if form.validate_on_submit():
        contact = Contact(
            user_id=current_user.id,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            email=form.email.data,
            phone=form.phone.data
        )
        db.session.add(contact)
        db.session.flush() # Get ID
        
        if form.groups.data:
            for gid in form.groups.data:
                sub = Subscription(contact_id=contact.id, group_id=gid)
                db.session.add(sub)
        
        db.session.commit()
        flash('Contact ajouté avec succès.', 'success')
        return redirect(url_for('contacts.list_contacts'))
    
    return render_template('contacts/contact_form.html', form=form, title='Ajouter un contact')

@contacts.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_contact(id):
    contact = Contact.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    form = ContactForm()
    user_groups = Group.query.filter_by(user_id=current_user.id).all()
    form.groups.choices = [(g.id, g.name) for g in user_groups]
    
    if form.validate_on_submit():
        contact.first_name = form.first_name.data
        contact.last_name = form.last_name.data
        contact.email = form.email.data
        contact.phone = form.phone.data
        
        # Update subscriptions
        Subscription.query.filter_by(contact_id=contact.id).delete()
        if form.groups.data:
            for gid in form.groups.data:
                sub = Subscription(contact_id=contact.id, group_id=gid)
                db.session.add(sub)
                
        db.session.commit()
        flash('Contact mis à jour.', 'success')
        return redirect(url_for('contacts.list_contacts'))
    
    elif request.method == 'GET':
        form.first_name.data = contact.first_name
        form.last_name.data = contact.last_name
        form.email.data = contact.email
        form.phone.data = contact.phone
        form.groups.data = [s.group_id for s in contact.subscriptions]
        
    return render_template('contacts/contact_form.html', form=form, title='Modifier le contact', contact=contact)

@contacts.route('/delete/<int:id>')
@login_required
def delete_contact(id):
    contact = Contact.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    db.session.delete(contact)
    db.session.commit()
    flash('Contact supprimé.', 'info')
    return redirect(url_for('contacts.list_contacts'))

# --- Groups Routes ---

@contacts.route('/groups/add', methods=['POST'])
@login_required
def add_group():
    name = request.form.get('name')
    if name:
        group = Group(name=name, user_id=current_user.id, is_paid=False, price=0.0, currency='eur')
        db.session.add(group)
        db.session.commit()
        flash(f'Groupe "{name}" créé.', 'success')
    else:
        flash("Le nom du groupe est requis.", "danger")
    return redirect(url_for('contacts.list_contacts'))

@contacts.route('/groups/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_group(id):
    group = Group.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    form = GroupForm()
    user_smtps = SMTPConfig.query.filter_by(user_id=current_user.id).all()
    form.smtp_config_id.choices = [(0, 'Défaut')] + [(s.id, f"{s.alias} ({s.email})") for s in user_smtps]

    if form.validate_on_submit():
        group.name = form.name.data
        group.description = form.description.data
        group.welcome_email_subject = form.welcome_email_subject.data
        group.welcome_email_body = form.welcome_email_body.data
        group.is_paid = form.is_paid.data
        group.price = form.price.data if form.is_paid.data else 0.0
        group.currency = form.currency.data if form.is_paid.data else 'eur'
        sid = form.smtp_config_id.data
        group.smtp_config_id = sid if (sid and sid > 0) else None
        db.session.commit()
        flash(f'Groupe "{group.name}" mis à jour.', 'success')
        return redirect(url_for('contacts.list_contacts'))
    elif request.method == 'GET':
        form.name.data = group.name
        form.description.data = group.description
        form.welcome_email_subject.data = group.welcome_email_subject
        form.welcome_email_body.data = group.welcome_email_body
        form.is_paid.data = group.is_paid
        form.price.data = group.price
        form.currency.data = group.currency
        form.smtp_config_id.data = group.smtp_config_id or 0
    return render_template('contacts/group_form.html', form=form, title='Modifier le groupe', group=group)

@contacts.route('/groups/delete/<int:id>')
@login_required
def delete_group(id):
    group = Group.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    db.session.delete(group)
    db.session.commit()
    flash('Groupe supprimé.', 'info')
    return redirect(url_for('contacts.list_contacts'))
