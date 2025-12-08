"""Main entry point for data ingestion."""

import argparse
import logging
import sys

from src.config import settings
from src.ingestion import DataType, DriveIngester

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
        "--data-type",
        type=str,
        choices=["content", "style_profile", "style_excerpt"],
        default=None,
        help="Data type to ingest (content, style_profile, style_excerpt)",
    )
    parser.add_argument(
        "--structured",
        action="store_true",
        help="Ingest from structured folder (content/style_profile/style_excerpts subfolders)",
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

        elif args.structured:
            # Ingest from structured folder with content/style subfolders
            folder_id = args.folder_id or settings.target_folder_id
            if not folder_id:
                logger.error("No folder ID specified. Use --folder-id or set TARGET_FOLDER_ID")
                sys.exit(1)

            logger.info(f"Starting structured ingestion from folder: {folder_id}")
            counts = ingester.ingest_structured_folder(folder_id=folder_id)
            logger.info("Ingestion complete:")
            for data_type, count in counts.items():
                logger.info(f"  {data_type}: {count} items")

        else:
            # Ingest from Google Drive (single folder)
            folder_id = args.folder_id or settings.target_folder_id
            if not folder_id:
                logger.error("No folder ID specified. Use --folder-id or set TARGET_FOLDER_ID")
                sys.exit(1)

            # Convert data_type string to DataType enum if specified
            data_type = DataType(args.data_type) if args.data_type else None

            logger.info(f"Starting ingestion from folder: {folder_id}")
            count = ingester.ingest_folder(
                folder_id=folder_id,
                recursive=not args.no_recursive,
                data_type=data_type,
            )
            logger.info(f"Successfully ingested {count} chunks from Google Drive")

        ingester.close()

    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
