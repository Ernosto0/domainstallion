from sqlalchemy import create_engine, text
from backend.database import SQLALCHEMY_DATABASE_URL


def migrate():
    # Create engine
    engine = create_engine(SQLALCHEMY_DATABASE_URL)

    with engine.connect() as conn:
        try:
            # Create watchlist table
            conn.execute(
                text(
                    """
                CREATE TABLE IF NOT EXISTS watchlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    domain_name TEXT NOT NULL,
                    domain_extension TEXT NOT NULL,
                    status TEXT DEFAULT 'taken',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notify_when_available BOOLEAN DEFAULT TRUE,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                );
                """
                )
            )

            # Check if columns exist in favorites table
            result = conn.execute(text("PRAGMA table_info(favorites);"))
            existing_columns = [row[1] for row in result.fetchall()]

            # Add columns only if they don't exist
            columns_to_add = {
                "total_score": "INTEGER DEFAULT 0",
                "length_score": "INTEGER DEFAULT 0",
                "dictionary_score": "INTEGER DEFAULT 0",
                "pronounceability_score": "INTEGER DEFAULT 0",
                "repetition_score": "INTEGER DEFAULT 0",
                "tld_score": "INTEGER DEFAULT 0",
            }

            for column_name, column_type in columns_to_add.items():
                if column_name not in existing_columns:
                    conn.execute(
                        text(
                            f"""
                        ALTER TABLE favorites 
                        ADD COLUMN {column_name} {column_type};
                        """
                        )
                    )

            conn.commit()
            print("Migration completed successfully")
        except Exception as e:
            print(f"Error during migration: {str(e)}")
            conn.rollback()


if __name__ == "__main__":
    migrate()
