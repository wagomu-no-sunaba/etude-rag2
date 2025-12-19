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
| LLM/Embeddings | Google Vertex AI (Gemini 2.0 Flash, text-embedding-004) |
| ベクトルDB | PostgreSQL 15+ with pgvector |
| フレームワーク | LangChain 0.3.0+, FastAPI, HTMX + Jinja2 |
| リランカー | BAAI/bge-reranker-v2-m3 |
| インフラ | Google Cloud Platform (Cloud Run, Cloud SQL, Vertex AI) |
| IaC | Terraform |
| CI/CD | Cloud Build |

## プロジェクト構成

```
etude-rag2/
├── src/
│   ├── main.py                 # データ取り込みCLI
│   ├── config.py               # 設定管理（Secret Manager統合）
│   ├── secret_manager.py       # Secret Managerヘルパー
│   ├── llm.py                  # LLM初期化・設定
│   ├── api/                    # FastAPI REST API
│   │   ├── main.py
│   │   ├── models.py
│   │   └── sse_models.py       # SSEストリーミング用モデル
│   ├── chains/                 # 記事生成パイプライン
│   │   ├── article_chain.py    # メインオーケストレーター
│   │   ├── article_classifier.py
│   │   ├── input_parser.py
│   │   ├── outline_generator.py
│   │   ├── style_analyzer.py
│   │   ├── structure_analyzer.py
│   │   ├── content_generators.py
│   │   ├── query_generator.py  # 検索クエリ生成（v3）
│   │   └── auto_rewrite.py     # 自動リライト（v3）
│   ├── retriever/              # 検索システム
│   │   ├── hybrid_search.py    # ハイブリッド検索 + RRF
│   │   ├── reranker.py         # BGEリランキング
│   │   ├── article_retriever.py
│   │   └── style_retriever.py  # スタイルプロファイル検索（v3）
│   ├── ingestion/              # データ取り込み
│   │   └── drive_ingester.py   # Google Drive連携
│   ├── templates/              # Jinja2テンプレート（HTMX UI）
│   │   ├── base.html           # ベーステンプレート
│   │   ├── index.html          # メインページ
│   │   └── partials/           # パーシャルテンプレート
│   │       ├── progress.html   # SSE進捗表示
│   │       └── result.html     # 生成結果表示
│   ├── static/                 # 静的ファイル
│   │   └── css/style.css       # カスタムCSS
│   ├── ui/                     # Streamlit UI（非推奨・削除予定）
│   │   ├── app.py
│   │   ├── api_client.py
│   │   ├── state.py
│   │   └── utils.py
│   └── verification/           # 品質検証
│       ├── hallucination_detector.py
│       └── style_checker.py
├── schemas/
│   └── schema.sql              # DBスキーマ
├── tests/                      # テストスイート
├── terraform/                  # インフラ設定
├── scripts/
│   └── sync-env-from-secrets.sh # Secret Manager → .env 生成
├── Dockerfile                  # APIサーバー用（HTMX UI含む）
├── Dockerfile.streamlit        # Streamlit UI用（非推奨・削除予定）
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

# 2. 環境変数の設定（2つの方法）

# 方法A: Secret Managerから自動生成（推奨）
./scripts/sync-env-from-secrets.sh dev

# 方法B: 手動設定
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
# APIサーバー（HTMX UI含む）
uv run uvicorn src.api.main:app --reload --port 8000
```

- **Web UI**: http://localhost:8000 （HTMX + SSEストリーミング）
- **API Docs**: http://localhost:8000/docs

> **Note**: Streamlit UI（`uv run streamlit run src/ui/app.py`）は非推奨・削除予定です。

## API エンドポイント

### Web UI

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/` | メインページ（記事生成フォーム） |
| POST | `/ui/generate` | 記事生成（HTMLパーシャル返却） |
| POST | `/ui/generate/stream` | 記事生成（SSE進捗表示用） |

### REST API

| メソッド | パス | 説明 |
|---------|------|------|
| POST | `/generate` | 記事ドラフト生成 |
| POST | `/generate/stream` | 記事ドラフト生成（SSEストリーミング） |
| POST | `/search` | ハイブリッド検索 |
| POST | `/verify` | ハルシネーション・スタイルチェック |
| GET | `/health` | ヘルスチェック |

## 設定管理

本プロジェクトは **Google Cloud Secret Manager** を設定の Single Source of Truth として使用します。

### 設定の優先順位

1. **環境変数**（最高優先、Cloud Run での注入用）
2. **Secret Manager**（シークレット値）
3. **.env ファイル**（ローカル開発のフォールバック）

### Secret Manager で管理される設定

| シークレットID | 説明 |
|---------------|------|
| `etude-rag2-db-password-{env}` | データベースパスワード |
| `etude-rag2-drive-folder-id-{env}` | Google Drive フォルダID |
| `etude-rag2-my-email-{env}` | ACLフィルタリング用メール |
| `etude-rag2-service-account-key-{env}` | サービスアカウントキー |
| `etude-rag2-app-config-{env}` | アプリ設定（JSON） |

### ローカル開発での設定

```bash
# Secret Manager から .env を自動生成（推奨）
./scripts/sync-env-from-secrets.sh dev

# または最小限の設定で Secret Manager を直接参照
export GOOGLE_PROJECT_ID=your-project-id
export ENVIRONMENT=dev
# → config.py が自動で Secret Manager から取得
```

### 環境変数一覧

```env
# Google Cloud（必須）
GOOGLE_PROJECT_ID=your-project-id
GOOGLE_LOCATION=us-central1
ENVIRONMENT=dev

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=rag_db
DB_USER=postgres
DB_PASSWORD=  # Secret Manager から自動取得

# Google Drive
TARGET_FOLDER_ID=  # Secret Manager から自動取得

# Vertex AI（デフォルト値あり）
EMBEDDING_MODEL=text-embedding-004
LLM_MODEL=gemini-2.0-flash
LLM_MODEL_LITE=gemini-2.0-flash-lite
LLM_TEMPERATURE=0.3

# Hybrid Search Parameters
HYBRID_SEARCH_K=20
RRF_K=50
FINAL_K=10

# Reranker
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
RERANKER_TOP_K=5
USE_FP16=true

# Feature Flags（v3機能）
USE_LITE_MODEL=true        # 軽量タスクにflash-liteを使用
USE_QUERY_GENERATOR=true   # クエリ生成チェーンを有効化
USE_STYLE_PROFILE_KB=true  # スタイルプロファイルKBを有効化
USE_AUTO_REWRITE=true      # 自動リライト機能を有効化
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

### 1. GCPプロジェクトの作成

```bash
# セットアップスクリプトでプロジェクト作成（推奨）
./scripts/setup-gcp-project.sh YOUR_PROJECT_ID [BILLING_ACCOUNT_ID]
```

### 2. Terraform

```bash
cd terraform
# setup-gcp-project.sh が terraform.tfvars を生成済み
# 必要に応じて編集

terraform init
terraform plan
terraform apply
```

### Cloud Build

```bash
# APIサーバーのビルド・デプロイ（HTMX UI含む）
gcloud builds submit --config cloudbuild.yaml

# データ取り込みジョブのビルド
gcloud builds submit --config cloudbuild-ingester.yaml

# Streamlit UIのビルド・デプロイ（非推奨・削除予定）
# gcloud builds submit --config cloudbuild-streamlit.yaml
```

## アーキテクチャ

```
┌─────────────┐     ┌───────────────────┐     ┌─────────────────┐
│   Browser   │────▶│     FastAPI       │────▶│  Cloud SQL      │
│  (HTMX UI)  │     │  (API + Web UI)   │     │  (PostgreSQL)   │
└─────────────┘     │  + Jinja2         │     │  + pgvector     │
      │             │  + SSE Streaming  │     │  + pg_trgm      │
      │ SSE         └────────┬──────────┘     └─────────────────┘
      ▼                      │
 リアルタイム                 ▼
 進捗表示             ┌─────────────┐
                     │  Vertex AI  │
                     │  Gemini 2.0 │
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
