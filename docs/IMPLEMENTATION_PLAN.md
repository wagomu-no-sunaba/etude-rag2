# note記事ドラフト生成RAGシステム 実装計画書

## 1. 概要

株式会社ギグーの採用広報note記事ドラフト生成システムを、LangChain + Vertex AI + Cloud SQLベースで完全Python実装する。

**実装優先順位**: 検索層 → 生成層 → 検証層 → API/UI

## 2. システム要件

### 2.1 機能要件（Difyワークフローv2準拠）

| # | 機能 | 説明 |
|---|------|------|
| 1 | 記事タイプ別ナレッジベース | アナウンスメント、イベントレポート、インタビュー、カルチャーの4種類 |
| 2 | 入力素材の構造化 | ユーザー入力からテーマ、キーポイント、引用等を抽出 |
| 3 | ハイブリッド検索 | ベクトル検索 + 全文検索をRRFで融合 |
| 4 | リランキング | BGEクロスエンコーダによる関連度再評価 |
| 5 | 文体・構成分析 | 過去記事から文体特徴と構成パターンを抽出 |
| 6 | 記事生成 | タイトル/リード/本文/締めの各パーツを生成 |
| 7 | ハルシネーション検知 | 入力素材にない情報を検出し[要確認]タグ挿入 |

### 2.2 非機能要件

| 項目 | 仕様 |
|------|------|
| デプロイ先 | GCP（Cloud Run + Cloud SQL + Vertex AI） |
| LLM | Vertex AI Gemini 1.5 Pro |
| Embeddings | Vertex AI text-embedding-004（768次元） |
| データソース | Google Drive（Markdown/JSONL） |
| Python | >= 3.12 |

## 3. アーキテクチャ

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           note記事ドラフト生成RAG                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────┐    ┌──────────┐ │
│  │  FastAPI    │    │   検索層     │    │   生成層      │    │  検証層  │ │
│  │  REST API   │───▶│ HybridSearch │───▶│ ArticleChain  │───▶│ Verifier │ │
│  │  Streamlit  │    │ BGEReranker  │    │ Gemini 1.5 Pro│    │ (Gemini) │ │
│  └─────────────┘    └──────────────┘    └───────────────┘    └──────────┘ │
│         │                  │                                               │
│         │                  ▼                                               │
│         │          ┌──────────────┐                                       │
│         │          │   Cloud SQL  │                                       │
│         │          │  PostgreSQL  │                                       │
│         │          │ pgvector/trgm│                                       │
│         │          └──────────────┘                                       │
│         │                  │                                               │
│         ▼                  ▼                                               │
│  ┌─────────────────────────────────────┐                                  │
│  │           Vertex AI                  │                                  │
│  │  - Gemini 1.5 Pro（生成）            │                                  │
│  │  - text-embedding-004（Embeddings）  │                                  │
│  └─────────────────────────────────────┘                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 4. ディレクトリ構成

```
src/
├── main.py                    # データ取り込みエントリポイント
├── config.py                  # 設定管理（Pydantic Settings）
├── api/                       # FastAPI REST API + Web UI
│   ├── main.py                # アプリケーション
│   ├── models.py              # リクエスト/レスポンスモデル
│   └── sse_models.py          # SSEイベントモデル
├── templates/                 # Jinja2テンプレート（HTMX UI）
│   ├── base.html              # ベーステンプレート
│   ├── index.html             # メインページ
│   └── partials/              # パーシャルテンプレート
│       ├── progress.html      # SSE進捗表示
│       └── result.html        # 生成結果表示
├── static/                    # 静的ファイル
│   └── css/style.css          # カスタムCSS
├── ui/                        # Streamlit UI（非推奨・削除予定）
│   ├── app.py
│   └── ...
├── models/
│   ├── __init__.py
│   ├── document.py            # Documentモデル
│   └── article.py             # ArticleType, ParsedInput等
├── retriever/
│   ├── __init__.py
│   ├── hybrid_search.py       # ハイブリッド検索（RRF融合）
│   ├── reranker.py            # BGEリランカー
│   └── article_retriever.py   # 記事タイプ別検索
├── chains/
│   ├── __init__.py
│   ├── input_parser.py        # 入力素材構造化
│   ├── article_classifier.py  # 記事タイプ分類
│   ├── style_analyzer.py      # 文体分析
│   ├── structure_analyzer.py  # 構成分析
│   ├── outline_generator.py   # アウトライン生成
│   ├── title_generator.py     # タイトル生成
│   ├── lead_generator.py      # リード文生成
│   ├── section_generator.py   # セクション本文生成
│   ├── closing_generator.py   # 締め生成
│   └── article_chain.py       # 全体オーケストレーション
├── verification/
│   ├── __init__.py
│   ├── style_checker.py       # 文体検証
│   └── hallucination_detector.py  # ハルシネーション検知
├── utils/
│   ├── __init__.py
│   ├── db.py                  # データベース接続
│   └── prompts.py             # プロンプトテンプレート
└── ingestion/
    ├── __init__.py
    └── drive_ingester.py      # Google Driveデータ取り込み
schemas/
└── schema.sql                 # データベーススキーマ
tests/
├── test_retriever.py
├── test_chains.py
└── test_verification.py
```

## 5. 実装フェーズ

### Phase 1: 検索層（優先実装）

#### 5.1.1 データベーススキーマ

**ファイル**: `schemas/schema.sql`

- pgvector拡張（ベクトル検索）
- pg_trgm拡張（全文検索）
- article_type ENUM（4種類の記事タイプ）
- documentsテーブル（embedding vector(768)）
- RRF関数（rrf_score）

#### 5.1.2 設定管理

**ファイル**: `src/config.py`

```python
class Settings(BaseSettings):
    # Google Cloud
    google_project_id: str
    google_location: str = "us-central1"

    # Vertex AI
    embedding_model: str = "text-embedding-004"
    llm_model: str = "gemini-1.5-pro"

    # Database
    db_host: str
    db_name: str
    db_user: str
    db_password: str

    # 検索パラメータ
    hybrid_search_k: int = 20
    rrf_k: int = 50
    final_k: int = 10

    # リランカー
    reranker_model: str = "BAAI/bge-reranker-base"
    reranker_top_k: int = 5
```

#### 5.1.3 ハイブリッド検索

**ファイル**: `src/retriever/hybrid_search.py`

```python
class HybridSearcher:
    def search(query, article_type=None, k=20) -> list[Document]:
        # 1. ベクトル検索 (embedding <-> query_vector)
        # 2. 全文検索 (pg_trgm similarity)
        # 3. RRF融合 (rrf_score関数)
        # 4. 記事タイプフィルタリング
```

**検索SQL**:
```sql
WITH vector_search AS (
    SELECT id, content, metadata, article_type,
           ROW_NUMBER() OVER (ORDER BY embedding <-> query_vector) as rank
    FROM documents WHERE article_type = ?
),
fulltext_search AS (
    SELECT id, content, metadata, article_type,
           ROW_NUMBER() OVER (ORDER BY similarity(content, query) DESC) as rank
    FROM documents WHERE similarity(content, query) > 0.1
),
combined AS (
    SELECT *, rrf_score(rank, 50) as score FROM vector_search
    UNION ALL
    SELECT *, rrf_score(rank, 50) as score FROM fulltext_search
)
SELECT id, content, metadata, SUM(score) as total_score
FROM combined GROUP BY id ORDER BY total_score DESC LIMIT 10
```

#### 5.1.4 BGEリランカー

**ファイル**: `src/retriever/reranker.py`

```python
class BGEReranker:
    def __init__(self, model="BAAI/bge-reranker-base", use_fp16=True):
        self.reranker = FlagReranker(model, use_fp16=use_fp16)

    def rerank(query, documents, top_k=5) -> list[Document]:
        # 1. クエリ-ドキュメントペア作成
        # 2. クロスエンコーダスコア計算
        # 3. Sigmoid正規化
        # 4. Top-K選別
```

#### 5.1.5 記事タイプ別検索

**ファイル**: `src/retriever/article_retriever.py`

```python
class ArticleRetriever:
    def retrieve(query, article_type=None, use_reranker=True):
        # 1. ハイブリッド検索
        # 2. リランキング（オプション）

    def retrieve_multi_query(queries, article_type=None):
        # 1. 複数クエリで検索
        # 2. 重複排除
        # 3. まとめてリランキング
```

#### 5.1.6 データ取り込み

**ファイル**: `src/ingestion/drive_ingester.py`

```python
class DriveIngester:
    def ingest_folder(folder_id):
        # 1. Google Drive APIでファイル一覧取得
        # 2. ファイルごとに処理

    def process_file(file_item):
        # 1. コンテンツ取得
        # 2. 記事タイプ判定（ファイル名/フォルダ名から推定）
        # 3. チャンク分割（RecursiveCharacterTextSplitter）
        # 4. Embedding生成（Vertex AI）
        # 5. DB挿入
```

### Phase 2: 生成層（後続実装）

| コンポーネント | ファイル | 説明 |
|--------------|---------|------|
| 入力素材構造化 | `chains/input_parser.py` | テーマ、キーポイント、引用等を抽出 |
| 記事タイプ分類 | `chains/article_classifier.py` | 4カテゴリに分類 |
| 文体分析 | `chains/style_analyzer.py` | 語尾パターン、トーン、特徴的フレーズ |
| 構成分析 | `chains/structure_analyzer.py` | 見出しパターン、リード/締めパターン |
| アウトライン生成 | `chains/outline_generator.py` | 見出し構成と概要 |
| タイトル生成 | `chains/title_generator.py` | 3案生成 |
| リード文生成 | `chains/lead_generator.py` | 100-150字 |
| セクション生成 | `chains/section_generator.py` | 各見出しの本文 |
| 締め生成 | `chains/closing_generator.py` | CTA含む締め |
| 全体オーケストレーション | `chains/article_chain.py` | パイプライン統合 |

### Phase 3: 検証層（後続実装）

| コンポーネント | ファイル | 説明 |
|--------------|---------|------|
| 文体検証 | `verification/style_checker.py` | 一貫性スコア、修正提案 |
| ハルシネーション検知 | `verification/hallucination_detector.py` | 未確認事実の検出、[要確認]タグ候補 |

### Phase 4: API・UI（後続実装）

| コンポーネント | ファイル | 説明 |
|--------------|---------|------|
| REST API | `api/main.py` | FastAPIエンドポイント |
| Web UI（メイン） | `templates/` | HTMX + Jinja2（SSEストリーミング対応） |
| Web UI（非推奨） | `ui/app.py` | Streamlit（削除予定） |

### Phase 5: デプロイ（後続実装）

| コンポーネント | ファイル | 説明 |
|--------------|---------|------|
| コンテナ | `Dockerfile`, `Dockerfile.base` | APIサーバー用 |
| インフラ | `terraform/*.tf` | Cloud Run, Cloud SQL |
| CI/CD | `cloudbuild.yaml` | Cloud Build |

## 6. 技術スタック

| カテゴリ | パッケージ | バージョン | 用途 |
|---------|-----------|----------|------|
| LangChain | langchain | >=0.3.0 | コア機能 |
| LangChain | langchain-google-vertexai | >=2.0.7 | Vertex AI連携 |
| LangChain | langchain-postgres | >=0.0.12 | pgvector連携 |
| DB | psycopg2-binary | >=2.9.10 | PostgreSQL接続 |
| DB | pgvector | >=0.3.6 | ベクトル検索 |
| ML | FlagEmbedding | >=1.2.11 | BGEリランカー |
| ML | sentence-transformers | >=3.0.0 | モデル基盤 |
| API | fastapi | >=0.115.0 | REST API |
| API | uvicorn | >=0.31.0 | ASGIサーバー |
| UI | streamlit | >=1.39.0 | Web UI |
| GCP | google-api-python-client | >=2.149.0 | Drive API |

## 7. 検索パイプライン詳細

```
1. クエリ入力
   ↓
2. クエリ書き換え（オプション）
   - 元クエリ + 3つの変形クエリを生成
   - 各クエリで検索 → マージ
   ↓
3. ハイブリッド検索
   ├── ベクトル検索（pgvector <-> 演算子）
   │   └── コサイン類似度でランキング
   └── 全文検索（pg_trgm）
       └── トライグラム類似度でランキング
   ↓
4. RRF融合
   - 各検索結果のランクからスコア計算
   - 1 / (rank + k) で統合
   ↓
5. 記事タイプフィルタリング
   - article_type = 指定タイプ
   ↓
6. BGEリランキング
   - クロスエンコーダで(query, doc)ペアをスコアリング
   - Sigmoid正規化
   - Top-K選別
   ↓
7. 結果返却
```

## 8. パラメータチューニング

| パラメータ | デフォルト値 | 説明 | 調整指針 |
|-----------|-------------|------|---------|
| `hybrid_search_k` | 20 | 各検索からの取得数 | 精度重視なら増加 |
| `rrf_k` | 50 | RRFのk値 | 高いほど順位差の影響小 |
| `final_k` | 10 | RRF後の取得数 | 必要なコンテキスト量に応じて |
| `reranker_top_k` | 5 | リランキング後の返却数 | LLMコンテキスト長に応じて |
| `chunk_size` | 1000 | チャンクサイズ | 記事の粒度に応じて |
| `chunk_overlap` | 200 | チャンク重複 | 文脈保持のため |

## 9. 環境変数

```bash
# .env ファイル例

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

# 検索パラメータ
HYBRID_SEARCH_K=20
RRF_K=50
FINAL_K=10

# リランカー
RERANKER_MODEL=BAAI/bge-reranker-base
RERANKER_TOP_K=5
USE_FP16=true

# Google Drive
TARGET_FOLDER_ID=your-folder-id
```

## 10. ローカル開発セットアップ

```bash
# 1. 依存関係インストール
uv sync

# 2. PostgreSQL + pgvector起動（Docker）
docker run -d \
  --name pgvector \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 \
  pgvector/pgvector:pg16

# 3. スキーマ適用
psql -h localhost -U postgres -d rag_db -f schemas/schema.sql

# 4. 環境変数設定
cp .env.example .env
# .envを編集

# 5. データ取り込み
uv run python -m src.main

# 6. APIサーバー起動
uv run uvicorn src.api_server:app --reload
```

## 11. 次のステップ

1. **Phase 1完了後**: サンプルデータでの検索精度評価
2. **Phase 2**: 生成層の実装（Gemini 1.5 Pro + Structured Output）
3. **Phase 3**: 検証層の実装（ハルシネーション検知）
4. **Phase 4**: API/UIの実装
5. **Phase 5**: GCPデプロイ（Terraform）
