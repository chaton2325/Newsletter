"""
Background worker that sends scheduled / recurring newsletters (created either from
the web compose page or from the Telegram bot). Runs inside the same process as the
Flask app (see run.py), polling every minute via APScheduler.
"""
import logging
from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

_scheduler = None


def _advance(scheduled_at, recurrence):
    if recurrence == 'daily':
        return scheduled_at + timedelta(days=1)
    if recurrence == 'weekly':
        return scheduled_at + timedelta(weeks=1)
    if recurrence == 'monthly':
        return scheduled_at + relativedelta(months=1)
    return None


def _process_due(app):
    from __init__ import db
    from models.schedule import ScheduledNewsletter
    from services.mistral_service import MistralService
    from services.newsletter_service import send_newsletter

    with app.app_context():
        now = datetime.now()
        due = ScheduledNewsletter.query.filter(
            ScheduledNewsletter.status == 'pending',
            ScheduledNewsletter.scheduled_at <= now
        ).all()

        for item in due:
            try:
                content = item.content
                if item.ai_generate and item.prompt:
                    success, html_or_error = MistralService.generate_html(item.prompt, previous_content=item.content)
                    if not success:
                        raise RuntimeError(html_or_error)
                    content = html_or_error
                    item.content = html_or_error

                smtp_config = item.smtp_config or item.user.smtp_configs.first()
                if not smtp_config:
                    raise RuntimeError("Aucune configuration SMTP disponible.")

                with app.test_request_context(base_url=app.config['SITE_BASE_URL']):
                    total_sent, total_targeted = send_newsletter(
                        item.user, smtp_config, item.subject, content,
                        group_ids=item.get_group_ids(), contact_ids=item.get_contact_ids()
                    )

                item.last_run_at = now
                item.last_error = None

                next_run = _advance(item.scheduled_at, item.recurrence)
                if next_run:
                    item.scheduled_at = next_run
                    item.status = 'pending'
                else:
                    item.status = 'sent'

                logger.info(f"ScheduledNewsletter #{item.id}: envoyé à {total_sent}/{total_targeted} destinataire(s).")

            except Exception as e:
                item.status = 'failed'
                item.last_error = str(e)
                item.last_run_at = now
                logger.exception(f"ScheduledNewsletter #{item.id} a échoué : {e}")

            db.session.commit()


def init_scheduler(app):
    """Starts the background scheduler once. Safe to call multiple times (no-op after the first)."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        _process_due,
        trigger='interval',
        minutes=1,
        args=[app],
        id='process_scheduled_newsletters',
        next_run_time=datetime.now(),
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    logger.info("Scheduler de newsletters programmées démarré (vérification toutes les minutes).")
    return _scheduler
