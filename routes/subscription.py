import stripe
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from models.contact import Contact, Group
from models.user import User
from models.smtp import SMTPConfig
from services.mail_service import MailService
from __init__ import db, csrf
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectMultipleField, HiddenField, widgets
from wtforms.validators import DataRequired, Email, Optional

subscription = Blueprint('subscription', __name__)

# Traducteur simple
TRANSLATIONS = {
    'en': {
        'title': 'Join our Newsletter',
        'first_name': 'First Name',
        'last_name': 'Last Name',
        'email': 'Email Address',
        'choose': 'Choose your subscriptions:',
        'subscribe': 'Subscribe Now',
        'success': 'Subscription successful!',
        'success_msg': 'Thank you for your trust.',
        'per_month': '/month'
    },
    'fr': {
        'title': 'Rejoignez notre Newsletter',
        'first_name': 'Prénom',
        'last_name': 'Nom',
        'email': 'Adresse Email',
        'choose': 'Choisissez vos abonnements :',
        'subscribe': 'S\'abonner maintenant',
        'success': 'Inscription réussie !',
        'success_msg': 'Merci de votre confiance.',
        'per_month': '/mois'
    }
}

class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()

class PublicSubscribeForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    groups = MultiCheckboxField('Groups', coerce=int)
    submit = SubmitField('Subscribe')

@subscription.route('/iframe/<int:user_id>', methods=['GET', 'POST'])
def iframe_subscribe(user_id):
    user = User.query.get_or_404(user_id)
    group_id = request.args.get('group_id', type=int)
    lang = request.args.get('lang', 'en') # 'en' par défaut
    if lang not in TRANSLATIONS: lang = 'en'
    
    t = TRANSLATIONS[lang]
    form = PublicSubscribeForm()
    
    # Mise à jour des labels selon la langue
    form.first_name.label.text = t['first_name']
    form.last_name.label.text = t['last_name']
    form.email.label.text = t['email']
    form.submit.label.text = t['subscribe']

    if group_id:
        user_groups = Group.query.filter_by(user_id=user_id, id=group_id).all()
    else:
        user_groups = Group.query.filter_by(user_id=user_id).all()
    
    form.groups.choices = [(g.id, f"{g.name} ({g.price} {g.currency.upper()}{t['per_month']})" if g.is_paid else g.name) for g in user_groups]
    
    if group_id and request.method == 'GET':
        form.groups.data = [group_id]

    if form.validate_on_submit():
        email = form.email.data
        contact = Contact.query.filter_by(email=email, user_id=user_id).first()
        if not contact:
            contact = Contact(user_id=user_id, first_name=form.first_name.data, last_name=form.last_name.data, email=email)
            db.session.add(contact)
            db.session.flush()
        
        selected_group_ids = list(set(form.groups.data))
        selected_groups = [Group.query.get(gid) for gid in selected_group_ids]
        paid_groups = [g for g in selected_groups if g.is_paid]
        free_groups = [g for g in selected_groups if not g.is_paid]
        
        for g in free_groups:
            if g not in contact.groups:
                contact.groups.append(g)
                smtp_to_use = g.smtp_config or user.smtp_configs.first()
                if smtp_to_use:
                    # Envoi de l'email personnalisé
                    subject = g.welcome_email_subject or f"Welcome to {g.name}"
                    body = g.welcome_email_body or f"<h2>Thank you!</h2><p>You are subscribed to {g.name}.</p>"
                    MailService.send_email(user, smtp_to_use, subject, body, [email])

        db.session.commit()

        if paid_groups:
            stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
            line_items = []
            for g in paid_groups:
                if not g.stripe_price_id:
                    product = stripe.Product.create(name=f"Newsletter: {g.name}", description=g.description)
                    price = stripe.Price.create(unit_amount=int(g.price * 100), currency=g.currency, recurring={"interval": "month"}, product=product.id)
                    g.stripe_price_id = price.id
                    db.session.commit()
                line_items.append({'price': g.stripe_price_id, 'quantity': 1})
            
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'], line_items=line_items, mode='subscription',
                success_url=url_for('subscription.success', _external=True, lang=lang) + '&session_id={CHECKOUT_SESSION_ID}',
                cancel_url=url_for('subscription.iframe_subscribe', user_id=user_id, group_id=group_id, lang=lang, _external=True),
                customer_email=email,
                metadata={'contact_id': contact.id, 'group_ids': ','.join([str(g.id) for g in paid_groups])}
            )
            return render_template('subscription/iframe_redirect.html', url=url_for('subscription.pay', session_id=checkout_session.id, lang=lang))
        
        return render_template('subscription/iframe.html', form=form, user=user, success=True, t=t)
        
    return render_template('subscription/iframe.html', form=form, user=user, t=t, lang=lang)

@subscription.route('/pay/<session_id>')
def pay(session_id):
    lang = request.args.get('lang', 'en')
    t = TRANSLATIONS.get(lang, TRANSLATIONS['en'])
    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        group_ids = session.metadata.get('group_ids', '').split(',')
        groups = [Group.query.get(int(gid)) for gid in group_ids if gid]
        return render_template('subscription/pay.html', session=session, groups=groups, t=t)
    except Exception as e:
        return redirect(url_for('main.index'))

@subscription.route('/success')
def success():
    lang = request.args.get('lang', 'en')
    t = TRANSLATIONS.get(lang, TRANSLATIONS['en'])
    session_id = request.args.get('session_id')
    if not session_id:
        return render_template('subscription/success_page.html', t=t)

    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status == 'paid':
            contact_id = session.metadata.get('contact_id')
            group_ids = session.metadata.get('group_ids', '').split(',')
            contact = Contact.query.get(contact_id)
            if contact:
                user = User.query.get(contact.user_id)
                paid_groups_added = []
                for gid in group_ids:
                    if gid:
                        group = Group.query.get(int(gid))
                        if group and group not in contact.groups:
                            contact.groups.append(group)
                            paid_groups_added.append(group)
                            smtp_to_use = group.smtp_config or user.smtp_configs.first()
                            if smtp_to_use:
                                subject = group.welcome_email_subject or f"Payment confirmed - {group.name}"
                                body = group.welcome_email_body or f"<p>Abonnement actif pour {group.name}</p>"
                                MailService.send_email(user, smtp_to_use, subject, body, [contact.email])
                db.session.commit()
                return render_template('subscription/success_page.html', paid=True, groups=paid_groups_added, t=t)
    except Exception as e:
        print(f"Erreur Stripe: {e}")
    return render_template('subscription/success_page.html', t=t)
