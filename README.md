# etude-rag2

note記事ドラフト自動生成のためのRAG（Retrieval-Augmented Generation）システムです。

## 概要

採用広報記事（お知らせ、イベントレポート、インタビュー、カルチャー記事）の下書きを、過去記事を参照しながら自動生成するシステムです。

## 主な機能

- **ハイブリッド検索**: ベクトル検索（pgvector）と全文検索（pg_trgm）を組み合わせた高精度な類似記事検索
- **BGEリランキング**: クロスエンコーダーによる検索結果の精度向上
- **記事タイプ分類**: 4種類の記事タイプ（お知らせ、イベントレポート、インタビュー、カルチャー）を自動判別
- **段階的コンテンツ生成**: 構成分析 → アウトライン → 各セクション生成のパイプライン
- **品質検証**: ハルシネーション検出、スタイルチェック機能

## 技術スタック

| カテゴリ | 技術 |
|---------|------|
| 言語 | Python 3.12+ |
| パッケージ管理 | uv |
| LLM/Embeddings | Google Vertex AI (Gemini 1.5 Pro, text-embedding-004) |
| ベクトルDB | PostgreSQL 15+ with pgvector |
| フレームワーク | LangChain 0.3.0+, FastAPI, Streamlit |
| リランカー | BAAI/bge-reranker-base |
| インフラ | Google Cloud Platform (Cloud Run, Cloud SQL, Vertex AI) |
| IaC | Terraform |
| CI/CD | Cloud Build |

## プロジェクト構成

```
etude-rag2/
├── src/
│   ├── main.py                 # データ取り込みCLI
│   ├── config.py               # 設定管理
│   ├── api/                    # FastAPI REST API
│   │   ├── main.py
│   │   └── models.py
│   ├── chains/                 # 記事生成パイプライン
│   │   ├── article_chain.py    # メインオーケストレーター
│   │   ├── article_classifier.py
│   │   ├── input_parser.py
│   │   ├── outline_generator.py
│   │   ├── style_analyzer.py
│   │   ├── structure_analyzer.py
│   │   └── content_generators.py
│   ├── retriever/              # 検索システム
│   │   ├── hybrid_search.py    # ハイブリッド検索 + RRF
│   │   ├── reranker.py         # BGEリランキング
│   │   └── article_retriever.py
│   ├── ingestion/              # データ取り込み
│   │   └── drive_ingester.py   # Google Drive連携
│   ├── ui/                     # Streamlit UI
│   │   └── app.py
│   └── verification/           # 品質検証
│       ├── hallucination_detector.py
│       └── style_checker.py
├── schemas/
│   └── schema.sql              # DBスキーマ
├── tests/                      # テストスイート
├── terraform/                  # インフラ設定
├── Dockerfile                  # APIサーバー用
├── Dockerfile.streamlit        # UI用
├── Dockerfile.ingester         # データ取り込み用
└── cloudbuild.yaml             # CI/CD設定
```

## セットアップ

### 前提条件

- Python 3.12+
- PostgreSQL 15+ (pgvector, pg_trgm拡張)
- Google Cloud プロジェクト（Vertex AI API有効化済み）

### ローカル開発環境

```bash
# 1. 依存関係のインストール
uv sync

# 2. 環境変数の設定
cp .env.example .env
# .envファイルを編集

# 3. データベースのセットアップ
createdb rag_db
psql rag_db < schemas/schema.sql

# 4. データの取り込み
uv run python src/main.py --folder-id YOUR_FOLDER_ID
# または
uv run python src/main.py --local-file input.md --article-type ANNOUNCEMENT
```

### サービスの起動

```bash
# APIサーバー
uv run uvicorn src.api.main:app --reload --port 8000

# Streamlit UI
uv run streamlit run src/ui/app.py
```

- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- UI: http://localhost:8501

## API エンドポイント

| メソッド | パス | 説明 |
|---------|------|------|
| POST | `/generate` | 記事ドラフト生成 |
| POST | `/search` | ハイブリッド検索 |
| POST | `/verify` | ハルシネーション・スタイルチェック |
| GET | `/health` | ヘルスチェック |

## 環境変数

```env
# Google Cloud
GOOGLE_PROJECT_ID=your-project-id
GOOGLE_LOCATION=us-central1
SERVICE_ACCOUNT_FILE=/path/to/service-account.json

# Vertex AI
EMBEDDING_MODEL=text-embedding-004
LLM_MODEL=gemini-1.5-pro
LLM_TEMPERATURE=0.3

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=rag_db
DB_USER=postgres
DB_PASSWORD=your-password

# Hybrid Search Parameters
HYBRID_SEARCH_K=20
RRF_K=50
FINAL_K=10

# Reranker
RERANKER_MODEL=BAAI/bge-reranker-base
RERANKER_TOP_K=5

# Google Drive
TARGET_FOLDER_ID=your-folder-id

# Chunking
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
```

## テスト

```bash
# 全テスト実行
uv run pytest tests/ -v

# 特定のテストファイル
uv run pytest tests/test_retriever.py -v

# コード品質チェック
uv run ruff format .
uv run ruff check --fix .
uv run mypy src/
```

## クラウドデプロイ

### Terraform

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# terraform.tfvarsを編集

terraform init
terraform plan
terraform apply
```

### Cloud Build

```bash
# APIサーバーのビルド・デプロイ
gcloud builds submit --config cloudbuild.yaml

# Streamlit UIのビルド・デプロイ
gcloud builds submit --config cloudbuild-streamlit.yaml

# データ取り込みジョブのビルド
gcloud builds submit --config cloudbuild-ingester.yaml
```

## アーキテクチャ

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│ Streamlit   │────▶│  FastAPI    │────▶│  Cloud SQL      │
│    UI       │     │   Server    │     │  (PostgreSQL)   │
└─────────────┘     └──────┬──────┘     │  + pgvector     │
                           │            │  + pg_trgm      │
                           ▼            └─────────────────┘
                    ┌─────────────┐
                    │  Vertex AI  │
                    │  Gemini     │
                    └─────────────┘
```

### RAGパイプライン

```
入力素材 → ハイブリッド検索 → BGEリランキング → コンテキスト構築 → LLM生成 → 品質検証
```

## ドキュメント

- [RAGシステム設計書](docs/RAG_SYSTEM_BLUEPRINT.md)
- [実装計画](docs/IMPLEMENTATION_PLAN.md)
- [LangChainリファレンス](docs/LANGCHAIN_REFERENCES.md)

## ライセンス

Private
