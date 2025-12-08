# Dify v3 互換実装計画

Difyワークフロー（note記事ドラフト生成_v3.yml）と同等の処理をPython/LangChainで実現するための実装計画。

> **ステータス**: 実装完了 ✅（全フェーズ実装済み）

---

## 1. 実装目標

### 1.1 機能目標
- カテゴリ別ナレッジベース検索（CONTENT_KB + STYLE_KB）
- 品質保証パイプライン（文体チェック → 自動リライト → ハルシネーション検知）
- メタ情報付き記事ドラフト出力

### 1.2 非機能目標
- **コスト削減**: 軽量LLM（gemini-2.0-flash-lite）の併用で25-30%削減
- **速度改善**: 軽量モデル使用箇所でレイテンシ短縮
- **検索精度向上**: BGE-reranker-v2-m3へのアップグレード

### 1.3 対応カテゴリ

| カテゴリ | 説明 | 用途例 |
|---------|------|--------|
| `INTERVIEW` | 社員インタビュー | 入社エントリ、人物フォーカス記事 |
| `EVENT_REPORT` | イベントレポート | 勉強会、セミナー報告 |
| `ANNOUNCEMENT` | お知らせ・リリース | 新サービス発表、プレスリリース |
| `CULTURE` | カルチャー・ストーリー | 企業文化、制度紹介 |

---

## 1.5 処理フロー全体像

```
[ユーザー入力]
       │
       ▼
┌─────────────────┐
│ 1. 入力解析      │  InputParserChain (flash-lite)
│   category/theme │
│   audience/goal  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 2. カテゴリ分類  │  ArticleClassifierChain (flash-lite)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 3. クエリ生成    │  QueryGeneratorChain (flash-lite)
└────────┬────────┘
         │
         ▼
┌──────────────────────────────────────────────────┐
│ 4. 並列検索                                       │
│                                                  │
│  ArticleRetriever    StyleProfileRetriever       │
│  (CONTENT_KB)        (STYLE_PROFILE + EXCERPTS)  │
│   top_k=15            top_k=1 / top_k=5          │
└──────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│ 5. 文体・構造    │  StyleAnalyzerChain (flash-lite)
│    分析         │  StructureAnalyzerChain (flash-lite)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 6. アウトライン  │  OutlineGeneratorChain (flash)
│    生成         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 7. コンテンツ    │  Title/Lead/Section/ClosingGeneratorChain (flash)
│    生成         │
└────────┬────────┘
         │
         ▼
┌──────────────────────────────────────────────────┐
│ 8. 品質保証パイプライン                            │
│                                                  │
│  文体チェック → 自動リライト → ハルシネーション検知  │
│  (flash-lite)    (flash)       (flash-lite)      │
│       │              │              │            │
│       ▼              ▼              ▼            │
│  consistency    rewritten     [要確認]タグ        │
│  score          article       挿入               │
└──────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│ 9. 最終整形      │  メタ情報付きMarkdown出力
└─────────────────┘
```

---

## 2. モデル構成

### 2.1 LLMモデル（2層構成）

| モデル | 用途 | 価格（入力/出力） |
|--------|------|------------------|
| **gemini-2.0-flash** | 高品質生成タスク | $0.10 / $0.40 per 1M tokens |
| **gemini-2.0-flash-lite** | 軽量タスク | $0.07 / $0.30 per 1M tokens |

### 2.2 チェーン別モデル割り当て

| チェーン | 現在 | 変更後 | 理由 |
|---------|------|--------|------|
| InputParserChain | flash | **flash-lite** | 構造化抽出は軽量モデルで十分 |
| ArticleClassifierChain | flash | **flash-lite** | 4択分類は軽量モデルで十分 |
| QueryGeneratorChain | - | **flash-lite** | 新規追加、軽量タスク |
| StyleAnalyzerChain | flash | **flash-lite** | パターン抽出は軽量で可 |
| StructureAnalyzerChain | flash | **flash-lite** | パターン抽出は軽量で可 |
| OutlineGeneratorChain | flash | flash | 創造的タスク、品質重視 |
| TitleGeneratorChain | flash | flash | 創造的タスク、品質重視 |
| LeadGeneratorChain | flash | flash | 品質重視 |
| SectionGeneratorChain | flash | flash | 品質重視 |
| ClosingGeneratorChain | flash | flash | 品質重視 |
| StyleCheckerChain | flash | **flash-lite** | 検証タスクは軽量で可 |
| HallucinationDetectorChain | flash | **flash-lite** | 検証タスクは軽量で可 |
| AutoRewriteChain | - | flash | 新規追加、品質重視 |

### 2.3 Rerankerモデル

| 現在 | 変更後 | 改善点 |
|------|--------|--------|
| BAAI/bge-reranker-base (278M) | **BAAI/bge-reranker-v2-m3** | 多言語対応強化、性能向上 |

### 2.4 コスト削減効果（推定）

```
現在: 全チェーンでflash使用
  → 入力: $0.10/1M × 全量
  → 出力: $0.40/1M × 全量

変更後: 7/13チェーンをflash-liteに
  → flash-lite部分: 約30%削減
  → 全体: 約20-25%削減（タスク分布による）
```

---

## 3. 実装フェーズ

### Phase 0: モデル設定基盤（優先度: 最高）✅ 完了

#### 0.1 config.py の拡張

```python
class Settings(BaseSettings):
    # LLM Models (2-tier)
    llm_model: str = "gemini-2.0-flash"           # 高品質タスク用
    llm_model_lite: str = "gemini-2.0-flash-lite" # 軽量タスク用
    llm_temperature: float = 0.3

    # Reranker
    reranker_model: str = "BAAI/bge-reranker-v2-m3"  # アップグレード
    reranker_top_k: int = 5
    use_fp16: bool = True
```

#### 0.2 LLMファクトリ関数の追加

**ファイル**: `src/llm.py`（新規）

```python
from langchain_google_vertexai import ChatVertexAI
from src.config import settings

def get_llm(
    quality: str = "high",  # "high" or "lite"
    temperature: float | None = None
) -> ChatVertexAI:
    """LLMインスタンスを取得（品質レベル指定）"""
    model = settings.llm_model if quality == "high" else settings.llm_model_lite
    temp = temperature if temperature is not None else settings.llm_temperature

    return ChatVertexAI(
        model_name=model,
        project=settings.google_project_id,
        location=settings.google_location,
        temperature=temp,
    )
```

#### 0.3 各チェーンの更新

全チェーンで `get_llm()` を使用するように変更。

```python
# Before
self.llm = llm or ChatVertexAI(
    model_name=settings.llm_model,
    ...
)

# After
self.llm = llm or get_llm(quality="lite", temperature=0.2)
```

---

### Phase 1: 入力処理の拡張（優先度: 高）✅ 完了

#### 1.1 ParsedInputモデルの拡張

**ファイル**: `src/chains/input_parser.py`

```python
class ParsedInput(BaseModel):
    """構造化された入力情報（Dify v3互換）"""

    # 既存フィールド
    theme: str
    key_points: list[str] = []
    interview_quotes: list[InterviewQuote] = []
    data_facts: list[str] = []
    keywords: list[str] = []
    missing_info: list[str] = []

    # 新規追加（Dify v3互換）
    category: str = ""              # interview/event/announcement/story
    audience: str = ""              # 想定読者
    goal: str = ""                  # 記事の目的
    desired_length: int = 2000      # 希望文字数
```

#### 1.2 プロンプト全文

```python
SYSTEM_PROMPT = """あなたは入力情報を構造化するエキスパートです。

## タスク
ユーザーから提供された記事素材を分析し、以下の情報を抽出・構造化してください。

## 抽出項目
1. category: 記事カテゴリ（INTERVIEW / EVENT_REPORT / ANNOUNCEMENT / CULTURE）
2. theme: 記事のテーマ・主旨（1文で要約）
3. audience: 想定読者
4. goal: 記事の目的
5. desired_length: 希望文字数（指定なしの場合は2000）
6. key_points: 記事に含めるべき重要ポイント
7. interview_quotes: インタビュー発言（該当する場合）
8. data_facts: 具体的な数値やデータ
9. keywords: 検索用キーワード（5-10個）
10. missing_info: 不足している情報

## カテゴリ判定基準
- INTERVIEW: 社員インタビュー、入社エントリ、人物フォーカス
- EVENT_REPORT: 勉強会、イベント、セミナー報告
- ANNOUNCEMENT: 新サービス、リリース、お知らせ
- CULTURE: 企業文化、制度紹介、カルチャー

## ルール
- 入力にない情報は推測しない
- カテゴリが不明確な場合は最も近いものを選択
- 数値や固有名詞は正確に抽出
- interview_quotesは {speaker: "発言者名", quote: "発言内容"} 形式
"""

USER_PROMPT = """## 入力素材
{input_material}

上記の素材を構造化してください。JSON形式で出力してください。
"""
```

---

### Phase 2: クエリ生成チェーンの追加（優先度: 中）✅ 完了

#### 2.1 新規チェーン作成

**ファイル**: `src/chains/query_generator.py`

```python
class QueryGeneratorChain:
    """カテゴリに最適化された検索クエリを生成（Dify v3: node_query_gen_*）"""

    def __init__(self, llm: ChatVertexAI | None = None):
        self.llm = llm or get_llm(quality="lite", temperature=0.3)
        self.prompt = ChatPromptTemplate.from_messages([...])

    def generate(
        self,
        parsed_input: ParsedInput,
        category: ArticleType
    ) -> str:
        """
        入力情報からカテゴリに最適化された検索クエリを生成

        Args:
            parsed_input: 構造化された入力情報
            category: 記事カテゴリ

        Returns:
            スペース区切りの検索クエリ文字列
        """
```

#### 2.2 カテゴリ別プロンプト

```
あなたは検索クエリを最適化する専門家です。

## タスク
以下の情報から、{category}記事の内容検索に最適な検索クエリを生成してください。

## 入力情報
- テーマ: {theme}
- 読者: {audience}
- 目的: {goal}
- キーワード: {keywords}

## クエリ生成ルール
- キーワード列挙形式で出力
- 各クエリは簡潔に（1-6単語）
- テーマに関連するクエリ（2-3個）
- {category}記事の構成参考用クエリ（1-2個）

## 出力形式
search_query: "キーワード1 キーワード2 キーワード3 ..."
```

---

### Phase 3: 文体プロファイルKBの実装（優先度: 高）✅ 完了

Dify v3では STYLE_PROFILE（文体ルール）と STYLE_EXCERPTS（文体見本）を分離して管理。

#### 3.1 データベーススキーマ拡張

**ファイル**: `schemas/schema.sql`

```sql
-- 文体プロファイルテーブル追加
CREATE TABLE IF NOT EXISTS style_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article_type article_type_enum NOT NULL,
    profile_type VARCHAR(20) NOT NULL,  -- 'profile' or 'excerpt'
    content TEXT NOT NULL,
    embedding vector(768),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- カテゴリ × プロファイルタイプでユニーク（profileは1つのみ）
CREATE UNIQUE INDEX IF NOT EXISTS idx_style_profile_unique
    ON style_profiles(article_type)
    WHERE profile_type = 'profile';

-- 検索用インデックス
CREATE INDEX IF NOT EXISTS idx_style_profiles_type
    ON style_profiles(article_type, profile_type);

CREATE INDEX IF NOT EXISTS idx_style_profiles_embedding
    ON style_profiles USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 10);
```

#### 3.2 StyleProfileRetriever実装

**ファイル**: `src/retriever/style_retriever.py`

```python
class StyleProfileRetriever:
    """文体プロファイルと抜粋を検索（Dify v3: STYLE_PROFILE + STYLE_EXCERPTS）"""

    def __init__(
        self,
        db_connection: str | None = None,
        embeddings: VertexAIEmbeddings | None = None,
        reranker: BGEReranker | None = None,
    ):
        self.conn_string = db_connection or settings.db_connection_string
        self.embeddings = embeddings or VertexAIEmbeddings(...)
        self.reranker = reranker

    def retrieve_profile(self, article_type: ArticleType) -> str | None:
        """
        カテゴリの文体プロファイル（ルール定義）を取得

        Dify v3相当: node_style_profile_* (top_k=1)
        """
        # profile_type='profile' でフィルタ、top_k=1

    def retrieve_excerpts(
        self,
        theme: str,
        article_type: ArticleType,
        top_k: int = 5
    ) -> list[str]:
        """
        テーマに類似した文体抜粋を取得

        Dify v3相当: node_style_excerpts_* (top_k=5)
        """
        # profile_type='excerpt' でフィルタ
        # theme でベクトル検索 → rerank
```

#### 3.3 文体プロファイルデータ（4カテゴリ全文）

**ファイル**: `data/style_profiles/interview.md`

```markdown
# インタビュー記事 文体プロファイル

## 語尾パターン
- 〜です、〜ですね、〜なんです
- 親しみやすさを重視
- 「〜していただきました」等の丁寧表現

## トーン
- カジュアル寄り
- インタビュイーの人柄が伝わる
- 読者との距離感を縮める

## 一人称
- 私（インタビュアー視点）
- インタビュイーは名前で呼ぶ

## 構成パターン
1. 人物紹介（経歴・現在の役割）
2. きっかけ・背景
3. 現在の仕事・活動
4. 今後の展望・メッセージ

## 特徴的表現
- 「〜について聞いてみました」
- 「〇〇さんはこう語ります」
- 「印象的だったのは〜」

## 禁止事項
- 過剰な煽り表現
- 根拠のない断定
- インタビュイーの発言の改変
```

**ファイル**: `data/style_profiles/event_report.md`

```markdown
# イベントレポート記事 文体プロファイル

## 語尾パターン
- 〜しました、〜でした
- 〜が行われました
- レポート調の客観的表現

## トーン
- 中立的・報告調
- 臨場感を伝える
- 学びや気づきを共有

## 一人称
- 筆者、私（参加者視点）
- 「私たち」（チーム参加の場合）

## 構成パターン
1. イベント概要（日時・場所・目的）
2. 内容のハイライト
3. 学び・気づき
4. まとめ・次回予告

## 特徴的表現
- 「〜が開催されました」
- 「印象的だったのは〜」
- 「参加者からは〜という声が」

## 禁止事項
- 主観的すぎる感想
- 参加者の特定につながる情報（許可なし）
- イベント内容の誤解を招く表現
```

**ファイル**: `data/style_profiles/announcement.md`

```markdown
# アナウンスメント記事 文体プロファイル

## 語尾パターン
- 〜します、〜いたします
- 〜を開始します
- フォーマルな丁寧語

## トーン
- 公式・フォーマル
- 明確で簡潔
- 信頼感を与える

## 一人称
- 弊社、当社、私たち
- 会社名（株式会社ギグー）

## 構成パターン
1. ニュースの要点（リード）
2. 詳細説明
3. 背景・目的
4. 今後の展開・CTA

## 特徴的表現
- 「この度〜」
- 「〜を発表いたします」
- 「詳細は以下をご覧ください」

## 禁止事項
- 曖昧な表現
- 未確定情報の断定
- 競合他社への言及
```

**ファイル**: `data/style_profiles/culture.md`

```markdown
# カルチャー/ストーリー記事 文体プロファイル

## 語尾パターン
- 〜です、〜ですね
- 〜なんです（親しみやすさ）
- 「〜しています」（現在進行形）

## トーン
- 親しみやすい
- 社内の雰囲気が伝わる
- 読者に「働きたい」と思わせる

## 一人称
- 私たち、チーム名
- 会社名（カジュアルに）

## 構成パターン
1. 制度・文化の紹介
2. 具体的な運用方法
3. 社員の声・エピソード
4. まとめ・メッセージ

## 特徴的表現
- 「実は〜」
- 「〇〇という制度があります」
- 「社員の〇〇さんに聞いてみました」

## 禁止事項
- 自慢に聞こえる表現
- 他社との比較
- 実態と乖離した美化
```

#### 3.4 データ投入スクリプト

**ファイル**: `scripts/seed_style_profiles.py`

```python
"""文体プロファイルデータをDBに投入"""

import asyncio
from pathlib import Path

import psycopg2
from langchain_google_vertexai import VertexAIEmbeddings

from src.config import settings

PROFILE_DIR = Path("data/style_profiles")

# カテゴリとファイル名のマッピング
CATEGORY_FILES = {
    "INTERVIEW": "interview.md",
    "EVENT_REPORT": "event_report.md",
    "ANNOUNCEMENT": "announcement.md",
    "CULTURE": "culture.md",
}


def seed_profiles():
    """文体プロファイルをDBに投入"""
    embeddings = VertexAIEmbeddings(
        model_name=settings.embedding_model,
        project=settings.google_project_id,
        location=settings.google_location,
    )

    conn = psycopg2.connect(settings.db_connection_string)
    cur = conn.cursor()

    for article_type, filename in CATEGORY_FILES.items():
        filepath = PROFILE_DIR / filename
        if not filepath.exists():
            print(f"Warning: {filepath} not found, skipping")
            continue

        content = filepath.read_text(encoding="utf-8")

        # Embedding生成
        embedding = embeddings.embed_query(content)

        # UPSERT（既存があれば更新）
        cur.execute(
            """
            INSERT INTO style_profiles (article_type, profile_type, content, embedding)
            VALUES (%s, 'profile', %s, %s)
            ON CONFLICT (article_type) WHERE profile_type = 'profile'
            DO UPDATE SET content = EXCLUDED.content,
                          embedding = EXCLUDED.embedding,
                          updated_at = CURRENT_TIMESTAMP
            """,
            (article_type, content, embedding),
        )
        print(f"Inserted/Updated profile for {article_type}")

    conn.commit()
    cur.close()
    conn.close()
    print("Done!")


if __name__ == "__main__":
    seed_profiles()
```

#### 3.5 StyleProfileRetriever 完全実装

```python
"""文体プロファイル検索（src/retriever/style_retriever.py）"""

from typing import List, Optional

import psycopg2
from langchain_core.documents import Document
from langchain_google_vertexai import VertexAIEmbeddings

from src.config import settings
from src.retriever.article_retriever import ArticleType
from src.retriever.reranker import BGEReranker, get_reranker


class StyleProfileRetriever:
    """文体プロファイルと抜粋を検索"""

    def __init__(
        self,
        embeddings: VertexAIEmbeddings | None = None,
        reranker: BGEReranker | None = None,
    ):
        self.embeddings = embeddings or VertexAIEmbeddings(
            model_name=settings.embedding_model,
            project=settings.google_project_id,
            location=settings.google_location,
        )
        self.reranker = reranker or get_reranker()
        self.conn_string = settings.db_connection_string

    def retrieve_profile(self, article_type: ArticleType) -> str | None:
        """
        カテゴリの文体プロファイル（ルール定義）を取得

        Args:
            article_type: 記事カテゴリ

        Returns:
            文体プロファイルテキスト、なければNone
        """
        conn = psycopg2.connect(self.conn_string)
        cur = conn.cursor()

        cur.execute(
            """
            SELECT content FROM style_profiles
            WHERE article_type = %s AND profile_type = 'profile'
            LIMIT 1
            """,
            (article_type.value,),
        )

        result = cur.fetchone()
        cur.close()
        conn.close()

        return result[0] if result else None

    def retrieve_excerpts(
        self,
        theme: str,
        article_type: ArticleType,
        top_k: int = 5,
    ) -> List[str]:
        """
        テーマに類似した文体抜粋を取得

        Args:
            theme: 検索テーマ
            article_type: 記事カテゴリ
            top_k: 取得件数

        Returns:
            文体抜粋テキストのリスト
        """
        # テーマをベクトル化
        query_embedding = self.embeddings.embed_query(theme)

        conn = psycopg2.connect(self.conn_string)
        cur = conn.cursor()

        # ベクトル検索（profile_type='excerpt'のみ）
        cur.execute(
            """
            SELECT content, 1 - (embedding <=> %s::vector) as similarity
            FROM style_profiles
            WHERE article_type = %s AND profile_type = 'excerpt'
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (query_embedding, article_type.value, query_embedding, top_k * 2),
        )

        results = cur.fetchall()
        cur.close()
        conn.close()

        if not results:
            return []

        # Rerank（利用可能な場合）
        if self.reranker:
            documents = [
                Document(page_content=content, metadata={"similarity": sim})
                for content, sim in results
            ]
            reranked = self.reranker.rerank(theme, documents, top_k=top_k)
            return [doc.page_content for doc in reranked]

        # Rerankなしの場合はそのまま返す
        return [content for content, _ in results[:top_k]]
```

---

### Phase 4: 自動リライトチェーンの実装（優先度: 中）✅ 完了

#### 4.1 新規チェーン作成

**ファイル**: `src/chains/auto_rewrite.py`

```python
class RewriteResult(BaseModel):
    """リライト結果"""
    rewritten_text: str
    changes_made: list[str]
    original_length: int
    rewritten_length: int


class AutoRewriteChain:
    """文体チェック結果を反映して記事をリライト（Dify v3: node_auto_rewrite）"""

    def __init__(self, llm: ChatVertexAI | None = None):
        # 品質重視のため flash を使用
        self.llm = llm or get_llm(quality="high", temperature=0.5)

    def rewrite(
        self,
        article_text: str,
        style_check_result: StyleCheckResult,
        style_profile: str
    ) -> RewriteResult:
        """
        文体問題を修正したリライト版を生成

        Args:
            article_text: 元の記事テキスト
            style_check_result: StyleCheckerChainの結果
            style_profile: 文体プロファイル

        Returns:
            RewriteResult: リライト済みテキストと変更内容
        """
```

#### 4.2 リライトプロンプト

```
あなたはスタイル編集者です。
STYLE_PROFILE を満たすように本文を完全リライトしてください。

## STYLE_PROFILE（文体ルール）
{style_profile}

## 文体チェック結果
一貫性スコア: {consistency_score}
問題点: {issues}
修正案: {corrected_sections}

## 元の記事
{article_text}

## 指示
1. STYLE_PROFILEに一致するよう文体を整える
2. 文体チェック結果の修正案を反映
3. 内容・事実は変更しない
4. 構成（見出し順序）は維持
```

---

### Phase 5: パイプライン統合（優先度: 高）✅ 完了

#### 5.1 ArticleGenerationPipelineの更新

**ファイル**: `src/chains/article_chain.py`

```python
class ArticleGenerationPipeline:
    """記事生成パイプライン（Dify v3互換）"""

    def __init__(self):
        # Phase 0: LLMファクトリ使用
        self.input_parser = InputParserChain()      # flash-lite
        self.classifier = ArticleClassifierChain()   # flash-lite

        # Phase 2: クエリ生成追加
        self.query_generator = QueryGeneratorChain() # flash-lite

        # 検索
        self.article_retriever = ArticleRetriever()

        # Phase 3: 文体プロファイル検索追加
        self.style_retriever = StyleProfileRetriever()

        # 分析
        self.style_analyzer = StyleAnalyzerChain()     # flash-lite
        self.structure_analyzer = StructureAnalyzerChain() # flash-lite

        # 生成
        self.outline_generator = OutlineGeneratorChain() # flash
        self.title_generator = TitleGeneratorChain()     # flash
        self.lead_generator = LeadGeneratorChain()       # flash
        self.section_generator = SectionGeneratorChain() # flash
        self.closing_generator = ClosingGeneratorChain() # flash

        # 検証
        self.style_checker = StyleCheckerChain()         # flash-lite
        self.hallucination_detector = HallucinationDetectorChain() # flash-lite

        # Phase 4: 自動リライト追加
        self.auto_rewriter = AutoRewriteChain()          # flash

    async def generate(self, input_material: str) -> ArticleDraft:
        """
        Dify v3互換の生成フロー

        1. 入力解析（category, audience, goal含む）
        2. カテゴリ分類
        3. クエリ生成（カテゴリ別最適化）
        4. 並列検索
           - CONTENT_KB: ArticleRetriever
           - STYLE_PROFILE: StyleProfileRetriever.retrieve_profile()
           - STYLE_EXCERPTS: StyleProfileRetriever.retrieve_excerpts()
        5. 分析（文体・構造）
        6. アウトライン生成
        7. コンテンツ生成（タイトル、リード、本文、締め）
        8. 品質保証パイプライン
           - 文体チェック
           - 自動リライト（スコア < 0.8の場合）
           - ハルシネーション検知
           - [要確認]タグ挿入
        9. 最終整形（メタ情報付き）
        """

    async def _retrieve_all(
        self,
        query: str,
        theme: str,
        article_type: ArticleType
    ) -> RetrievalResult:
        """並列検索（CONTENT_KB + STYLE_PROFILE + STYLE_EXCERPTS）"""
        content_task = self.article_retriever.retrieve_by_type(
            query=query,
            article_type=article_type,
            top_k=15  # Dify v3と同じ
        )
        profile_task = self.style_retriever.retrieve_profile(article_type)
        excerpts_task = self.style_retriever.retrieve_excerpts(
            theme=theme,
            article_type=article_type,
            top_k=5  # Dify v3と同じ
        )

        content, profile, excerpts = await asyncio.gather(
            content_task, profile_task, excerpts_task
        )

        return RetrievalResult(
            content_chunks=content,
            style_profile=profile,
            style_excerpts=excerpts
        )

    async def _quality_assurance(
        self,
        draft: ArticleDraft,
        style_profile: str,
        content_chunks: list[Document]
    ) -> ArticleDraft:
        """品質保証パイプライン（Dify v3: フェーズ7相当）"""

        # 1. 文体チェック
        style_check = await self.style_checker.acheck(
            draft.to_markdown(),
            style_profile
        )

        # 2. 自動リライト（スコアが低い場合）
        if style_check.consistency_score < 0.8:
            rewrite_result = await self.auto_rewriter.arewrite(
                draft.to_markdown(),
                style_check,
                style_profile
            )
            draft = self._parse_rewritten_draft(rewrite_result)

        # 3. ハルシネーション検知
        hallucination_result = await self.hallucination_detector.adetect(
            draft.to_markdown(),
            content_chunks
        )

        # 4. [要確認]タグ挿入
        if hallucination_result.unverified_claims:
            draft = self._apply_tags(draft, hallucination_result)

        # メタ情報更新
        draft.consistency_score = style_check.consistency_score
        draft.verification_confidence = hallucination_result.confidence

        return draft
```

---

### Phase 6: 最終整形の拡張（優先度: 低）✅ 完了

#### 6.1 ArticleDraftモデルの拡張

```python
class ArticleDraft(BaseModel):
    """記事ドラフト（Dify v3互換メタ情報付き）"""

    # 既存フィールド
    titles: list[str]
    lead: str
    sections: list[SectionContent]
    closing: str
    article_type: ArticleType

    # 新規追加（メタ情報）
    theme: str = ""
    desired_length: int = 2000
    actual_length: int = 0
    tag_count: int = 0
    consistency_score: float = 0.0
    verification_confidence: float = 0.0

    def to_markdown_with_meta(self) -> str:
        """Dify v3互換のメタ情報付きMarkdown出力"""
        md = self.to_markdown()

        category_ja = {
            ArticleType.INTERVIEW: "インタビュー",
            ArticleType.EVENT_REPORT: "イベントレポート",
            ArticleType.ANNOUNCEMENT: "アナウンスメント",
            ArticleType.CULTURE: "カルチャー/ストーリー",
        }

        meta = f"""
---

### メタ情報

- **記事カテゴリ**: {category_ja.get(self.article_type, str(self.article_type))}
- **テーマ**: {self.theme}
- **総文字数**: 約{self.actual_length}字（目標: {self.desired_length}字）
- **[要確認]タグ**: {self.tag_count}箇所
- **文体一貫性スコア**: {int(self.consistency_score * 100)}%
- **事実検証信頼度**: {int(self.verification_confidence * 100)}%

### 次のステップ

1. [要確認] タグがある箇所は事実確認してください
2. タイトルは3案から選択または調整してください
3. 必要に応じて文章を微調整してください
"""
        return md + meta
```

---

## 4. 実装スケジュール

```
Week 1:
├── Phase 0: モデル設定基盤
│   ├── config.py 拡張（llm_model_lite, reranker_model）
│   ├── src/llm.py 新規作成（get_llm ファクトリ）
│   └── 全チェーンのLLM初期化を更新
│
├── Phase 1: 入力処理の拡張
│   ├── ParsedInput に audience, goal, desired_length 追加
│   └── プロンプト更新

Week 2:
├── Phase 3: 文体プロファイルKB（前半）
│   ├── DBスキーマ追加（style_profiles テーブル）
│   ├── StyleProfileRetriever 実装
│   └── 文体プロファイルデータ作成（4カテゴリ分）
│
├── Phase 2: クエリ生成チェーン
│   ├── QueryGeneratorChain 実装
│   └── パイプライン統合

Week 3:
├── Phase 3: 文体プロファイルKB（後半）
│   ├── データ投入スクリプト
│   └── パイプライン統合
│
├── Phase 4: 自動リライト
│   ├── AutoRewriteChain 実装
│   └── 品質保証パイプライン統合

Week 4:
├── Phase 5: パイプライン統合
│   ├── ArticleGenerationPipeline 全体更新
│   ├── 並列検索実装
│   └── 品質保証パイプライン実装
│
├── Phase 6: 最終整形
│   └── メタ情報付き出力

Week 5:
├── テスト・デバッグ
│   ├── ユニットテスト
│   ├── 統合テスト
│   └── E2Eテスト
│
└── ドキュメント更新
```

---

## 5. ファイル変更一覧（実装済み）

### 新規作成（完了）
| ファイル | 説明 | ステータス |
|---------|------|----------|
| `src/llm.py` | LLMファクトリ関数 | ✅ |
| `src/chains/query_generator.py` | クエリ生成チェーン | ✅ |
| `src/chains/auto_rewrite.py` | 自動リライトチェーン | ✅ |
| `src/retriever/style_retriever.py` | 文体プロファイル検索 | ✅ |
| `scripts/seed_style_profiles.py` | データ投入スクリプト | ✅ |

### 変更（完了）
| ファイル | 変更内容 | ステータス |
|---------|---------|----------|
| `src/config.py` | `llm_model_lite`, Feature Flags 追加 | ✅ |
| `src/chains/input_parser.py` | ParsedInput拡張、プロンプト更新 | ✅ |
| `src/chains/article_chain.py` | パイプライン全体更新 | ✅ |
| `src/chains/*.py` (全チェーン) | `get_llm()` 使用に変更 | ✅ |
| `src/retriever/reranker.py` | モデル名デフォルト変更（v2-m3） | ✅ |
| `src/verification/*.py` | `get_llm()` 使用に変更 | ✅ |
| `schemas/schema.sql` | style_profiles テーブル追加 | ✅ |

---

## 6. テスト計画

### 6.1 ユニットテスト

```python
# tests/test_llm_factory.py
def test_get_llm_high_quality():
    """高品質モデル取得"""

def test_get_llm_lite():
    """軽量モデル取得"""

# tests/test_query_generator.py
def test_generate_interview_query():
    """インタビュー用クエリ生成"""

def test_generate_event_query():
    """イベント用クエリ生成"""

# tests/test_style_retriever.py
def test_retrieve_profile():
    """文体プロファイル取得"""

def test_retrieve_excerpts():
    """文体抜粋取得"""

# tests/test_auto_rewrite.py
def test_rewrite_with_issues():
    """問題ありの場合のリライト"""

def test_rewrite_preserves_content():
    """リライトが内容を保持すること"""
```

### 6.2 統合テスト

```python
# tests/test_pipeline_v3.py
def test_full_pipeline_interview():
    """インタビュー記事のフルパイプライン"""

def test_full_pipeline_with_auto_rewrite():
    """自動リライトを含むパイプライン"""

def test_parallel_retrieval():
    """並列検索の動作確認"""
```

### 6.3 性能テスト

```python
# tests/test_performance.py
def test_lite_model_latency():
    """軽量モデルのレイテンシ計測"""

def test_cost_comparison():
    """コスト比較（flash vs flash-lite）"""
```

---

## 7. マイグレーション手順

### 7.1 データベースマイグレーション

```bash
# 1. スキーマ適用
./scripts/apply-schema.sh dev

# 2. 文体プロファイルデータ投入
uv run python scripts/seed_style_profiles.py
```

### 7.2 環境変数更新

```bash
# .env に追加（または既存値を更新）
LLM_MODEL=gemini-2.0-flash
LLM_MODEL_LITE=gemini-2.0-flash-lite
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
```

### 7.3 依存関係確認

```bash
# pyproject.toml の FlagEmbedding が v2-m3 対応か確認
uv sync
```

---

## 8. ロールバック計画

### 8.1 機能フラグによる段階的有効化

```python
# config.py
class Settings:
    # 新機能フラグ
    use_lite_model: bool = True          # flash-lite 使用
    use_query_generator: bool = True     # クエリ生成チェーン
    use_style_profile_kb: bool = True    # 文体プロファイルKB
    use_auto_rewrite: bool = True        # 自動リライト
    reranker_version: str = "v2-m3"      # "base" or "v2-m3"
```

### 8.2 ロールバック手順

```bash
# 1. 機能フラグを無効化
USE_LITE_MODEL=false
USE_QUERY_GENERATOR=false
USE_STYLE_PROFILE_KB=false
USE_AUTO_REWRITE=false
RERANKER_VERSION=base

# 2. 再デプロイ
./scripts/deploy-backend.sh dev
```

---

## 9. 参考資料

### 外部ドキュメント（参照不要）
このドキュメントは自己完結しており、以下のドキュメントを参照せずに実装可能です。

- ~~[Dify v3ワークフロー仕様](./DIFY_WORKFLOW_V3.md)~~ - 本ドキュメントに必要情報を統合済み
- ~~[差分分析](./DIFY_V3_IMPLEMENTATION_GAP.md)~~ - 本ドキュメントに必要情報を統合済み

### 外部リンク（モデル情報）
- [Gemini 2.0 Flash-Lite | Vertex AI](https://cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/2-0-flash-lite)
- [BAAI/bge-reranker-v2-m3 - Hugging Face](https://huggingface.co/BAAI/bge-reranker-v2-m3)

### プロジェクト内参照（既存コード理解用）
実装時に既存コードを参照する場合：
- `src/chains/article_chain.py` - 現在のパイプライン実装
- `src/retriever/hybrid_search.py` - ハイブリッド検索の実装パターン
- `src/verification/style_checker.py` - StyleCheckResult の型定義
