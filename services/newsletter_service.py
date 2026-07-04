from models.contact import Contact, Group
from services.mail_service import MailService
from routes.subscription import generate_unsubscribe_link


def send_newsletter(user, smtp_config, subject, content, group_ids=None, contact_ids=None, attachments=None):
    """
    Sends a newsletter to the union of the given groups' subscribers and individual
    contacts, appending a personalized unsubscribe footer to each email.

    Shared by the web compose page, the Telegram bot, and the scheduled-send worker
    so the three call sites stay in sync.

    Returns (total_sent, total_targeted).
    """
    group_ids = group_ids or []
    contact_ids = contact_ids or []

    to_send = {}
    for gid in group_ids:
        group = Group.query.get(gid)
        if group and group.user_id == user.id:
            for sub in group.subscriptions:
                to_send[sub.contact.email] = (sub.contact.id, group.id)

    for cid in contact_ids:
        contact = Contact.query.get(cid)
        if contact and contact.user_id == user.id:
            to_send[contact.email] = (contact.id, 0)

    if not to_send or not smtp_config:
        return 0, len(to_send)

    total_sent = 0
    for email, (contact_id, group_id) in to_send.items():
        unsub_url = generate_unsubscribe_link(contact_id, group_id)

        group_name = "our mailing list"
        if group_id > 0:
            g = Group.query.get(group_id)
            if g:
                group_name = g.name

        footer = (
            f'<br><hr><p style="font-size: 12px; color: #999;">'
            f'You are receiving this email because you are subscribed to {group_name}. '
            f'<a href="{unsub_url}">Unsubscribe</a></p>'
        )
        personalized_content = (content or "") + footer

        success, _ = MailService.send_email(user, smtp_config, subject, personalized_content, [email], attachments)
        if success:
            total_sent += 1

    return total_sent, len(to_send)
