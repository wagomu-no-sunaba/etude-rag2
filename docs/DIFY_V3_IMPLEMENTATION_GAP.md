# Dify v3ワークフロー実装差分分析・実装計画

Difyワークフロー（note記事ドラフト生成_v3.yml）と現在のPython実装の差分を分析し、同等の処理を実現するための実装計画を記載する。

---

## 1. 現状比較サマリー

### 処理フロー対応表

| フェーズ | Dify v3 ノード | 現在の実装 | 差分状況 |
|---------|---------------|-----------|---------|
| 入力処理 | node_collect_inputs | InputParserChain | **部分的差分あり** |
| カテゴリ分岐 | node_category_switch | ArticleClassifierChain | **実装済み** |
| クエリ生成 | node_query_gen_* (4個) | (keywords利用) | **未実装** |
| コンテンツ検索 | node_content_kb_* (4個) | ArticleRetriever | **部分的差分あり** |
| 文体プロファイル | node_style_profile_* (4個) | (参照記事から抽出) | **未実装** |
| 文体抜粋 | node_style_excerpts_* (4個) | StyleAnalyzerChain | **部分的差分あり** |
| 結果マージ | node_merge_results | (パイプライン処理) | **実装済み** |
| アウトライン生成 | node_generate_outline | OutlineGeneratorChain | **実装済み** |
| 本文生成 | node_generate_article | SectionGeneratorChain等 | **実装済み** |
| 文体チェック | node_style_check | StyleCheckerChain | **実装済み** |
| 自動リライト | node_auto_rewrite | (提案のみ) | **未実装** |
| ハルシネーション検知 | node_hallucination_detect | HallucinationDetectorChain | **実装済み** |
| タグ挿入 | node_tag_inserter | apply_tags() | **実装済み** |
| 最終整形 | node_final_format | to_markdown() | **部分的差分あり** |

---

## 2. 詳細差分分析

### 2.1 入力処理（node_collect_inputs vs InputParserChain）

#### Dify v3の抽出項目
```
category, theme, audience, goal, desired_length,
key_points, interview_quotes, data_facts, keywords
```

#### 現在の実装（ParsedInput）
```python
theme, key_points, interview_quotes, data_facts,
people, keywords, missing_info
```

#### 差分
| 項目 | Dify | Python | 対応 |
|------|------|--------|------|
| `category` | 入力時に抽出 | 別チェーンで判定 | 統合が必要 |
| `audience` | あり | **なし** | 追加が必要 |
| `goal` | あり | **なし** | 追加が必要 |
| `desired_length` | あり（デフォ2000） | **なし** | 追加が必要 |
| `people` | なし | あり | Dify互換では不要 |
| `missing_info` | なし | あり | 維持（便利機能） |

### 2.2 クエリ生成（node_query_gen_* - 未実装）

#### Dify v3の処理
- カテゴリ別に専用LLMでクエリを生成
- 入力: theme, audience, goal, keywords
- 出力: search_query（スペース区切り）
- モデル: gpt-4o-mini (temp: 0.3)

#### 現在の実装
- InputParserChainで抽出したkeywordsをそのまま使用
- クエリ最適化なし

#### 必要な実装
```python
class QueryGeneratorChain:
    """カテゴリ別検索クエリを生成"""
    def generate(self, parsed_input: ParsedInput, category: str) -> str:
        # theme, audience, goal, keywords からクエリを生成
```

### 2.3 ナレッジ検索（3層構造 - 部分的未実装）

#### Dify v3のナレッジベース構成
```
┌─────────────────────────────────────────────────────┐
│ カテゴリごとに3種類のKBを検索                          │
│                                                     │
│ 1. CONTENT_KB (top_k=15)                           │
│    - 過去記事全文                                   │
│    - Cohere rerank-multilingual-v3.0              │
│                                                     │
│ 2. STYLE_PROFILE (top_k=1)                         │
│    - 文体ルール定義ドキュメント                      │
│    - Cohere rerank-english-v3.0                   │
│    - クエリ: カテゴリ名                              │
│                                                     │
│ 3. STYLE_EXCERPTS (top_k=5)                        │
│    - 文体見本（記事抜粋）                            │
│    - Cohere rerank-multilingual-v3.0              │
│    - クエリ: テーマ                                  │
└─────────────────────────────────────────────────────┘
```

#### 現在の実装
```
┌─────────────────────────────────────────────────────┐
│ ArticleRetriever                                    │
│                                                     │
│ - ハイブリッド検索（Vector + FT + RRF）               │
│ - BGE再ランク                                        │
│ - カテゴリフィルタあり                                │
│                                                     │
│ 文体取得:                                            │
│ - 参照記事からStyleAnalyzerChainで自動抽出           │
│ - 事前定義されたSTYLE_PROFILEなし                    │
└─────────────────────────────────────────────────────┘
```

#### 差分
1. **STYLE_PROFILE（文体ルール）が未実装**
   - Difyでは事前定義された文体ルールドキュメントを検索
   - 現在は参照記事から動的に抽出

2. **STYLE_EXCERPTS（文体抜粋）の分離が未実装**
   - Difyでは専用KBとして分離
   - 現在はCONTENT_KBと同じ検索結果を使用

3. **Rerankモデルの差異**
   - Dify: Cohere rerank-multilingual/english-v3.0
   - Python: BGE (BAAI/bge-reranker-base)

### 2.4 自動リライト（node_auto_rewrite - 未実装）

#### Dify v3の処理
```
入力:
  - 元の記事テキスト
  - 一貫性スコア
  - 問題点リスト
  - 修正案

処理:
  - gpt-4o (temp: 0.5) で完全リライト
  - STYLE_PROFILEに完全適合させる

出力:
  - リライト済み記事テキスト
```

#### 現在の実装
- StyleCheckerChainは問題点と修正提案を返すのみ
- 実際のリライトは未実装
- `/verify` エンドポイントで検証結果を返すだけ

#### 必要な実装
```python
class AutoRewriteChain:
    """文体チェック結果を反映して記事をリライト"""
    def rewrite(
        self,
        article_text: str,
        style_check_result: StyleCheckResult,
        style_profile: str
    ) -> str:
```

### 2.5 最終整形（node_final_format - 部分的差分）

#### Dify v3のメタ情報
```
- 記事カテゴリ（日本語）
- テーマ
- 総文字数（目標との比較）
- [要確認]タグの箇所数
- 文体一貫性スコア（%）
- 事実検証信頼度（%）
```

#### 現在の実装（ArticleDraft.to_markdown）
```python
# タイトル、リード、本文、締めをMarkdown化
# メタ情報の付与は限定的
```

#### 差分
- 目標文字数との比較が未実装
- 文体一貫性スコアの出力が未実装
- 事実検証信頼度の出力が未実装
- 「次のステップ」案内が未実装

---

## 3. 実装計画

### Phase 1: 入力処理の拡張（優先度: 高）

#### 1.1 ParsedInputモデルの拡張

**ファイル**: `src/chains/input_parser.py`

```python
class ParsedInput(BaseModel):
    # 既存フィールド
    theme: str
    key_points: list[str]
    interview_quotes: list[dict]  # {speaker, quote}
    data_facts: list[str]
    keywords: list[str]
    missing_info: list[str]

    # 新規追加（Dify v3互換）
    audience: str = ""           # 想定読者
    goal: str = ""               # 記事の目的
    desired_length: int = 2000   # 希望文字数
```

#### 1.2 プロンプト修正

抽出項目に `audience`, `goal`, `desired_length` を追加。

---

### Phase 2: クエリ生成チェーンの追加（優先度: 中）

#### 2.1 新規チェーン作成

**ファイル**: `src/chains/query_generator.py`

```python
class QueryGeneratorChain:
    """カテゴリに最適化された検索クエリを生成"""

    def __init__(self, llm: BaseChatModel = None):
        self.llm = llm or get_llm(temperature=0.3)
        self.prompt = ChatPromptTemplate.from_messages([...])

    def generate(
        self,
        parsed_input: ParsedInput,
        category: ArticleType
    ) -> str:
        """
        入力情報からカテゴリに最適化された検索クエリを生成

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
```

---

### Phase 3: 文体プロファイルKBの実装（優先度: 高）

#### 3.1 データベーススキーマ拡張

**ファイル**: `schemas/schema.sql`

```sql
-- 文体プロファイルテーブル追加
CREATE TABLE style_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article_type article_type_enum NOT NULL,
    profile_type VARCHAR(20) NOT NULL,  -- 'profile' or 'excerpt'
    content TEXT NOT NULL,
    embedding vector(768),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_type_profile
        UNIQUE (article_type, profile_type)
        WHERE profile_type = 'profile'
);

CREATE INDEX idx_style_profiles_type ON style_profiles(article_type, profile_type);
CREATE INDEX idx_style_profiles_embedding ON style_profiles
    USING ivfflat (embedding vector_cosine_ops);
```

#### 3.2 StyleProfileRetriever実装

**ファイル**: `src/retriever/style_retriever.py`

```python
class StyleProfileRetriever:
    """文体プロファイルと抜粋を検索"""

    def retrieve_profile(self, article_type: ArticleType) -> str:
        """
        カテゴリの文体プロファイル（ルール定義）を取得
        top_k=1
        """

    def retrieve_excerpts(
        self,
        theme: str,
        article_type: ArticleType,
        top_k: int = 5
    ) -> list[str]:
        """
        テーマに類似した文体抜粋を取得
        """
```

#### 3.3 文体プロファイルデータの準備

各カテゴリの文体ルールを定義したドキュメントを作成・登録。

```markdown
# インタビュー記事 文体プロファイル

## 語尾パターン
- 〜です、〜ですね、〜なんです
- 親しみやすさを重視

## トーン
- カジュアル寄り
- インタビュイーの人柄が伝わる

## 一人称
- 私（インタビュアー）
- インタビュイーは名前で呼ぶ

## 構成パターン
1. 人物紹介
2. きっかけ・背景
3. 現在の仕事・活動
4. 今後の展望

## 特徴的表現
- 「〜について聞いてみました」
- 「〇〇さんはこう語ります」
```

---

### Phase 4: 自動リライトチェーンの実装（優先度: 中）

#### 4.1 新規チェーン作成

**ファイル**: `src/chains/auto_rewrite.py`

```python
class AutoRewriteChain:
    """文体チェック結果を反映して記事をリライト"""

    def __init__(self, llm: BaseChatModel = None):
        self.llm = llm or get_llm(temperature=0.5)

    def rewrite(
        self,
        article_text: str,
        style_check_result: StyleCheckResult,
        style_profile: str
    ) -> RewriteResult:
        """
        文体問題を修正したリライト版を生成

        Returns:
            RewriteResult:
                rewritten_text: str
                changes_made: list[str]
        """
```

#### 4.2 パイプラインへの統合

**ファイル**: `src/chains/article_chain.py`

```python
class ArticleGenerationPipeline:
    def generate(self, input_material: str) -> ArticleDraft:
        # ... 既存処理 ...

        # Phase 7: 品質保証パイプライン
        style_check = self.style_checker.check(draft, style_profile)

        if style_check.consistency_score < 0.8:
            # 自動リライト実行
            rewrite_result = self.auto_rewriter.rewrite(
                draft.to_markdown(),
                style_check,
                style_profile
            )
            draft = self._parse_rewritten_draft(rewrite_result)

        # ハルシネーション検知...
```

---

### Phase 5: 最終整形の拡張（優先度: 低）

#### 5.1 ArticleDraftモデルの拡張

**ファイル**: `src/chains/article_chain.py`

```python
class ArticleDraft(BaseModel):
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

- **記事カテゴリ**: {category_ja[self.article_type]}
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

### Phase 6: Rerankモデルの選択肢追加（優先度: 低）

#### 6.1 Cohere Rerankの追加

**ファイル**: `src/retriever/reranker.py`

```python
class CohereReranker:
    """Cohere Rerank API を使用した再ランカー"""

    def __init__(self, model: str = "rerank-multilingual-v3.0"):
        self.client = cohere.Client(api_key=settings.cohere_api_key)
        self.model = model

    def rerank(
        self,
        query: str,
        documents: list[Document],
        top_k: int = 5
    ) -> list[Document]:
        results = self.client.rerank(
            model=self.model,
            query=query,
            documents=[d.page_content for d in documents],
            top_n=top_k
        )
        # スコア付きで返却
```

#### 6.2 設定での切り替え

**ファイル**: `src/config.py`

```python
class Settings(BaseSettings):
    reranker_type: str = "bge"  # "bge" or "cohere"
    cohere_api_key: str = ""
    cohere_rerank_model: str = "rerank-multilingual-v3.0"
```

---

## 4. 実装優先順位

```
┌─────────────────────────────────────────────────────┐
│ Phase 1: 入力処理の拡張              [優先度: 高]    │
│   - ParsedInput に audience, goal, desired_length   │
│   - 約1日                                           │
├─────────────────────────────────────────────────────┤
│ Phase 3: 文体プロファイルKB           [優先度: 高]    │
│   - DBスキーマ追加                                   │
│   - StyleProfileRetriever 実装                      │
│   - 文体プロファイルデータ作成                        │
│   - 約2-3日                                          │
├─────────────────────────────────────────────────────┤
│ Phase 2: クエリ生成チェーン           [優先度: 中]    │
│   - QueryGeneratorChain 実装                        │
│   - パイプライン統合                                 │
│   - 約1日                                           │
├─────────────────────────────────────────────────────┤
│ Phase 4: 自動リライト                [優先度: 中]    │
│   - AutoRewriteChain 実装                           │
│   - パイプライン統合                                 │
│   - 約1-2日                                          │
├─────────────────────────────────────────────────────┤
│ Phase 5: 最終整形の拡張              [優先度: 低]    │
│   - メタ情報出力                                     │
│   - 約0.5日                                          │
├─────────────────────────────────────────────────────┤
│ Phase 6: Cohere Rerank対応           [優先度: 低]    │
│   - Cohere API統合                                   │
│   - 設定での切り替え                                 │
│   - 約1日                                           │
└─────────────────────────────────────────────────────┘

合計: 約7-9日
```

---

## 5. 実装後のアーキテクチャ

```
[ユーザー入力]
       │
       ▼
┌─────────────────┐
│ InputParserChain│  ← 拡張: audience, goal, desired_length
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ArticleClassifier│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│QueryGeneratorChain│  ← 新規: カテゴリ別クエリ生成
└────────┬────────┘
         │
         ▼
┌──────────────────────────────────────────────────┐
│ 並列検索                                          │
│                                                  │
│  ArticleRetriever    StyleProfileRetriever       │
│  (CONTENT_KB)        (STYLE_PROFILE + EXCERPTS)  │
│                      ← 新規                       │
└──────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│OutlineGenerator │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ContentGenerators│  Title, Lead, Section, Closing
└────────┬────────┘
         │
         ▼
┌──────────────────────────────────────────────────┐
│ 品質保証パイプライン                               │
│                                                  │
│  StyleChecker → AutoRewriteChain → HallucinationDetector
│                 ← 新規                            │
└──────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│ 最終整形        │  ← 拡張: メタ情報付き出力
│ (to_markdown_   │
│  with_meta)     │
└─────────────────┘
```

---

## 6. テスト計画

### 6.1 ユニットテスト

```python
# tests/test_query_generator.py
def test_query_generator_interview():
    """インタビューカテゴリのクエリ生成"""

def test_query_generator_event():
    """イベントカテゴリのクエリ生成"""

# tests/test_style_retriever.py
def test_retrieve_profile():
    """文体プロファイル取得"""

def test_retrieve_excerpts():
    """文体抜粋取得"""

# tests/test_auto_rewrite.py
def test_rewrite_with_issues():
    """問題ありの場合のリライト"""

def test_rewrite_no_issues():
    """問題なしの場合（変更なし）"""
```

### 6.2 統合テスト

```python
# tests/test_pipeline_integration.py
def test_full_pipeline_with_style_profile():
    """文体プロファイルを使用したフルパイプライン"""

def test_pipeline_with_auto_rewrite():
    """自動リライトを含むパイプライン"""
```

### 6.3 E2Eテスト

```python
# tests/test_api_e2e.py
def test_generate_endpoint_full_flow():
    """/generate エンドポイントのフルフロー"""
    # 入力 → クエリ生成 → 検索 → 生成 → リライト → 出力
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

### 7.2 設定更新

```bash
# .env に追加
COHERE_API_KEY=xxx  # Phase 6で使用
```

### 7.3 依存関係追加

```bash
# pyproject.toml に追加
uv add cohere  # Phase 6で使用
```

---

## 8. 互換性考慮

### 8.1 既存API互換性

- `/generate` エンドポイントの入出力形式は維持
- 新規メタ情報は `markdown` フィールドに追加
- 既存クライアントへの影響なし

### 8.2 段階的ロールアウト

```python
# config.py
class Settings:
    # 新機能フラグ
    enable_query_generator: bool = False
    enable_style_profile_kb: bool = False
    enable_auto_rewrite: bool = False
```

機能フラグで段階的に有効化可能。

---

## 9. 参考資料

- [Dify v3ワークフロー仕様](./DIFY_WORKFLOW_V3.md)
- [現在の実装アーキテクチャ](./RAG_SYSTEM_BLUEPRINT.md)
- [LangChain LCEL ドキュメント](./LANGCHAIN_REFERENCES.md)
