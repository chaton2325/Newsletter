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

    conn.commit()
    conn.close()
    print("Mise à jour de la base de données terminée avec succès.")

if __name__ == "__main__":
    update_database()
