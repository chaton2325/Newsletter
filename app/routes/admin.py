from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.models.user import User
from app import db
from app.utils.decorators import admin_required
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, SubmitField
from wtforms.validators import DataRequired, EqualTo, ValidationError

admin = Blueprint('admin', __name__)

class UserForm(FlaskForm):
    username = StringField('Nom d\'utilisateur', validators=[DataRequired()])
    password = PasswordField('Mot de passe', validators=[DataRequired()])
    confirm_password = PasswordField('Confirmer le mot de passe', validators=[DataRequired(), EqualTo('password')])
    role = SelectField('Rôle', choices=[('user', 'Utilisateur'), ('superadmin', 'Superadmin')], default='user')
    submit = SubmitField('Enregistrer')

class EditUserForm(FlaskForm):
    username = StringField('Nom d\'utilisateur', validators=[DataRequired()])
    role = SelectField('Rôle', choices=[('user', 'Utilisateur'), ('superadmin', 'Superadmin')])
    password = PasswordField('Nouveau mot de passe (laisser vide pour ne pas changer)')
    submit = SubmitField('Mettre à jour')

@admin.route('/users')
@login_required
@admin_required
def list_users():
    users = User.query.all()
    return render_template('admin/list_users.html', title='Gestion des utilisateurs', users=users)

@admin.route('/user/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_user():
    form = UserForm()
    if form.validate_on_submit():
        existing_user = User.query.filter_by(username=form.username.data).first()
        if existing_user:
            flash('Ce nom d\'utilisateur existe déjà.', 'danger')
            return render_template('admin/user_form.html', form=form, title='Créer un utilisateur')
        
        user = User(username=form.username.data, role=form.role.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Utilisateur créé avec succès.', 'success')
        return redirect(url_for('admin.list_users'))
    
    return render_template('admin/user_form.html', form=form, title='Créer un utilisateur')

@admin.route('/user/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(id):
    user = User.query.get_or_404(id)
    form = EditUserForm()
    
    if form.validate_on_submit():
        user.username = form.username.data
        user.role = form.role.data
        if form.password.data:
            user.set_password(form.password.data)
        db.session.commit()
        flash('Utilisateur mis à jour avec succès.', 'success')
        return redirect(url_for('admin.list_users'))
    
    elif request.method == 'GET':
        form.username.data = user.username
        form.role.data = user.role
        
    return render_template('admin/user_form.html', form=form, title='Modifier l\'utilisateur', user=user)

@admin.route('/user/delete/<int:id>')
@login_required
@admin_required
def delete_user(id):
    if id == current_user.id:
        flash('Vous ne pouvez pas supprimer votre propre compte.', 'danger')
        return redirect(url_for('admin.list_users'))
        
    user = User.query.get_or_404(id)
    db.session.delete(user)
    db.session.commit()
    flash('Utilisateur supprimé.', 'info')
    return redirect(url_for('admin.list_users'))
