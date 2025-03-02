from sqlalchemy import create_engine, text
from backend.database import SQLALCHEMY_DATABASE_URL


def migrate():
    # Create engine
    engine = create_engine(SQLALCHEMY_DATABASE_URL)

    # Add missing columns
    with engine.connect() as conn:
        try:
            # Check if columns exist first
            conn.execute(
                text(
                    """
                ALTER TABLE favorites 
                ADD COLUMN total_score INTEGER DEFAULT 0;
            """
                )
            )
            conn.execute(
                text(
                    """
                ALTER TABLE favorites 
                ADD COLUMN length_score INTEGER DEFAULT 0;
            """
                )
            )
            conn.execute(
                text(
                    """
                ALTER TABLE favorites 
                ADD COLUMN dictionary_score INTEGER DEFAULT 0;
            """
                )
            )
            conn.execute(
                text(
                    """
                ALTER TABLE favorites 
                ADD COLUMN pronounceability_score INTEGER DEFAULT 0;
            """
                )
            )
            conn.execute(
                text(
                    """
                ALTER TABLE favorites 
                ADD COLUMN repetition_score INTEGER DEFAULT 0;
            """
                )
            )
            conn.execute(
                text(
                    """
                ALTER TABLE favorites 
                ADD COLUMN tld_score INTEGER DEFAULT 0;
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
