# LangChain 参考ドキュメント一覧

このプロジェクトで使用しているLangChainの機能と、対応する公式ドキュメントへのリンク集です。

---

## 1. コア概念・チュートリアル

### RAG (Retrieval-Augmented Generation)

| ドキュメント | 説明 |
|------------|------|
| [Build a RAG agent with LangChain](https://docs.langchain.com/oss/python/langchain/rag) | RAGエージェントの構築チュートリアル。2-step RAGチェーンとAgenticRAGの両方をカバー |
| [Retrieval-Augmented Generation 概要](https://docs.langchain.com/oss/python/langchain/retrieval) | RAGアーキテクチャの概念説明。Agentic RAGと2-Step RAGの違い |
| [RAG評価 (LangSmith)](https://docs.langchain.com/langsmith/evaluate-rag-tutorial) | RAGアプリケーションの評価手法。データセット作成、評価メトリクス |

### LangChain概要

| ドキュメント | 説明 |
|------------|------|
| [LangChain Overview (Python)](https://docs.langchain.com/oss/python/langchain/overview) | LangChain v1.xの概要。エージェント、モデル統合の基本 |
| [Install LangChain](https://docs.langchain.com/oss/python/langchain/install) | インストール手順（`pip install -U langchain`） |
| [Component Architecture](https://docs.langchain.com/oss/python/langchain/component-architecture) | LangChainのコンポーネント構成図。Input処理→Embedding→Retrieval→Generation→Orchestration |

---

## 2. データ処理・ドキュメント

### Document クラス

| ドキュメント | 説明 |
|------------|------|
| [Documents and Document Loaders](https://docs.langchain.com/oss/python/langchain/knowledge-base) | `Document`抽象クラスの説明。`page_content`、`metadata`、`id`属性 |

**本プロジェクトでの使用例:**
```python
from langchain_core.documents import Document

Document(
    page_content=chunk,
    metadata={
        "source": file_name,
        "file_id": file_id,
        "chunk_index": i,
    }
)
```

### テキスト分割 (Text Splitters)

| ドキュメント | 説明 |
|------------|------|
| [Text Splitters](https://docs.langchain.com/oss/python/integrations/splitters/index) | テキスト分割の戦略一覧。ほとんどのユースケースで`RecursiveCharacterTextSplitter`を推奨 |
| [Splitting documents (RAGチュートリアル内)](https://docs.langchain.com/oss/python/langchain/rag) | ドキュメント分割の実践的な使い方 |

**本プロジェクトでの使用例:**
```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    separators=["\n\n", "\n", "。", ".", " ", ""]
)
chunks = splitter.split_text(content)
```

---

## 3. Embeddings（埋め込み）

### Vertex AI Embeddings

| ドキュメント | 説明 |
|------------|------|
| [Embeddings 概要](https://docs.langchain.com/oss/python/langchain/knowledge-base) | Embeddingsの概念説明。ベクトル検索の基礎 |
| [Google Cloud (Vertex AI)](https://docs.langchain.com/oss/python/integrations/providers/google) | Google Cloud/Vertex AI統合の全体像 |
| [Embedding Model Integrations](https://docs.langchain.com/oss/python/integrations/text_embedding/index) | 各種Embeddingモデルの統合一覧 |

**本プロジェクトでの使用例:**
```python
from langchain_google_vertexai import VertexAIEmbeddings

embeddings = VertexAIEmbeddings(
    model_name="text-embedding-004",
    project=settings.google_project_id,
    location=settings.google_location,
)

# クエリの埋め込み
query_vector = embeddings.embed_query(query)

# ドキュメントのバッチ埋め込み
vectors = embeddings.embed_documents([doc.page_content for doc in documents])
```

---

## 4. Vector Store（ベクトルストア）

### PGVector / PostgreSQL

| ドキュメント | 説明 |
|------------|------|
| [Vector Stores 概要](https://docs.langchain.com/oss/python/langchain/knowledge-base) | VectorStoreの概念。`add_documents`、`similarity_search`メソッド |
| [PGVectorStore](https://docs.langchain.com/oss/python/integrations/vectorstores/index) | PostgreSQL + pgvector統合。`langchain-postgres`パッケージ |

**本プロジェクトでの使用例:**

本プロジェクトでは`langchain-postgres`の`PGVector`クラスを直接使用せず、カスタムのハイブリッド検索を実装しています：

```python
from langchain_postgres import PGVector

# 標準的な使い方（参考）
vector_store = PGVector(
    embeddings=embeddings,
    collection_name="my_docs",
    connection="postgresql+psycopg://...",
)
```

---

## 5. Chat Models（チャットモデル）

### Vertex AI (Gemini)

| ドキュメント | 説明 |
|------------|------|
| [Google Vertex AI Chat Models](https://docs.langchain.com/oss/python/integrations/chat/index) | ChatVertexAIの統合ドキュメント |
| [All Chat Models](https://docs.langchain.com/oss/python/integrations/chat/index) | サポートされている全チャットモデル一覧 |

**本プロジェクトでの使用例:**
```python
from langchain_google_vertexai import ChatVertexAI

llm = ChatVertexAI(
    model_name="gemini-1.5-flash",
    project=settings.google_project_id,
    location=settings.google_location,
    temperature=0.5,
)
```

### Ollama（ローカルLLM）

| ドキュメント | 説明 |
|------------|------|
| [Ollama Provider](https://docs.langchain.com/oss/python/integrations/providers/ollama) | Ollamaの全統合（Chat、LLM、Embeddings） |
| [Local Models](https://docs.langchain.com/oss/python/langchain/models) | ローカルモデル実行の概要 |

**本プロジェクトでの使用例（ブループリント）:**
```python
from langchain_ollama import ChatOllama

llm = ChatOllama(
    base_url="http://localhost:11434",
    model="qwen2.5:3b",
    temperature=0.7
)
```

---

## 6. プロンプトテンプレート

### ChatPromptTemplate

| ドキュメント | 説明 |
|------------|------|
| [Prompt Engineering Concepts](https://docs.langchain.com/langsmith/prompt-engineering-concepts) | プロンプトとプロンプトテンプレートの違い、Chat vs Completion形式 |
| [Prompt Quickstart (LangSmith)](https://docs.langchain.com/langsmith/prompt-engineering-quickstart) | プロンプトの作成、テスト、イテレーション |

**本プロジェクトでの使用例:**
```python
from langchain_core.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_messages([
    ("system", """あなたは文章スタイルを分析する専門家です。

## タスク
以下の過去記事から文体特徴を抽出してください。

## 出力形式
{format_instructions}"""),
    ("human", """## 過去記事
{reference_articles}

上記の過去記事から文体特徴を抽出してください。""")
])
```

---

## 7. 出力パーサー

### StrOutputParser / JsonOutputParser

| ドキュメント | 説明 |
|------------|------|
| [Structured Output](https://docs.langchain.com/oss/python/langchain/models) | 構造化出力の概念。Pydantic、TypedDict、JSON Schemaサポート |
| [Structured Output (Agent)](https://docs.langchain.com/oss/python/langchain/structured-output) | エージェントでの構造化出力 |

**本プロジェクトでの使用例:**
```python
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser

# 文字列出力
chain = prompt | llm | StrOutputParser()

# JSON/Pydantic出力
parser = JsonOutputParser(pydantic_object=StyleAnalysis)
chain = prompt | llm | parser
```

---

## 8. LCEL (LangChain Expression Language)

### チェーンの構築

| ドキュメント | 説明 |
|------------|------|
| [Trace with LangChain](https://docs.langchain.com/langsmith/trace-with-langchain) | LCELチェーンの構築例（`prompt | model | output_parser`） |

**本プロジェクトでの使用例:**
```python
# シンプルなチェーン構成
self.chain = self.prompt | self.llm | self.parser

# 呼び出し
result = self.chain.invoke({
    "reference_articles": articles_text,
    "article_type": article_type,
    "format_instructions": self.parser.get_format_instructions(),
})

# 非同期呼び出し
result = await self.chain.ainvoke({...})
```

---

## 9. 評価・観測

### LangSmith

| ドキュメント | 説明 |
|------------|------|
| [Trace with LangChain](https://docs.langchain.com/langsmith/trace-with-langchain) | LangSmithでのトレーシング設定 |
| [Evaluate a RAG application](https://docs.langchain.com/langsmith/evaluate-rag-tutorial) | RAG評価のチュートリアル |
| [RAG Evaluation Approaches](https://docs.langchain.com/langsmith/evaluation-approaches) | RAG評価のアプローチ（オフライン、オンライン、ペアワイズ） |

---

## 10. インストール・セットアップ

### パッケージ

本プロジェクトで使用しているLangChain関連パッケージ：

```toml
# pyproject.toml
[project]
dependencies = [
    # LangChain Core
    "langchain>=0.3.0",
    "langchain-community>=0.3.0",

    # Google Cloud / Vertex AI
    "langchain-google-vertexai>=2.0.7",

    # PostgreSQL Vector Store
    "langchain-postgres>=0.0.12",

    # Local LLM (Ollama)
    "langchain-ollama>=0.2.0",
]
```

| パッケージ | ドキュメント | 用途 |
|-----------|------------|------|
| `langchain` | [Install](https://docs.langchain.com/oss/python/langchain/install) | コア機能 |
| `langchain-google-vertexai` | [Google Cloud](https://docs.langchain.com/oss/python/integrations/providers/google) | Vertex AI Embeddings/Chat |
| `langchain-postgres` | [PGVector](https://docs.langchain.com/oss/python/integrations/vectorstores/index) | PostgreSQLベクトルストア |
| `langchain-ollama` | [Ollama](https://docs.langchain.com/oss/python/integrations/providers/ollama) | ローカルLLM |

---

## 11. 高度なトピック

### ハイブリッド検索 / リランキング

LangChainの標準機能では直接サポートされていないため、本プロジェクトではカスタム実装：

- **ハイブリッド検索**: `pgvector`（ベクトル検索）+ `pg_trgm`（全文検索）をRRFで融合
- **リランキング**: `FlagEmbedding`の`FlagReranker`（BGEクロスエンコーダ）を使用

参考リソース：
| リソース | 説明 |
|---------|------|
| [RAG From Scratch シリーズ](https://docs.langchain.com/langsmith/evaluation-approaches) | RAGの詳細な実装パターン |
| [Agentic RAG](https://docs.langchain.com/oss/python/langchain/retrieval) | エージェントベースのRAG |

---

## クイックリファレンス

### よく使うインポート

```python
# ドキュメント
from langchain_core.documents import Document

# テキスト分割
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Embeddings
from langchain_google_vertexai import VertexAIEmbeddings

# Chat Models
from langchain_google_vertexai import ChatVertexAI
from langchain_ollama import ChatOllama

# プロンプト
from langchain_core.prompts import ChatPromptTemplate

# 出力パーサー
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
```

### LCEL パターン

```python
# 基本パターン
chain = prompt | llm | parser
result = chain.invoke({"key": "value"})

# 非同期
result = await chain.ainvoke({"key": "value"})

# ストリーミング
for chunk in chain.stream({"key": "value"}):
    print(chunk)
```

---

## 更新履歴

- 2024年12月: 初版作成
