# RAGシステム構築ブループリント

LangChainベースのRAG（Retrieval-Augmented Generation）システムを構築するためのリファレンスドキュメント。

## 目次

1. [システム概要](#システム概要)
2. [アーキテクチャ](#アーキテクチャ)
3. [技術スタック](#技術スタック)
4. [コンポーネント詳細](#コンポーネント詳細)
5. [データベース設計](#データベース設計)
6. [検索パイプライン](#検索パイプライン)
7. [LLM統合](#llm統合)
8. [セキュリティ（ACL制御）](#セキュリティacl制御)
9. [デプロイメント](#デプロイメント)
10. [パフォーマンス最適化](#パフォーマンス最適化)

---

## システム概要

### 機能一覧

| 機能 | 説明 |
|------|------|
| データ取り込み | Google DriveからMarkdown/JSONLファイルを取得・ベクトル化 |
| ハイブリッド検索 | ベクトル検索 + 全文検索をRRFで融合 |
| リランキング | BGEクロスエンコーダによる関連度再評価 |
| FAQ回答生成 | 短文回答（400字以内）の生成 |
| ブログドラフト生成 | 長文記事の生成 |
| ACL制御 | ユーザーのアクセス権限に基づくフィルタリング |
| 評価機能 | 生成品質の自動評価（関連性・忠実性・読みやすさ） |

### データフロー

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         データ取り込みパイプライン                        │
├─────────────────────────────────────────────────────────────────────────┤
│  Google Drive API    →    ファイル処理    →    Vertex AI    →    PostgreSQL │
│  (OAuth認証)              (Markdown/JSONL)      (Embeddings)      (pgvector)   │
│  ↓                        ↓                    ↓                ↓          │
│  ACL取得                  チャンク分割          768次元ベクトル    documents表  │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                           検索・生成パイプライン                          │
├─────────────────────────────────────────────────────────────────────────┤
│  ユーザークエリ → ハイブリッド検索 → リランキング → コンテキスト圧縮 → LLM生成 │
│       ↓              ↓                ↓              ↓              ↓     │
│  クエリ書き換え    RRF融合          BGE Reranker    トークン最適化    回答出力  │
│  (オプション)     (Vector+FTS)     (Top-K選別)     (3Bモデル対応)   (出典付き) │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## アーキテクチャ

### ディレクトリ構成

```
project-root/
├── src/                          # アプリケーションコード
│   ├── main.py                   # データ取り込みエントリポイント
│   ├── config.py                 # 設定管理（Pydantic Settings）
│   ├── api/                      # FastAPI REST API + Web UI
│   │   ├── main.py               # アプリケーション
│   │   ├── models.py             # リクエスト/レスポンスモデル
│   │   └── sse_models.py         # SSEイベントモデル
│   ├── templates/                # Jinja2テンプレート（HTMX UI）
│   │   ├── base.html             # ベーステンプレート
│   │   ├── index.html            # メインページ
│   │   └── partials/             # パーシャルテンプレート
│   │       ├── progress.html     # SSE進捗表示
│   │       └── result.html       # 生成結果表示
│   ├── static/                   # 静的ファイル
│   │   └── css/style.css         # カスタムCSS
│   ├── ui/                       # Streamlit UI（非推奨・削除予定）
│   ├── retriever/                # 検索システム
│   ├── chains/                   # 記事生成パイプライン
│   ├── verification/             # 品質検証
│   └── ingestion/                # データ取り込み
├── schemas/
│   └── schema.sql                # データベーススキーマ
├── terraform/                    # インフラ定義（IaC）
│   ├── main.tf
│   ├── cloud_run.tf
│   ├── cloudsql.tf
│   └── variables.tf
├── Dockerfile                    # APIサーバー用（HTMX UI含む）
├── Dockerfile.base               # 依存関係プリビルド
├── Dockerfile.ingester           # データ取り込みジョブ用
├── Dockerfile.streamlit          # Streamlit UI用（非推奨・削除予定）
├── cloudbuild.yaml               # CI/CD設定
├── pyproject.toml                # Python依存関係
└── tests/                        # テストコード
```

### GCPインフラ構成

```
┌──────────────────────────────────────────────────────────────────┐
│                        Google Cloud Platform                      │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐    ┌─────────────────┐    ┌──────────────┐ │
│  │   Cloud Run     │    │   Cloud Run     │    │  Cloud Run   │ │
│  │   (API Server)  │    │   (Streamlit)   │    │    Job       │ │
│  │  + HTMX Web UI  │    │  非推奨・削除予定 │    │  (Ingester)  │ │
│  └────────┬────────┘    └────────┬────────┘    └──────┬───────┘ │
│           │                      │                    │         │
│           └──────────┬───────────┴────────────────────┘         │
│                      │                                          │
│                      ▼                                          │
│           ┌──────────────────┐                                  │
│           │    Cloud SQL     │                                  │
│           │   (PostgreSQL)   │                                  │
│           │  pgvector/pg_trgm│                                  │
│           └──────────────────┘                                  │
│                      │                                          │
│                      │ Unix Socket                              │
│                      ▼                                          │
│           ┌──────────────────┐         ┌──────────────────┐    │
│           │  Compute Engine  │         │ Artifact Registry │    │
│           │  (Ollama Server) │         │  (Docker Images)  │    │
│           │   qwen2.5:3b     │         │                   │    │
│           └──────────────────┘         └──────────────────┘    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 技術スタック

### Python環境

```toml
# pyproject.toml
[project]
requires-python = ">=3.12"

[tool.uv]
# uvによる高速パッケージ管理
```

### 主要依存関係

| カテゴリ | パッケージ | 用途 |
|---------|-----------|------|
| **LangChain** | `langchain>=0.3.0` | コア機能 |
| | `langchain-postgres>=0.0.12` | PGVector統合 |
| | `langchain-google-vertexai>=2.0` | Embeddings |
| | `langchain-ollama>=0.2.0` | ローカルLLM |
| **データベース** | `psycopg2-binary` | PostgreSQL接続 |
| | `pgvector` | ベクトル検索 |
| **ML** | `FlagEmbedding>=1.2.11` | BGEリランカー |
| | `sentence-transformers>=3.0` | モデル基盤 |
| **API** | `fastapi>=0.115.0` | REST API |
| | `uvicorn[standard]>=0.31.0` | ASGIサーバー |
| **UI** | `streamlit>=1.39.0` | Web UI |
| **評価** | `ragas>=0.1.19` | RAG評価 |

### コード品質

```bash
# Ruff（リンター・フォーマッター）
uv run ruff format .
uv run ruff check --fix .
```

---

## コンポーネント詳細

### 1. 設定管理 (`config.py`)

Pydantic Settingsによる型安全な設定管理:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Google Cloud
    service_account_file: str
    target_folder_id: str
    google_project_id: str
    embedding_model: str = "text-embedding-004"

    # Database
    db_host: str  # /cloudsql/{connection_name} でUnix Socket対応
    db_name: str
    db_user: str
    db_password: str
    db_port: int = 5432

    # 検索チューニング
    hybrid_search_k: int = 10
    rrf_k: int = 50
    reranker_model: str = "BAAI/bge-reranker-base"
    reranker_top_k: int = 5

    # LLM
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"
    llm_temperature: float = 0.7

    # 機能フラグ
    query_rewrite_enabled: bool = True
    context_compression_enabled: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"

    @property
    def db_connection_string(self) -> str:
        """Cloud SQL Unix Socket対応"""
        if self.db_host.startswith("/"):
            return f"postgresql://{self.db_user}:{self.db_password}@/{self.db_name}?host={self.db_host}"
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def db_connection_string_psycopg(self) -> str:
        """LangChain PGVector用（psycopgドライバ）"""
        # postgresql+psycopg://... 形式
        ...

settings = Settings()
```

### 2. データ取り込み (`main.py`)

Google Driveからのデータ取得とベクトル化:

```python
class DriveIngester:
    def process_file(self, file_item, allowed_principals: list[str]):
        file_name = file_item["name"]

        if file_name.endswith(".md"):
            # Markdownはチャンク分割
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                separators=["\n\n", "\n", "。", ".", " ", ""]
            )
            chunks = splitter.split_text(content)
            return [
                Document(
                    page_content=chunk,
                    metadata={
                        "source": file_name,
                        "file_id": file_id,
                        "chunk_index": i,
                        "total_chunks": len(chunks)
                    }
                )
                for i, chunk in enumerate(chunks)
            ]

        elif file_name.endswith(".jsonl"):
            # JSONLは1行=1ドキュメント
            documents = []
            for line in content.splitlines():
                data = json.loads(line)
                text = data.get("text") or data.get("content") or json.dumps(data)
                documents.append(Document(page_content=text, metadata=data))
            return documents

    def insert_documents(self, documents: list[Document]):
        # バッチでEmbedding生成（効率的）
        vectors = self.embeddings.embed_documents(
            [doc.page_content for doc in documents]
        )

        for doc, vector in zip(documents, vectors):
            cursor.execute("""
                INSERT INTO documents (content, embedding, allowed_principals, metadata)
                VALUES (%s, %s, %s, %s)
            """, (doc.page_content, vector, doc.allowed_principals, json.dumps(doc.metadata)))

        conn.commit()
```

### 3. ハイブリッド検索 (`hybrid_search.py`)

ベクトル検索と全文検索をRRFで融合:

```python
class HybridSearcher:
    def search(
        self,
        query: str,
        user_email: str | None = None,
        k: int = 10,
        boost_tags: list[str] | None = None
    ) -> list[Document]:
        # 1. クエリをベクトル化
        query_vector = self.embeddings.embed_query(query)

        # 2. ハイブリッド検索SQL実行
        sql = """
        SELECT id, content, metadata, allowed_principals, SUM(rrf_score) AS score
        FROM (
            -- ベクトル検索
            SELECT id, content, metadata, allowed_principals,
                   rrf_score(rank() OVER (ORDER BY embedding <-> %s), %s) AS rrf_score
            FROM documents
            WHERE allowed_principals LIKE %s
            ORDER BY embedding <-> %s
            LIMIT %s

            UNION ALL

            -- 全文検索（pg_trgm）
            SELECT id, content, metadata, allowed_principals,
                   rrf_score(rank() OVER (ORDER BY similarity(content, %s) DESC), %s) AS rrf_score
            FROM documents
            WHERE allowed_principals LIKE %s
              AND similarity(content, %s) > 0.1
            LIMIT %s
        ) AS combined
        GROUP BY id, content, metadata, allowed_principals
        ORDER BY score DESC
        LIMIT %s
        """

        acl_filter = f"%{user_email}%" if user_email else "%"
        results = cursor.execute(sql, params)

        # 3. タグブースト適用（オプション）
        if boost_tags:
            results = self._apply_tag_boost(results, boost_tags, boost_value=0.1)

        return results
```

**RRFスコア計算（PostgreSQL関数）**:

```sql
CREATE FUNCTION rrf_score(rank bigint, rrf_k int DEFAULT 50)
  RETURNS numeric AS $$
  SELECT COALESCE(1.0 / ($1 + $2), 0.0);
$$ LANGUAGE SQL IMMUTABLE PARALLEL SAFE;
```

### 4. リランキング (`reranker.py`)

BGEクロスエンコーダによる関連度再評価:

```python
from FlagEmbedding import FlagReranker

class BGEReranker:
    def __init__(self, model_name: str = "BAAI/bge-reranker-base", use_fp16: bool = True):
        # 初回はHugging Face Hubからダウンロード
        self.reranker = FlagReranker(model_name, use_fp16=use_fp16)

    def rerank(
        self,
        query: str,
        documents: list[Document],
        top_k: int = 5
    ) -> list[Document]:
        # クエリ-ドキュメントペアを作成
        pairs = [[query, doc.page_content] for doc in documents]

        # スコア計算（-5〜+5の範囲）
        scores = self.reranker.compute_score(pairs)

        # Sigmoid正規化（0〜1の範囲に変換）
        normalized = [1 / (1 + math.exp(-s)) for s in scores]

        # スコア順にソート
        scored_docs = sorted(
            zip(scores, normalized, documents),
            key=lambda x: x[0],
            reverse=True
        )

        # メタデータにスコアを追加
        result = []
        for score, norm, doc in scored_docs[:top_k]:
            doc.metadata["rerank_score"] = score
            doc.metadata["rerank_score_normalized"] = norm
            result.append(doc)

        return result

# Graceful Degradation
def get_reranker() -> BGEReranker | None:
    try:
        return BGEReranker()
    except Exception as e:
        logger.warning(f"Reranker初期化失敗: {e}")
        return None  # Noneの場合はリランキングをスキップ
```

### 5. FAQ回答生成 (`faq_chain.py`)

3Bモデル向けに最適化されたRAGチェーン:

```python
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate

class FAQAnswerChain:
    def __init__(self):
        self.llm = ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            temperature=settings.llm_temperature
        )

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """あなたは社内サポート担当です。

【回答方針】
- コンテキスト情報のみに基づいて回答
- 日本語で400字以内に簡潔にまとめる
- 情報がない場合は「見つかりません」と明記
- 推測や一般論は避ける

【出典ルール】
- 情報を述べた直後に [1], [2] と番号を付与
- 最後に「参照元:」セクションを追加"""),
            ("human", """【質問】
{query}

【参照情報】
{context}

上記に基づいて回答してください。""")
        ])

        self.chain = self.prompt | self.llm | StrOutputParser()

    def generate_answer(
        self,
        query: str,
        user_email: str | None = None,
        retrieval_k: int = 10,
        rerank_top_k: int = 3
    ) -> dict:
        # 1. ドキュメント検索
        documents = self.searcher.search(query, user_email, k=retrieval_k)

        # 2. リランキング（オプション）
        if self.reranker:
            documents = self.reranker.rerank(query, documents, top_k=rerank_top_k)

        # 3. コンテキスト圧縮（3Bモデル用）
        context = self._compress_context(documents, max_chars=800)

        # 4. 回答生成
        answer = self.chain.invoke({"query": query, "context": context})

        return {
            "answer": answer,
            "sources": [doc.metadata for doc in documents],
            "context_found": bool(documents)
        }

    def _compress_context(self, documents: list[Document], max_chars: int) -> str:
        """3Bモデルのコンテキストウィンドウに収める"""
        context_parts = []
        current_length = 0

        for i, doc in enumerate(documents):
            text = f"[資料{i+1}: {doc.metadata.get('source', '不明')}]\n{doc.page_content}"
            if current_length + len(text) > max_chars:
                # 文の区切りで切る
                remaining = max_chars - current_length
                text = text[:remaining].rsplit("。", 1)[0] + "。"
            context_parts.append(text)
            current_length += len(text)
            if current_length >= max_chars:
                break

        return "\n---\n".join(context_parts)
```

### 6. REST API (`api_server.py`)

FastAPIによるエンドポイント提供:

```python
from fastapi import FastAPI, HTTPException

app = FastAPI(title="RAG API")

# シングルトンパターン
_reranker: BGEReranker | None = None
_faq_chain: FAQAnswerChain | None = None

def get_reranker() -> BGEReranker | None:
    global _reranker
    if _reranker is None:
        try:
            _reranker = BGEReranker()
        except Exception as e:
            logger.warning(f"Reranker初期化失敗: {e}")
    return _reranker

@app.post("/search")
async def search(request: SearchRequest):
    """ハイブリッド検索（リランキング対応）"""
    results = get_hybrid_searcher().search(
        query=request.query,
        user_email=request.user_email,
        k=request.k
    )

    if request.use_reranker and (reranker := get_reranker()):
        results = reranker.rerank(request.query, results, top_k=request.rerank_top_k)

    return {"documents": [doc.dict() for doc in results]}

@app.post("/faq/answer")
async def faq_answer(request: FAQRequest):
    """FAQ回答生成"""
    chain = get_faq_chain()
    result = chain.generate_answer(
        query=request.query,
        user_email=request.user_email
    )
    return result

@app.get("/health")
async def health():
    """ヘルスチェック"""
    return {"status": "healthy"}
```

### 7. Web UI（HTMX + Jinja2）

FastAPI + Jinja2 + HTMXベースの軽量Web UI（SSEストリーミング対応）:

```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html lang="ja">
<head>
    <script src="https://unpkg.com/htmx.org@2.0.4"></script>
    <script src="https://unpkg.com/htmx-ext-sse@2.2.2/sse.js"></script>
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>{% block content %}{% endblock %}</body>
</html>

<!-- templates/index.html -->
<form hx-post="/ui/generate/stream" hx-target="#result" hx-swap="innerHTML">
    <select name="article_type">
        <option value="auto">自動判定</option>
        <option value="ANNOUNCEMENT">お知らせ</option>
        <!-- ... -->
    </select>
    <textarea name="input_material" rows="10" required></textarea>
    <button type="submit">生成</button>
</form>
<div id="result"></div>

<!-- templates/partials/progress.html -->
<div hx-ext="sse" sse-connect="/generate/stream" sse-swap="progress,complete,error">
    <progress value="{{ percentage }}" max="100"></progress>
    <span>{{ step_name }}</span>
</div>
```

**技術スタック:**
- HTMX 2.0.4 + SSE Extension 2.2.2
- Jinja2テンプレートエンジン
- Server-Sent Events（リアルタイム進捗表示）

### 7.1 Streamlit UI（非推奨・削除予定）

> **Warning**: Streamlit UIは非推奨です。新しいHTMX UIをご利用ください。

```python
# src/ui/app.py - 非推奨・削除予定
import streamlit as st
# ...
```

---

## データベース設計

### スキーマ定義

```sql
-- 拡張機能
CREATE EXTENSION IF NOT EXISTS vector;    -- pgvector
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- 全文検索

-- ドキュメントテーブル
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    embedding vector(768),                 -- Vertex AI Embeddings
    allowed_principals TEXT,               -- ACL: 'email1,email2' 形式
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- インデックス
CREATE INDEX idx_embedding ON documents USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_content_trgm ON documents USING gin (content gin_trgm_ops);
CREATE INDEX idx_metadata ON documents USING gin (metadata);

-- RRFスコア関数
CREATE OR REPLACE FUNCTION rrf_score(rank bigint, rrf_k int DEFAULT 50)
  RETURNS numeric AS $$
  SELECT COALESCE(1.0 / ($1 + $2), 0.0);
$$ LANGUAGE SQL IMMUTABLE PARALLEL SAFE;

-- タグ管理
CREATE TABLE tags (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE document_tags (
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (document_id, tag_id)
);
```

### 接続設定

```python
# ローカル開発
db_host = "localhost"
db_port = 5432

# Cloud SQL（Unix Socket）
db_host = "/cloudsql/project:region:instance"
# 接続文字列: postgresql://user:pass@/dbname?host=/cloudsql/...
```

---

## 検索パイプライン

### 検索フローの詳細

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
       └── BM25/トライグラム類似度でランキング
   ↓
4. RRF融合
   - 各検索結果のランクからスコア計算
   - 1 / (rank + k) で統合
   ↓
5. ACLフィルタリング
   - allowed_principals LIKE '%user@email%'
   ↓
6. タグブースト（オプション）
   - 特定タグを持つ文書のスコアを加算
   ↓
7. BGEリランキング
   - クロスエンコーダで(query, doc)ペアをスコアリング
   - Sigmoid正規化
   - Top-K選別
   ↓
8. 結果返却
```

### パラメータチューニング

| パラメータ | デフォルト値 | 説明 |
|-----------|-------------|------|
| `hybrid_search_k` | 10 | ハイブリッド検索の取得数 |
| `rrf_k` | 50 | RRFのk値（高いほど順位差の影響小） |
| `reranker_top_k` | 5 | リランキング後の返却数 |
| `tag_boost_value` | 0.1 | タグブーストの加算値 |

---

## LLM統合

### Ollama設定

```yaml
# 推奨モデル
model: qwen2.5:3b         # バランス型（速度/品質）
# alternatives:
# - qwen3:14b            # 高品質（GPU推奨）
# - llama3.2:3b          # 英語向け
```

### プロンプト設計のポイント

```python
# 3Bモデル向け最適化
prompt_template = """
あなたは[役割]です。

【回答方針】
- [箇条書きで明確に]
- [文字数制限を明示]
- [禁止事項を明記]

【質問】
{query}

【参照情報】
{context}

上記に基づいて回答してください。
"""

# コンテキスト圧縮
max_context_chars = 800  # 3Bモデル用
# 大きいモデルでは1500〜3000に増やす
```

### LCEL（LangChain Expression Language）

```python
# シンプルなチェーン構成
chain = prompt | llm | output_parser

# 呼び出し
result = chain.invoke({"query": query, "context": context})
```

---

## セキュリティ（ACL制御）

### 3層アクセス制御

```
1. データ取り込み時
   - Google Drive APIからPermissionを取得
   - allowed_principalsとしてDBに保存

2. 検索時
   - SQLのWHERE句でフィルタリング
   - allowed_principals LIKE '%user@email%'

3. API時
   - エンドポイントでuser_emailを必須化
   - アクセス権のないドキュメントは404
```

### 実装例

```python
# データ取り込み
def get_allowed_principals(file_id: str) -> list[str]:
    permissions = drive_service.permissions().list(fileId=file_id).execute()
    return [p["emailAddress"] for p in permissions.get("permissions", [])
            if p.get("type") == "user"]

# 検索
def search_with_acl(query: str, user_email: str):
    return cursor.execute("""
        SELECT * FROM documents
        WHERE allowed_principals LIKE %s
        ORDER BY embedding <-> %s
        LIMIT 10
    """, (f"%{user_email}%", query_vector))
```

---

## デプロイメント

### Dockerイメージ構成

```dockerfile
# Dockerfile.base（依存関係レイヤー）
FROM python:3.12-slim AS builder
RUN pip install uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Dockerfile（ランタイム）
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
COPY src/ /app/src/
CMD ["uvicorn", "src.api_server:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Terraform構成

```hcl
# Cloud Run Service
resource "google_cloud_run_service" "api" {
  name     = "rag-api"
  location = var.region

  template {
    spec {
      containers {
        image = "${var.registry}/api-server:latest"

        resources {
          limits = {
            memory = "2Gi"
            cpu    = "2"
          }
        }

        env {
          name  = "DB_HOST"
          value = "/cloudsql/${google_sql_database_instance.main.connection_name}"
        }
      }

      # Cloud SQL接続
      metadata {
        annotations = {
          "run.googleapis.com/cloudsql-instances" = google_sql_database_instance.main.connection_name
        }
      }
    }
  }
}

# Cloud SQL
resource "google_sql_database_instance" "main" {
  name             = "rag-db"
  database_version = "POSTGRES_15"

  settings {
    tier = "db-custom-2-4096"

    database_flags {
      name  = "cloudsql.enable_pg_trgm"
      value = "on"
    }

    backup_configuration {
      enabled = true
      backup_retention_settings {
        retained_backups = 7
      }
    }
  }
}
```

### CI/CD（Cloud Build）

```yaml
# cloudbuild.yaml
steps:
  - name: 'gcr.io/kaniko-project/executor:latest'
    args:
      - '--destination=${_REGISTRY}/api-server:latest'
      - '--cache=true'
      - '--cache-repo=${_REGISTRY}/cache'
      - '--cache-ttl=168h'
timeout: 600s

substitutions:
  _REGISTRY: us-central1-docker.pkg.dev/${PROJECT_ID}/rag-repo
```

---

## パフォーマンス最適化

### 検索の最適化

| 技法 | 効果 |
|------|------|
| RRF融合 | ベクトル検索のみより高い再現率 |
| クエリ書き換え | 言い換えへの対応力向上 |
| BGEリランキング | 精度向上（Top-K選別） |
| タグブースト | ドメイン特化の重み付け |

### LLM生成の最適化

| 技法 | 効果 |
|------|------|
| コンテキスト圧縮 | トークン削減・推論高速化 |
| 短いプロンプト | 3Bモデルでの安定性向上 |
| FP16推論 | GPU使用時のメモリ効率化 |

### インフラの最適化

| 技法 | 効果 |
|------|------|
| Baseイメージ分離 | ビルド時間短縮 |
| Kanikoキャッシュ | CI/CD高速化 |
| Unix Socket接続 | Cloud SQLへの低レイテンシ接続 |
| 自前Ollama | API費用削減 |

---

## エラーハンドリング

### Graceful Degradation

```python
# リランカー失敗時
def get_reranker():
    try:
        return BGEReranker()
    except Exception:
        return None  # Noneなら検索結果をそのまま返す

# クエリ書き換え失敗時
try:
    queries = query_rewriter.rewrite(query)
except Exception:
    queries = [query]  # 元のクエリのみ使用

# LLM生成失敗時
try:
    answer = chain.invoke(...)
except Exception as e:
    return {
        "answer": "エラーが発生しました。",
        "error": str(e)
    }
```

---

## 今後の拡張ポイント

1. **マルチモーダル対応**: 画像・PDFのEmbedding
2. **ストリーミング応答**: Server-Sent Events
3. **フィードバック学習**: ユーザー評価の収集と反映
4. **A/Bテスト**: リランカー・プロンプトの比較
5. **キャッシュ層**: Redis/Memcachedによるクエリキャッシュ
