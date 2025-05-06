"""Script to extract database schema and save it to a JSON file."""

import logging
import sys
from pathlib import Path

# Add project root to Python path to allow importing from src
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.sens.schema import SchemaExtractor  # noqa: E402
from src.sens.settings import get_settings  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main():
    """Main function to extract and save schema."""
    logger.info("Starting schema extraction process...")

    # Get settings
    settings = get_settings()
    schema_path = settings.schema_path

    # Ensure the output directory exists
    schema_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Schema will be saved to: {schema_path}")

    try:
        # Instantiate the extractor with database settings from environment
        extractor = SchemaExtractor(
            host=settings.db_host,
            port=settings.db_port,
            dbname=settings.db_name,
            user=settings.db_user,
            password=settings.db_password,
        )

        # Extract and save the schema
        logger.info("Connecting to database and extracting schema...")
        schema = extractor.extract_and_save()

        logger.info(
            "Schema extracted successfully",
            extra={
                "schema_path": str(schema_path),
                "table_count": len(schema.tables),
                "relationship_count": len(schema.relationships),
            },
        )

    except Exception as e:
        logger.exception(f"Failed to extract schema: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
