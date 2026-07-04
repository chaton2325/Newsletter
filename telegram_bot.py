"""
Bot Telegram MIRLETTER.

Permet, depuis Telegram, de :
- lier plusieurs comptes Telegram à un même compte MIRLETTER via un code généré dans
  Réglages > Bot Telegram
- générer du contenu HTML de newsletter via l'API Mistral
- prévisualiser le rendu (lien web) et régénérer si besoin
- choisir les groupes/contacts destinataires
- envoyer immédiatement, ou programmer l'envoi (unique ou récurrent : quotidien,
  hebdomadaire, mensuel)

Lancement : python telegram_bot.py (ou automatiquement via run.py)
Nécessite TELEGRAM_BOT_TOKEN et MISTRAL_API_KEY dans .env.
"""
import logging
from datetime import datetime

from dateutil import parser as date_parser
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from __init__ import create_app, db
from models import User, Group, Contact, SMTPConfig, TelegramDraft, TelegramLink, TelegramLinkCode
from models.schedule import ScheduledNewsletter
from services.mistral_service import MistralService
from services.newsletter_service import send_newsletter

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = create_app()

STATE_AWAITING_SUBJECT = "awaiting_subject"
STATE_AWAITING_PROMPT = "awaiting_prompt"
STATE_AWAITING_REGEN_PROMPT = "awaiting_regen_prompt"
STATE_AWAITING_SCHEDULE_DATETIME = "awaiting_schedule_datetime"

RECURRENCE_LABELS = {
    'none': 'une seule fois',
    'daily': 'tous les jours',
    'weekly': 'toutes les semaines',
    'monthly': 'tous les mois',
}


def get_linked_user(chat_id):
    link = TelegramLink.query.filter_by(chat_id=str(chat_id)).first()
    return link.user if link else None


def draft_preview_markup(draft_id):
    keyboard = [
        [
            InlineKeyboardButton("✅ Envoyer", callback_data=f"d:{draft_id}:send"),
            InlineKeyboardButton("🔁 Régénérer", callback_data=f"d:{draft_id}:regen"),
        ],
        [InlineKeyboardButton("❌ Annuler", callback_data=f"d:{draft_id}:cancel")],
    ]
    return InlineKeyboardMarkup(keyboard)


def draft_preview_text(draft):
    preview_url = f"{app.config['SITE_BASE_URL']}/newsletter/telegram_preview/{draft.preview_token}"
    return (
        f"✅ <b>Contenu généré</b>\n\n"
        f"<b>Objet :</b> {draft.subject}\n\n"
        f"🔗 <a href=\"{preview_url}\">Voir l'aperçu</a>\n\n"
        f"Que voulez-vous faire ?"
    )


def recipient_menu(draft, user):
    selected_groups = set(draft.get_group_ids())
    selected_contacts = set(draft.get_contact_ids())

    groups = Group.query.filter_by(user_id=user.id).all()
    contacts = Contact.query.filter_by(user_id=user.id).all()
    smtp_configs = user.smtp_configs.all()

    rows = []
    for g in groups:
        mark = "✅" if g.id in selected_groups else "⬜"
        rows.append([InlineKeyboardButton(f"{mark} 👥 {g.name}", callback_data=f"d:{draft.id}:g:{g.id}")])
    for c in contacts:
        mark = "✅" if c.id in selected_contacts else "⬜"
        rows.append([InlineKeyboardButton(f"{mark} {c.full_name}", callback_data=f"d:{draft.id}:c:{c.id}")])

    if len(smtp_configs) > 1:
        for s in smtp_configs:
            mark = "🔘" if draft.smtp_config_id == s.id else "⚪"
            rows.append([InlineKeyboardButton(f"{mark} SMTP: {s.alias}", callback_data=f"d:{draft.id}:smtp:{s.id}")])
    elif len(smtp_configs) == 1 and not draft.smtp_config_id:
        draft.smtp_config_id = smtp_configs[0].id
        db.session.commit()

    rows.append([InlineKeyboardButton("◀ Retour", callback_data=f"d:{draft.id}:back")])
    rows.append([
        InlineKeyboardButton("🚀 Envoyer maintenant", callback_data=f"d:{draft.id}:confirm"),
        InlineKeyboardButton("🕒 Programmer", callback_data=f"d:{draft.id}:schedule"),
    ])

    text = (
        "👥 <b>Choisissez les destinataires</b>\n\n"
        "Cochez les groupes et/ou contacts individuels à qui envoyer cette newsletter, "
        "puis envoyez-la maintenant ou programmez-la."
    )
    if not smtp_configs:
        text += "\n\n⚠️ Aucune configuration SMTP trouvée sur le site : ajoutez-en une avant d'envoyer."

    return text, InlineKeyboardMarkup(rows)


def recurrence_menu(draft_id):
    keyboard = [
        [InlineKeyboardButton("Une seule fois", callback_data=f"rs:{draft_id}:none")],
        [InlineKeyboardButton("Tous les jours", callback_data=f"rs:{draft_id}:daily")],
        [InlineKeyboardButton("Toutes les semaines", callback_data=f"rs:{draft_id}:weekly")],
        [InlineKeyboardButton("Tous les mois", callback_data=f"rs:{draft_id}:monthly")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    args = context.args

    with app.app_context():
        if args:
            code = args[0].strip()
            link_code = TelegramLinkCode.query.filter_by(code=code).first()
            if not link_code:
                await update.message.reply_text(
                    "❌ Code de liaison invalide ou expiré. Régénérez-en un depuis Réglages > Bot Telegram sur le site."
                )
                return

            if TelegramLink.query.filter_by(chat_id=str(chat_id)).first():
                await update.message.reply_text("Ce compte Telegram est déjà lié à un compte MIRLETTER.")
                return

            chat = update.effective_chat
            label = chat.full_name or (f"@{chat.username}" if chat.username else f"Telegram {chat_id}")
            user = User.query.get(link_code.user_id)

            link = TelegramLink(user_id=link_code.user_id, chat_id=str(chat_id), label=label)
            db.session.add(link)
            db.session.delete(link_code)
            db.session.commit()

            await update.message.reply_text(
                f"✅ Compte Telegram lié avec succès à {user.username} !\n\n"
                "Utilisez /newsletter pour composer une newsletter, ou /scheduled pour voir les envois programmés."
            )
            return

        user = get_linked_user(chat_id)
        if user:
            await update.message.reply_text(
                f"👋 Bonjour, ce compte Telegram est lié à {user.username}.\n"
                "Utilisez /newsletter pour composer une newsletter."
            )
        else:
            await update.message.reply_text(
                "👋 Bienvenue sur le bot MIRLETTER !\n\n"
                "Pour lier ce compte Telegram, rendez-vous dans Réglages > Bot Telegram sur le site, "
                "générez un code, puis envoyez-moi : /start <code>"
            )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 <b>Commandes disponibles</b>\n\n"
        "/newsletter — générer une nouvelle newsletter avec l'IA\n"
        "/scheduled — voir et annuler les envois programmés\n"
        "/cancel — annuler la composition en cours\n"
        "/start &lt;code&gt; — lier ce compte Telegram à MIRLETTER",
        parse_mode=ParseMode.HTML,
    )


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Composition annulée.")


async def cmd_newsletter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    with app.app_context():
        user = get_linked_user(chat_id)
        if not user:
            await update.message.reply_text(
                "❌ Ce compte Telegram n'est pas lié. Rendez-vous dans Réglages > Bot Telegram sur le site pour obtenir un code."
            )
            return
        if not user.smtp_configs.first():
            await update.message.reply_text(
                "❌ Aucune configuration SMTP n'est enregistrée sur votre compte. Ajoutez-en une dans Réglages avant de continuer."
            )
            return

    context.user_data.clear()
    context.user_data['state'] = STATE_AWAITING_SUBJECT
    await update.message.reply_text("✏️ Quel est l'objet (sujet) de cette newsletter ?")


async def cmd_scheduled(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    with app.app_context():
        user = get_linked_user(chat_id)
        if not user:
            await update.message.reply_text("❌ Ce compte Telegram n'est pas lié.")
            return

        items = ScheduledNewsletter.query.filter_by(user_id=user.id, status='pending') \
            .order_by(ScheduledNewsletter.scheduled_at.asc()).all()

        if not items:
            await update.message.reply_text("Aucune newsletter programmée pour le moment.")
            return

        for item in items:
            text = (
                f"🕒 <b>{item.subject}</b>\n"
                f"Prochain envoi : {item.scheduled_at.strftime('%d/%m/%Y %H:%M')}\n"
                f"Répétition : {RECURRENCE_LABELS.get(item.recurrence or 'none', 'une seule fois')}"
            )
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Annuler", callback_data=f"sched:{item.id}:cancel")]])
            await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    state = context.user_data.get('state')
    text = update.message.text.strip()

    if state == STATE_AWAITING_SUBJECT:
        context.user_data['subject'] = text
        context.user_data['state'] = STATE_AWAITING_PROMPT
        await update.message.reply_text(
            "🧠 Décrivez le contenu que vous souhaitez générer (thème, ton, points clés...). "
            "L'IA va rédiger le HTML de la newsletter."
        )
        return

    if state == STATE_AWAITING_PROMPT:
        await update.message.reply_text("⏳ Génération du contenu en cours...")
        with app.app_context():
            user = get_linked_user(chat_id)
            success, html_or_error = MistralService.generate_html(text)
            if not success:
                await update.message.reply_text(f"❌ {html_or_error}")
                context.user_data['state'] = None
                return

            draft = TelegramDraft(
                user_id=user.id,
                chat_id=str(chat_id),
                subject=context.user_data.get('subject', 'Newsletter'),
                content=html_or_error,
                prompt=text,
            )
            db.session.add(draft)
            db.session.commit()
            context.user_data['draft_id'] = draft.id
            context.user_data['state'] = None
            await update.message.reply_text(
                draft_preview_text(draft),
                parse_mode=ParseMode.HTML,
                reply_markup=draft_preview_markup(draft.id),
            )
        return

    if state == STATE_AWAITING_REGEN_PROMPT:
        draft_id = context.user_data.get('draft_id')
        await update.message.reply_text("⏳ Régénération du contenu en cours...")
        with app.app_context():
            draft = TelegramDraft.query.get(draft_id)
            if not draft or draft.chat_id != str(chat_id):
                await update.message.reply_text("❌ Brouillon introuvable.")
                context.user_data['state'] = None
                return
            success, html_or_error = MistralService.generate_html(text, previous_content=draft.content)
            if not success:
                await update.message.reply_text(f"❌ {html_or_error}")
                context.user_data['state'] = None
                return
            draft.content = html_or_error
            draft.prompt = text
            db.session.commit()
            context.user_data['state'] = None
            await update.message.reply_text(
                draft_preview_text(draft),
                parse_mode=ParseMode.HTML,
                reply_markup=draft_preview_markup(draft.id),
            )
        return

    if state == STATE_AWAITING_SCHEDULE_DATETIME:
        draft_id = context.user_data.get('draft_id')
        try:
            parsed = date_parser.parse(text, dayfirst=True)
        except (ValueError, OverflowError):
            await update.message.reply_text(
                "❌ Date/heure non reconnue. Réessayez, par exemple : 10/07/2026 18:00"
            )
            return

        if parsed < datetime.now():
            await update.message.reply_text("❌ Cette date/heure est déjà passée. Choisissez une date future.")
            return

        context.user_data['schedule_dt'] = parsed
        context.user_data['state'] = None
        await update.message.reply_text(
            f"📅 Envoi programmé pour le {parsed.strftime('%d/%m/%Y à %H:%M')}.\n\n"
            "À quelle fréquence ?",
            reply_markup=recurrence_menu(draft_id),
        )
        return

    await update.message.reply_text("Utilisez /newsletter pour composer une nouvelle newsletter.")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    await query.answer()

    parts = query.data.split(":")
    prefix = parts[0]

    if prefix == "sched":
        schedule_id = int(parts[1])
        action = parts[2]
        with app.app_context():
            item = ScheduledNewsletter.query.get(schedule_id)
            user = get_linked_user(chat_id)
            if not item or not user or item.user_id != user.id:
                await query.edit_message_text("❌ Introuvable.")
                return
            if action == "cancel":
                item.status = 'cancelled'
                db.session.commit()
                await query.edit_message_text(f"❌ Envoi programmé « {item.subject} » annulé.")
        return

    if prefix == "rs":
        draft_id = int(parts[1])
        recurrence = parts[2]
        recurrence = None if recurrence == 'none' else recurrence
        schedule_dt = context.user_data.get('schedule_dt')

        with app.app_context():
            draft = TelegramDraft.query.get(draft_id)
            if not draft or draft.chat_id != str(chat_id):
                await query.edit_message_text("❌ Brouillon introuvable.")
                return
            if not schedule_dt:
                await query.edit_message_text("❌ Session expirée, relancez la programmation avec /newsletter.")
                return

            user = User.query.get(draft.user_id)
            smtp_config = SMTPConfig.query.get(draft.smtp_config_id) if draft.smtp_config_id else user.smtp_configs.first()

            scheduled_item = ScheduledNewsletter(
                user_id=user.id,
                source='telegram',
                subject=draft.subject,
                content=draft.content,
                prompt=draft.prompt,
                ai_generate=recurrence is not None,  # recurring campaigns re-generate content each run
                smtp_config_id=smtp_config.id if smtp_config else None,
                group_ids=draft.group_ids,
                contact_ids=draft.contact_ids,
                scheduled_at=schedule_dt,
                recurrence=recurrence,
            )
            db.session.add(scheduled_item)
            draft.status = 'scheduled'
            db.session.commit()

            label = RECURRENCE_LABELS.get(recurrence or 'none', 'une seule fois')
            await query.edit_message_text(
                f"🕒 Newsletter « {draft.subject} » programmée le "
                f"{schedule_dt.strftime('%d/%m/%Y à %H:%M')} ({label})."
            )
        context.user_data.clear()
        return

    if prefix != "d":
        return

    draft_id = int(parts[1])
    action = parts[2]

    with app.app_context():
        draft = TelegramDraft.query.get(draft_id)
        if not draft or draft.chat_id != str(chat_id):
            await query.edit_message_text("❌ Ce brouillon n'est plus disponible.")
            return
        user = User.query.get(draft.user_id)

        if action == "regen":
            context.user_data['state'] = STATE_AWAITING_REGEN_PROMPT
            context.user_data['draft_id'] = draft.id
            await query.message.reply_text(
                "🧠 Décrivez ce que vous voulez changer ou le nouveau contenu souhaité."
            )
            return

        if action == "cancel":
            draft.status = 'cancelled'
            db.session.commit()
            context.user_data.clear()
            await query.edit_message_text("❌ Brouillon annulé.")
            return

        if action == "send":
            text, markup = recipient_menu(draft, user)
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
            return

        if action == "back":
            await query.edit_message_text(
                draft_preview_text(draft),
                parse_mode=ParseMode.HTML,
                reply_markup=draft_preview_markup(draft.id),
            )
            return

        if action == "g":
            group_id = int(parts[3])
            ids = set(draft.get_group_ids())
            ids.symmetric_difference_update({group_id})
            draft.group_ids = ",".join(str(i) for i in ids)
            db.session.commit()
            text, markup = recipient_menu(draft, user)
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
            return

        if action == "c":
            contact_id = int(parts[3])
            ids = set(draft.get_contact_ids())
            ids.symmetric_difference_update({contact_id})
            draft.contact_ids = ",".join(str(i) for i in ids)
            db.session.commit()
            text, markup = recipient_menu(draft, user)
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
            return

        if action == "smtp":
            smtp_id = int(parts[3])
            draft.smtp_config_id = smtp_id
            db.session.commit()
            text, markup = recipient_menu(draft, user)
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
            return

        if action == "confirm":
            await send_draft(query, draft, user)
            context.user_data.clear()
            return

        if action == "schedule":
            if not draft.get_group_ids() and not draft.get_contact_ids():
                await query.answer("Sélectionnez au moins un groupe ou un contact.", show_alert=True)
                return
            context.user_data['state'] = STATE_AWAITING_SCHEDULE_DATETIME
            context.user_data['draft_id'] = draft.id
            await query.message.reply_text(
                "🕒 À quelle date et heure voulez-vous programmer l'envoi ?\n"
                "Exemple : 10/07/2026 18:00"
            )
            return


async def send_draft(query, draft, user):
    group_ids = draft.get_group_ids()
    contact_ids = draft.get_contact_ids()

    if not group_ids and not contact_ids:
        await query.answer("Sélectionnez au moins un groupe ou un contact.", show_alert=True)
        return

    smtp_config = SMTPConfig.query.get(draft.smtp_config_id) if draft.smtp_config_id else user.smtp_configs.first()
    if not smtp_config:
        await query.answer("Aucune configuration SMTP disponible.", show_alert=True)
        return

    with app.test_request_context(base_url=app.config['SITE_BASE_URL']):
        total_sent, total_targeted = send_newsletter(
            user, smtp_config, draft.subject, draft.content,
            group_ids=group_ids, contact_ids=contact_ids
        )
        draft.status = 'sent'
        db.session.commit()

    await query.edit_message_text(f"🚀 Newsletter envoyée à {total_sent} destinataire(s) sur {total_targeted}.")


def build_application():
    with app.app_context():
        token = app.config.get('TELEGRAM_BOT_TOKEN')
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN n'est pas configuré (voir .env).")

    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("cancel", cmd_cancel))
    application.add_handler(CommandHandler("newsletter", cmd_newsletter))
    application.add_handler(CommandHandler("scheduled", cmd_scheduled))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    return application


def run_bot_blocking(install_signal_handlers=True):
    """
    Starts the bot's polling loop and blocks until it stops.

    install_signal_handlers must be False when this runs outside the main
    thread (e.g. spawned from run.py alongside Flask), since asyncio/PTB can
    only register OS signal handlers from the main thread.
    """
    import asyncio
    asyncio.set_event_loop(asyncio.new_event_loop())

    application = build_application()
    logger.info("Bot Telegram MIRLETTER démarré (polling)...")
    kwargs = {"allowed_updates": Update.ALL_TYPES, "close_loop": False}
    if not install_signal_handlers:
        kwargs["stop_signals"] = None
    application.run_polling(**kwargs)


def main():
    run_bot_blocking(install_signal_handlers=True)


if __name__ == "__main__":
    main()
