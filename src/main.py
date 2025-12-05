"""Main entry point for data ingestion."""

import argparse
import logging
import sys

from src.config import settings
from src.ingestion import DriveIngester

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Main function for data ingestion CLI."""
    parser = argparse.ArgumentParser(
        description="Ingest documents from Google Drive into RAG database"
    )
    parser.add_argument(
        "--folder-id",
        type=str,
        default=None,
        help="Google Drive folder ID to ingest (uses TARGET_FOLDER_ID if not specified)",
    )
    parser.add_argument(
        "--local-file",
        type=str,
        default=None,
        help="Path to local file to ingest (for testing)",
    )
    parser.add_argument(
        "--article-type",
        type=str,
        choices=["ANNOUNCEMENT", "EVENT_REPORT", "INTERVIEW", "CULTURE"],
        default=None,
        help="Article type for local file ingestion",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Do not process subfolders recursively",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        ingester = DriveIngester()

        if args.local_file:
            # Ingest local file
            logger.info(f"Ingesting local file: {args.local_file}")
            count = ingester.ingest_local_file(
                args.local_file,
                article_type=args.article_type,
            )
            logger.info(f"Successfully ingested {count} chunks from local file")
        else:
            # Ingest from Google Drive
            folder_id = args.folder_id or settings.target_folder_id
            if not folder_id:
                logger.error("No folder ID specified. Use --folder-id or set TARGET_FOLDER_ID")
                sys.exit(1)

            logger.info(f"Starting ingestion from folder: {folder_id}")
            count = ingester.ingest_folder(
                folder_id=folder_id,
                recursive=not args.no_recursive,
            )
            logger.info(f"Successfully ingested {count} chunks from Google Drive")

        ingester.close()

    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
