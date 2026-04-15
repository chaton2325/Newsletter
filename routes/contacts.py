from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models.contact import Contact, Group
from __init__ import db
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectMultipleField
from wtforms.validators import DataRequired, Email, Optional

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
    submit = SubmitField('Créer le groupe')

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
        if form.groups.data:
            contact.groups = [Group.query.get(gid) for gid in form.groups.data]
        db.session.add(contact)
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
        contact.groups = [Group.query.get(gid) for gid in form.groups.data]
        db.session.commit()
        flash('Contact mis à jour.', 'success')
        return redirect(url_for('contacts.list_contacts'))
    
    elif request.method == 'GET':
        form.first_name.data = contact.first_name
        form.last_name.data = contact.last_name
        form.email.data = contact.email
        form.phone.data = contact.phone
        form.groups.data = [g.id for g in contact.groups]
        
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
    form = GroupForm()
    if form.validate_on_submit():
        group = Group(name=form.name.data, user_id=current_user.id)
        db.session.add(group)
        db.session.commit()
        flash(f'Groupe "{group.name}" créé.', 'success')
    return redirect(url_for('contacts.list_contacts'))

@contacts.route('/groups/delete/<int:id>')
@login_required
def delete_group(id):
    group = Group.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    db.session.delete(group)
    db.session.commit()
    flash('Groupe supprimé.', 'info')
    return redirect(url_for('contacts.list_contacts'))
