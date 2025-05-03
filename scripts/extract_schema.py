"""Script to extract database schema and save it to a JSON file."""

import logging
import os
import sys
from pathlib import Path

# Add project root to Python path to allow importing from src
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.sens.schema import SchemaExtractor  # noqa: E402

# --- Configuration ---
# Output path for the schema metadata
DEFAULT_SCHEMA_PATH = "config/schema_metadata.json"

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

    schema_output_path = os.getenv("SCHEMA_PATH", DEFAULT_SCHEMA_PATH)
    output_path_obj = Path(schema_output_path)

    # Ensure the output directory exists
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Schema will be saved to: {schema_output_path}")

    try:
        # Instantiate the extractor (assuming it reads DB config from env/defaults)
        extractor = SchemaExtractor()

        # Extract and save the schema
        logger.info("Connecting to database and extracting schema...")
        # Call extract_and_save without output_path, assuming internal handling
        _ = extractor.extract_and_save()

        logger.info(
            "Schema extracted successfully (path determined by SchemaExtractor)"
        )

    except Exception as e:
        logger.exception(f"Failed to extract schema: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
