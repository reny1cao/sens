"""Script to build the FAISS embedding index for column semantic search."""

import logging
import os
import sys
from pathlib import Path

# Add project root to Python path to allow importing from src
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.sens.retrieval.embedding import EmbeddingSearch  # noqa: E402
from src.sens.settings import get_settings  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],  # Ensure logs go to stdout
)
logger = logging.getLogger(__name__)


def main():
    """Main function to build the embedding index."""
    logger.info("Starting embedding index build process...")

    settings = get_settings()
    schema_path = str(settings.schema_path)
    index_dir = str(settings.index_dir)

    # Ensure schema file exists
    if not Path(schema_path).exists():
        logger.error(
            f"Schema file not found at {schema_path}. Please ensure schema is extracted first."
        )
        sys.exit(1)

    logger.info(f"Using schema file: {schema_path}")
    logger.info(f"Using index directory: {index_dir}")

    try:
        # Initialize the embedding search component
        searcher = EmbeddingSearch(index_dir=index_dir)

        # Build the index
        logger.info("Building FAISS index and lookup map...")
        searcher.build_index(schema_path=schema_path)

        logger.info(f"Embedding index built successfully in {index_dir}")

    except Exception as e:
        logger.exception(f"Failed to build embedding index: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
