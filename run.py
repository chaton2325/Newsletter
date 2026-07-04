import os
import threading
from __init__ import create_app

app = create_app()


def start_telegram_bot():
    """Lance le bot Telegram (polling) dans un thread à part, si un token est configuré."""
    if not app.config.get('TELEGRAM_BOT_TOKEN'):
        print("TELEGRAM_BOT_TOKEN non configuré : le bot Telegram ne sera pas démarré.")
        return

    from telegram_bot import run_bot_blocking

    thread = threading.Thread(
        target=run_bot_blocking,
        kwargs={'install_signal_handlers': False},
        daemon=True,
        name='telegram-bot'
    )
    thread.start()


if __name__ == '__main__':
    # Avec le reloader Werkzeug actif, ce script est exécuté deux fois : une fois comme
    # process moniteur, puis relancé dans un sous-processus enfant marqué WERKZEUG_RUN_MAIN=true,
    # qui sert réellement les requêtes. On ne démarre le bot que dans ce process réel,
    # pour éviter deux instances en conflit sur l'API Telegram (getUpdates 409 Conflict).
    USE_RELOADER = True
    if not USE_RELOADER or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        start_telegram_bot()

    # On autorise le mode debug pour le développement
    app.run(debug=True, port=9060, host='0.0.0.0', use_reloader=USE_RELOADER)
