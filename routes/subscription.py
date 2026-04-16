import stripe
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify, make_response
from models.contact import Contact, Group, Subscription
from models.user import User
from models.smtp import SMTPConfig
from services.mail_service import MailService
from __init__ import db, csrf
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectMultipleField, HiddenField, widgets
from wtforms.validators import DataRequired, Email, Optional
from itsdangerous import URLSafeSerializer

subscription = Blueprint('subscription', __name__)

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
        'per_month': '/month',
        'unsubscribe_success': 'You have been unsubscribed.',
        'unsubscribe_confirm': 'Are you sure you want to unsubscribe?'
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
        'per_month': '/mois',
        'unsubscribe_success': 'Vous avez été désabonné avec succès.',
        'unsubscribe_confirm': 'Voulez-vous vraiment vous désabonner ?'
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

# Route modifiée pour accepter l'ID de groupe dans le chemin
@subscription.route('/iframe/<int:user_id>', methods=['GET', 'POST'])
@subscription.route('/iframe/<int:user_id>/<int:group_id>', methods=['GET', 'POST'])
def iframe_subscribe(user_id, group_id=None):
    user = User.query.get_or_404(user_id)
    
    # On vérifie aussi le paramètre d'URL pour la rétro-compatibilité
    if not group_id:
        group_id = request.args.get('group_id', type=int)
        
    lang = request.args.get('lang', 'en')
    if lang not in TRANSLATIONS: lang = 'en'
    t = TRANSLATIONS[lang]
    form = PublicSubscribeForm()
    
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
            sub = Subscription.query.filter_by(contact_id=contact.id, group_id=g.id).first()
            if not sub:
                sub = Subscription(contact_id=contact.id, group_id=g.id)
                db.session.add(sub)
                smtp_to_use = g.smtp_config or user.smtp_configs.first()
                if smtp_to_use:
                    subject = g.welcome_email_subject or f"Welcome to {g.name}"
                    body = g.welcome_email_body or f"<h2>Thank you!</h2><p>You are subscribed to {g.name}.</p>"
                    unsub_url = generate_unsubscribe_link(contact.id, g.id)
                    body += f'<br><br><a href="{unsub_url}" style="color: #999; font-size: 12px;">Unsubscribe / Se désabonner</a>'
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
            resp = make_response(render_template('subscription/iframe_redirect.html', url=url_for('subscription.pay', session_id=checkout_session.id, lang=lang)))
            resp.headers['X-Frame-Options'] = 'ALLOWALL'
            resp.headers['Content-Security-Policy'] = "frame-ancestors *"
            return resp
        
        resp = make_response(render_template('subscription/iframe.html', form=form, user=user, success=True, t=t))
        resp.headers['X-Frame-Options'] = 'ALLOWALL'
        resp.headers['Content-Security-Policy'] = "frame-ancestors *"
        return resp
        
    resp = make_response(render_template('subscription/iframe.html', form=form, user=user, t=t, lang=lang))
    resp.headers['X-Frame-Options'] = 'ALLOWALL'
    resp.headers['Content-Security-Policy'] = "frame-ancestors *"
    return resp

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
    except Exception:
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
        session = stripe.checkout.Session.retrieve(session_id, expand=['subscription'])
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
                        sub = Subscription.query.filter_by(contact_id=contact.id, group_id=group.id).first()
                        if not sub:
                            sub = Subscription(
                                contact_id=contact.id, 
                                group_id=group.id, 
                                stripe_subscription_id=session.subscription.id if session.subscription else None
                            )
                            db.session.add(sub)
                            paid_groups_added.append(group)
                            smtp_to_use = group.smtp_config or user.smtp_configs.first()
                            if smtp_to_use:
                                subject = group.welcome_email_subject or f"Payment confirmed - {group.name}"
                                body = group.welcome_email_body or f"<p>Subscription active for {group.name}</p>"
                                unsub_url = generate_unsubscribe_link(contact.id, group.id)
                                body += f'<br><br><a href="{unsub_url}" style="color: #999; font-size: 12px;">Unsubscribe / Se désabonner</a>'
                                MailService.send_email(user, smtp_to_use, subject, body, [contact.email])
                db.session.commit()
                return render_template('subscription/success_page.html', paid=True, groups=paid_groups_added, t=t)
    except Exception as e:
        print(f"Stripe Error: {e}")
    return render_template('subscription/success_page.html', t=t)

def generate_unsubscribe_link(contact_id, group_id):
    s = URLSafeSerializer(current_app.config['SECRET_KEY'])
    token = s.dumps({'c': contact_id, 'g': group_id})
    return url_for('subscription.unsubscribe', token=token, _external=True)

@subscription.route('/unsubscribe/<token>', methods=['GET', 'POST'])
def unsubscribe(token):
    s = URLSafeSerializer(current_app.config['SECRET_KEY'])
    try:
        data = s.loads(token)
        contact_id = data['c']
        group_id = data['g']
    except Exception:
        return "Invalid Link", 400

    contact = Contact.query.get_or_404(contact_id)
    group = None
    if group_id > 0:
        group = Group.query.get(group_id)
    
    if request.method == 'POST':
        stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
        
        if group_id > 0:
            sub = Subscription.query.get((contact_id, group_id))
            if sub:
                if sub.stripe_subscription_id:
                    try:
                        stripe.Subscription.delete(sub.stripe_subscription_id)
                    except Exception as e:
                        print(f"Stripe Cancel Error: {e}")
                    db.session.delete(contact)
                else:
                    db.session.delete(sub)
        else:
            for sub in contact.subscriptions:
                if sub.stripe_subscription_id:
                    try:
                        stripe.Subscription.delete(sub.stripe_subscription_id)
                    except Exception as e:
                        print(f"Stripe Global Cancel Error: {e}")
            db.session.delete(contact)
        
        db.session.commit()
        return render_template('subscription/unsubscribe_result.html', success=True)

    return render_template('subscription/unsubscribe_result.html', group=group)
