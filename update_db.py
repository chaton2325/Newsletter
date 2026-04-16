import sqlite3
import os

# Database path
db_path = os.path.join('instance', 'mirletter.db')

def update_database():
    if not os.path.exists(db_path):
        print(f"La base de données n'existe pas à l'emplacement : {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Columns to add to the 'groups' table
    columns_to_add = [
        ("is_paid", "BOOLEAN DEFAULT 0"),
        ("price", "FLOAT DEFAULT 0.0"),
        ("currency", "VARCHAR(3) DEFAULT 'eur'"),
        ("stripe_price_id", "VARCHAR(128)"),
        ("smtp_config_id", "INTEGER"),
        ("description", "TEXT"),
        ("welcome_email_subject", "VARCHAR(128)"),
        ("welcome_email_body", "TEXT")
    ]

    print("Mise à jour de la table 'groups'...")

    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE groups ADD COLUMN {col_name} {col_type}")
            print(f"Colonne '{col_name}' ajoutée avec succès.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"La colonne '{col_name}' existe déjà.")
            else:
                print(f"Erreur lors de l'ajout de '{col_name}': {e}")

    conn.commit()
    conn.close()
    print("Mise à jour terminée.")

if __name__ == "__main__":
    update_database()
