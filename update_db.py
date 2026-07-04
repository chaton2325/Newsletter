import sqlite3
import os

db_path = os.path.join('instance', 'mirletter.db')

def update_database():
    if not os.path.exists(db_path):
        print(f"La base de données n'existe pas : {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Mise à jour de la table 'groups'
    columns_groups = [
        ("is_paid", "BOOLEAN DEFAULT 0"),
        ("price", "FLOAT DEFAULT 0.0"),
        ("currency", "VARCHAR(3) DEFAULT 'eur'"),
        ("stripe_price_id", "VARCHAR(128)"),
        ("description", "TEXT"),
        ("smtp_config_id", "INTEGER"),
        ("welcome_email_subject", "VARCHAR(128)"),
        ("welcome_email_body", "TEXT")
    ]

    for col_name, col_type in columns_groups:
        try:
            cursor.execute(f"ALTER TABLE groups ADD COLUMN {col_name} {col_type}")
            print(f"Groups: Colonne '{col_name}' ajoutée.")
        except sqlite3.OperationalError:
            pass

    # 2. Création de la table 'subscriptions' (remplace contacts_groups)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            contact_id INTEGER NOT NULL,
            group_id INTEGER NOT NULL,
            subscribed_at DATETIME,
            stripe_subscription_id VARCHAR(128),
            PRIMARY KEY (contact_id, group_id),
            FOREIGN KEY(contact_id) REFERENCES contacts(id),
            FOREIGN KEY(group_id) REFERENCES groups(id)
        )
    ''')
    print("Table 'subscriptions' créée ou déjà présente.")

    # 3. Migration des données existantes si nécessaire
    try:
        cursor.execute("SELECT contact_id, group_id FROM contacts_groups")
        old_data = cursor.fetchall()
        for c_id, g_id in old_data:
            cursor.execute("INSERT OR IGNORE INTO subscriptions (contact_id, group_id, subscribed_at) VALUES (?, ?, datetime('now'))", (c_id, g_id))
        print(f"Migration réussie : {len(old_data)} abonnements déplacés.")
    except sqlite3.OperationalError:
        print("Aucune donnée ancienne à migrer dans 'contacts_groups'.")

    # 4. Table 'telegram_drafts' (brouillons générés via le bot Telegram)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS telegram_drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            chat_id VARCHAR(64) NOT NULL,
            subject VARCHAR(256),
            content TEXT,
            prompt TEXT,
            preview_token VARCHAR(64) NOT NULL UNIQUE,
            smtp_config_id INTEGER,
            group_ids VARCHAR(256) DEFAULT '',
            contact_ids VARCHAR(256) DEFAULT '',
            status VARCHAR(20) DEFAULT 'draft',
            created_at DATETIME,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(smtp_config_id) REFERENCES smtp_configs(id)
        )
    ''')
    print("Table 'telegram_drafts' créée ou déjà présente.")

    # 5. Tables 'telegram_links' / 'telegram_link_codes' (plusieurs comptes Telegram par utilisateur)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS telegram_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            chat_id VARCHAR(64) NOT NULL UNIQUE,
            label VARCHAR(128),
            linked_at DATETIME,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS telegram_link_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            code VARCHAR(32) NOT NULL UNIQUE,
            created_at DATETIME,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    print("Tables 'telegram_links' / 'telegram_link_codes' créées ou déjà présentes.")

    # 5b. Migration depuis l'ancien schéma à liaison unique (users.telegram_chat_id / telegram_link_code)
    try:
        cursor.execute("SELECT id, telegram_chat_id, telegram_link_code FROM users")
        for user_id, chat_id, link_code in cursor.fetchall():
            if chat_id:
                cursor.execute(
                    "INSERT OR IGNORE INTO telegram_links (user_id, chat_id, label, linked_at) VALUES (?, ?, ?, datetime('now'))",
                    (user_id, chat_id, None)
                )
            if link_code:
                cursor.execute(
                    "INSERT OR IGNORE INTO telegram_link_codes (user_id, code, created_at) VALUES (?, ?, datetime('now'))",
                    (user_id, link_code)
                )

        # SQLite >= 3.35 supports DROP COLUMN; older versions just keep the (now unused) columns.
        try:
            cursor.execute("ALTER TABLE users DROP COLUMN telegram_chat_id")
            cursor.execute("ALTER TABLE users DROP COLUMN telegram_link_code")
            print("Users: anciennes colonnes 'telegram_chat_id'/'telegram_link_code' supprimées.")
        except sqlite3.OperationalError:
            print("Users: colonnes Telegram legacy conservées (SQLite trop ancien pour DROP COLUMN).")
    except sqlite3.OperationalError:
        pass  # Old columns don't exist (fresh install) — nothing to migrate.

    # 6. Table 'scheduled_newsletters' (envois programmés / récurrents, web + Telegram)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scheduled_newsletters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            source VARCHAR(20) DEFAULT 'web',
            subject VARCHAR(256) NOT NULL,
            content TEXT,
            prompt TEXT,
            ai_generate BOOLEAN DEFAULT 0,
            smtp_config_id INTEGER,
            group_ids VARCHAR(256) DEFAULT '',
            contact_ids VARCHAR(256) DEFAULT '',
            scheduled_at DATETIME NOT NULL,
            recurrence VARCHAR(20),
            status VARCHAR(20) DEFAULT 'pending',
            last_run_at DATETIME,
            last_error TEXT,
            created_at DATETIME,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(smtp_config_id) REFERENCES smtp_configs(id)
        )
    ''')
    print("Table 'scheduled_newsletters' créée ou déjà présente.")

    conn.commit()
    conn.close()
    print("Mise à jour de la base de données terminée avec succès.")

if __name__ == "__main__":
    update_database()
