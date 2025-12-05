"""Google Drive data ingestion for RAG system."""

import io
import json
import logging
from pathlib import Path
from typing import Any

import psycopg2
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from langchain_google_vertexai import VertexAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import settings
from src.retriever.article_retriever import ArticleType

logger = logging.getLogger(__name__)


class DriveIngester:
    """Ingest documents from Google Drive into the RAG database.

    This class handles:
    - Google Drive API authentication and file access
    - Article type classification based on file/folder names
    - Text chunking with overlap
    - Embedding generation via Vertex AI
    - Database insertion
    """

    # Keywords for article type classification
    TYPE_KEYWORDS: dict[str, list[str]] = {
        ArticleType.ANNOUNCEMENT.value: [
            "announce",
            "release",
            "お知らせ",
            "リリース",
            "発表",
            "ローンチ",
        ],
        ArticleType.EVENT_REPORT.value: [
            "event",
            "report",
            "勉強会",
            "イベント",
            "セミナー",
            "lt",
            "meetup",
        ],
        ArticleType.INTERVIEW.value: [
            "interview",
            "インタビュー",
            "入社",
            "社員紹介",
            "転職",
        ],
        ArticleType.CULTURE.value: [
            "culture",
            "カルチャー",
            "制度",
            "福利厚生",
            "働き方",
            "リモート",
        ],
    }

    def __init__(
        self,
        service_account_file: str | None = None,
        embeddings: VertexAIEmbeddings | None = None,
        connection_string: str | None = None,
    ):
        """Initialize the Drive ingester.

        Args:
            service_account_file: Path to service account JSON file.
            embeddings: VertexAIEmbeddings instance (creates one if None).
            connection_string: Database connection string.
        """
        sa_file = service_account_file or settings.service_account_file
        if not sa_file:
            raise ValueError(
                "Service account file is required. "
                "Set SERVICE_ACCOUNT_FILE environment variable or pass it directly."
            )

        # Initialize Google Drive API
        creds = service_account.Credentials.from_service_account_file(
            sa_file,
            scopes=["https://www.googleapis.com/auth/drive.readonly"],
        )
        self.drive_service = build("drive", "v3", credentials=creds)

        # Initialize embeddings
        self.embeddings = embeddings or VertexAIEmbeddings(
            model=settings.embedding_model,
            project=settings.google_project_id,
            location=settings.google_location,
        )

        # Initialize database connection
        self._connection_string = connection_string or settings.db_connection_string
        self.conn = psycopg2.connect(self._connection_string)

        # Initialize text splitter
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            separators=["\n\n", "\n", "。", ".", " ", ""],
        )

    def classify_article_type(
        self,
        file_name: str,
        folder_name: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Classify article type based on file/folder names and metadata.

        Args:
            file_name: Name of the file.
            folder_name: Name of the containing folder.
            metadata: Optional additional metadata for classification.

        Returns:
            Article type string (one of ArticleType enum values).
        """
        # Combine all text for keyword matching
        search_text = f"{file_name} {folder_name}".lower()
        if metadata:
            search_text += f" {json.dumps(metadata, ensure_ascii=False)}".lower()

        # Check each type's keywords
        for article_type, keywords in self.TYPE_KEYWORDS.items():
            if any(keyword in search_text for keyword in keywords):
                return article_type

        # Default to CULTURE if no match
        return ArticleType.CULTURE.value

    def ingest_folder(
        self,
        folder_id: str | None = None,
        recursive: bool = True,
    ) -> int:
        """Ingest all files from a Google Drive folder.

        Args:
            folder_id: Google Drive folder ID. Uses TARGET_FOLDER_ID if None.
            recursive: Whether to process subfolders.

        Returns:
            Number of documents ingested.
        """
        folder_id = folder_id or settings.target_folder_id
        if not folder_id:
            raise ValueError("Folder ID is required")

        return self._process_folder(folder_id, "", recursive)

    def _process_folder(
        self,
        folder_id: str,
        parent_path: str,
        recursive: bool,
    ) -> int:
        """Recursively process a folder and its contents.

        Args:
            folder_id: Google Drive folder ID.
            parent_path: Path of parent folders for classification.
            recursive: Whether to process subfolders.

        Returns:
            Number of documents ingested.
        """
        total_count = 0

        # Get folder name
        folder_meta = self.drive_service.files().get(fileId=folder_id, fields="name").execute()
        folder_name = folder_meta.get("name", "")
        current_path = f"{parent_path}/{folder_name}" if parent_path else folder_name

        logger.info(f"Processing folder: {current_path}")

        # List files in folder
        page_token = None
        while True:
            results = (
                self.drive_service.files()
                .list(
                    q=f"'{folder_id}' in parents and trashed = false",
                    fields="nextPageToken, files(id, name, mimeType)",
                    pageToken=page_token,
                )
                .execute()
            )

            for item in results.get("files", []):
                mime_type = item.get("mimeType", "")

                if mime_type == "application/vnd.google-apps.folder":
                    # Process subfolder
                    if recursive:
                        total_count += self._process_folder(item["id"], current_path, recursive)
                else:
                    # Process file
                    count = self.process_file(item, current_path)
                    total_count += count

            page_token = results.get("nextPageToken")
            if not page_token:
                break

        return total_count

    def process_file(
        self,
        file_item: dict[str, str],
        folder_path: str = "",
    ) -> int:
        """Process a single file from Google Drive.

        Args:
            file_item: File metadata dict with 'id', 'name', 'mimeType'.
            folder_path: Path of containing folders.

        Returns:
            Number of chunks ingested (0 if file skipped).
        """
        file_name = file_item["name"]
        file_id = file_item["id"]
        mime_type = file_item.get("mimeType", "")

        # Skip unsupported file types
        if not self._is_supported_file(file_name, mime_type):
            logger.debug(f"Skipping unsupported file: {file_name}")
            return 0

        logger.info(f"Processing file: {file_name}")

        try:
            # Download file content
            content = self._download_file(file_id)
            if not content:
                logger.warning(f"Empty content for file: {file_name}")
                return 0

            # Classify article type
            article_type = self.classify_article_type(file_name, folder_path)

            # Split into chunks
            chunks = self._split_content(file_name, content)
            if not chunks:
                logger.warning(f"No chunks generated for file: {file_name}")
                return 0

            # Generate embeddings
            vectors = self.embeddings.embed_documents(chunks)

            # Insert into database
            self._insert_documents(
                chunks=chunks,
                vectors=vectors,
                article_type=article_type,
                file_name=file_name,
                file_id=file_id,
            )

            logger.info(f"Ingested {len(chunks)} chunks from: {file_name}")
            return len(chunks)

        except Exception as e:
            logger.error(f"Error processing file {file_name}: {e}")
            return 0

    def _is_supported_file(self, file_name: str, mime_type: str) -> bool:
        """Check if file type is supported for ingestion."""
        supported_extensions = {".md", ".txt", ".jsonl"}
        ext = Path(file_name).suffix.lower()
        return ext in supported_extensions

    def _download_file(self, file_id: str) -> str:
        """Download file content from Google Drive."""
        request = self.drive_service.files().get_media(fileId=file_id)
        content_io = io.BytesIO()
        downloader = MediaIoBaseDownload(content_io, request)

        done = False
        while not done:
            _, done = downloader.next_chunk()

        return content_io.getvalue().decode("utf-8")

    def _split_content(self, file_name: str, content: str) -> list[str]:
        """Split content into chunks based on file type."""
        ext = Path(file_name).suffix.lower()

        if ext == ".jsonl":
            # JSONL: each line is a separate document
            chunks = []
            for line in content.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    # Try common text fields
                    text = (
                        data.get("text")
                        or data.get("content")
                        or data.get("body")
                        or json.dumps(data, ensure_ascii=False)
                    )
                    if text:
                        chunks.append(text)
                except json.JSONDecodeError:
                    # Not valid JSON, treat as plain text
                    chunks.append(line)
            return chunks
        else:
            # Markdown/text: use text splitter
            return self.splitter.split_text(content)

    def _insert_documents(
        self,
        chunks: list[str],
        vectors: list[list[float]],
        article_type: str,
        file_name: str,
        file_id: str,
    ) -> None:
        """Insert document chunks into the database."""
        with self.conn.cursor() as cur:
            for i, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
                metadata = {
                    "source": file_name,
                    "file_id": file_id,
                }
                cur.execute(
                    """
                    INSERT INTO documents
                    (content, embedding, article_type, source_file, chunk_index,
                     total_chunks, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        chunk,
                        vector,
                        article_type,
                        file_name,
                        i,
                        len(chunks),
                        json.dumps(metadata, ensure_ascii=False),
                    ),
                )
        self.conn.commit()

    def ingest_local_file(
        self,
        file_path: str | Path,
        article_type: str | None = None,
    ) -> int:
        """Ingest a local file (for testing without Google Drive).

        Args:
            file_path: Path to the local file.
            article_type: Article type override (auto-detected if None).

        Returns:
            Number of chunks ingested.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        file_name = file_path.name
        content = file_path.read_text(encoding="utf-8")

        # Auto-detect article type if not provided
        if article_type is None:
            article_type = self.classify_article_type(file_name, str(file_path.parent))

        # Split into chunks
        chunks = self._split_content(file_name, content)
        if not chunks:
            return 0

        # Generate embeddings
        vectors = self.embeddings.embed_documents(chunks)

        # Insert into database
        self._insert_documents(
            chunks=chunks,
            vectors=vectors,
            article_type=article_type,
            file_name=file_name,
            file_id=f"local:{file_path}",
        )

        logger.info(f"Ingested {len(chunks)} chunks from local file: {file_name}")
        return len(chunks)

    def close(self):
        """Close database connection."""
        if self.conn and not self.conn.closed:
            self.conn.close()

    def __del__(self):
        """Cleanup on deletion."""
        self.close()
