# プロンプト評価・改善サイクル戦略

このドキュメントでは、RAGシステムのプロンプトを体系的に評価・改善するための方針と実装計画を定義する。

## 背景と課題

### 現状

- 10個以上のLangChainチェーンが存在（ArticleClassifier, TitleGenerator, SectionGenerator等）
- プロンプトはPythonコード内に直接埋め込み
- プロンプト変更の影響を事前に評価する仕組みがない
- 本番環境でのプロンプト品質をモニタリングする手段がない

### 現状のワークフロー（問題あり）

```
プロンプト変更 → デプロイ → 本番で確認 → 問題発覚 → 修正
                    （フィードバックループが長すぎる）
```

### 目指すべきワークフロー

```
プロンプト変更 → 自動評価(Evals) → 結果確認 → 本番デプロイ
                                        ↑
                          ログ分析・ユーザーフィードバック
```

---

## 評価・改善の3つの柱

### 1. オフライン評価（Evals）

プロンプト変更前に品質を検証する仕組み。

### 2. オンラインモニタリング

本番環境でのプロンプト実行をトレース・分析する仕組み。

### 3. プロンプトバージョン管理

プロンプトの変更履歴を追跡し、ロールバック可能にする仕組み。

---

## Phase 1: オフライン評価基盤の構築

### 目的

プロンプト変更時に自動テストで品質を検証できるようにする。

### 実装内容

#### 1.1 ゴールデンデータセットの作成

各チェーンに対して、入力と期待される出力のペアを作成する。

```
tests/
  evals/
    datasets/
      classifier_golden.json      # 記事分類の正解データ
      title_golden.json           # タイトル生成の良い例
      section_golden.json         # セクション生成の良い例
      hallucination_golden.json   # ハルシネーション検出の正解データ
    conftest.py
    test_classifier_eval.py
    test_content_quality_eval.py
    test_hallucination_eval.py
```

#### 1.2 データセットのフォーマット

```json
// classifier_golden.json
{
  "version": "1.0",
  "description": "ArticleClassifierChainの評価用データセット",
  "cases": [
    {
      "id": "case_001",
      "description": "新機能リリースの告知記事",
      "input": {
        "theme": "新機能「AIアシスタント」をリリースしました",
        "key_points": ["AI機能追加", "業務効率化", "無料で利用可能"],
        "people": [],
        "keywords": ["リリース", "新機能", "AI"],
        "interview_quotes": []
      },
      "expected": {
        "article_type": "ANNOUNCEMENT",
        "min_confidence": 0.8
      }
    }
  ]
}
```

#### 1.3 評価スクリプトの実装

```python
# tests/evals/test_classifier_eval.py
import json
import pytest
from src.chains.article_classifier import ArticleClassifierChain
from src.chains.input_parser import ParsedInput

def load_golden_data(name: str) -> list[dict]:
    with open(f"tests/evals/datasets/{name}_golden.json") as f:
        data = json.load(f)
    return data["cases"]

@pytest.mark.eval
@pytest.mark.parametrize("case", load_golden_data("classifier"), ids=lambda c: c["id"])
def test_classifier_accuracy(case):
    """ArticleClassifierの分類精度を評価"""
    classifier = ArticleClassifierChain()
    parsed_input = ParsedInput(**case["input"])

    result = classifier.classify(parsed_input)

    assert result.article_type == case["expected"]["article_type"], \
        f"Expected {case['expected']['article_type']}, got {result.article_type}"
    assert result.confidence >= case["expected"]["min_confidence"], \
        f"Confidence {result.confidence} below threshold {case['expected']['min_confidence']}"
```

#### 1.4 評価タイプ別の手法

| チェーン | 評価タイプ | 評価方法 |
|---------|-----------|---------|
| ArticleClassifier | 正解率 | ゴールデンデータとの完全一致 |
| TitleGenerator | LLM-as-Judge | 別のLLMで品質スコアリング（1-5点） |
| LeadGenerator | LLM-as-Judge + ルール | 文字数チェック + 品質スコア |
| SectionGenerator | LLM-as-Judge + ルール | 文体一致度 + ハルシネーションチェック |
| HallucinationDetector | 正解率 | 検出すべき箇所の再現率・適合率 |

#### 1.5 LLM-as-Judge の実装例

```python
# tests/evals/judges.py
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_vertexai import ChatVertexAI

JUDGE_PROMPT = """あなたは記事タイトルの品質を評価する専門家です。

## 評価対象タイトル
{title}

## 記事のテーマ
{theme}

## 評価基準
1. 魅力度: クリックしたくなるか（1-5点）
2. 適切性: テーマを適切に表現しているか（1-5点）
3. 長さ: 適切な長さか（1-5点）

## 出力形式
JSON形式で出力:
{{"attractiveness": N, "relevance": N, "length": N, "total": N, "reason": "..."}}
"""

class TitleJudge:
    def __init__(self):
        self.llm = ChatVertexAI(model="gemini-1.5-flash", temperature=0)
        self.prompt = ChatPromptTemplate.from_template(JUDGE_PROMPT)
        self.chain = self.prompt | self.llm

    def evaluate(self, title: str, theme: str) -> dict:
        result = self.chain.invoke({"title": title, "theme": theme})
        return json.loads(result.content)
```

#### 1.6 CI/CD統合

```yaml
# .github/workflows/eval.yml
name: Prompt Evaluation

on:
  pull_request:
    paths:
      - 'src/chains/**'
      - 'tests/evals/**'

jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: uv sync
      - name: Run evaluations
        run: uv run pytest tests/evals/ -v --tb=short
        env:
          GOOGLE_APPLICATION_CREDENTIALS: ${{ secrets.GCP_SA_KEY }}
```

### 成果物

- [ ] `tests/evals/datasets/` にゴールデンデータセット（各10-20件）
- [ ] `tests/evals/test_*.py` 評価スクリプト
- [ ] `tests/evals/judges.py` LLM-as-Judge実装
- [ ] CI/CDワークフロー設定

### 推定工数

- ゴールデンデータセット作成: 2-3日
- 評価スクリプト実装: 1-2日
- CI/CD統合: 0.5日

---

## Phase 2: オンラインモニタリング（LangSmith導入）

### 目的

本番環境でのプロンプト実行をトレース・可視化し、問題の早期発見を可能にする。

### 実装内容

#### 2.1 LangSmith設定

```python
# src/config.py に追加
class Settings(BaseSettings):
    # ... 既存設定 ...

    # LangSmith設定
    langchain_tracing_v2: bool = Field(default=True, alias="LANGCHAIN_TRACING_V2")
    langchain_api_key: str | None = Field(default=None, alias="LANGCHAIN_API_KEY")
    langchain_project: str = Field(default="etude-rag2", alias="LANGCHAIN_PROJECT")
```

```bash
# .env に追加
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls_xxx
LANGCHAIN_PROJECT=etude-rag2-dev
```

#### 2.2 トレースで記録される情報

- 各チェーンの入出力
- レイテンシ（処理時間）
- トークン使用量
- エラー・例外
- カスタムメタデータ（記事タイプ、リクエストID等）

#### 2.3 カスタムメタデータの追加

```python
from langchain_core.runnables import RunnableConfig

def generate_article(input_data: dict) -> dict:
    config = RunnableConfig(
        metadata={
            "request_id": str(uuid.uuid4()),
            "article_type": input_data.get("article_type"),
            "user_id": input_data.get("user_id"),
        },
        tags=["production", "article-generation"],
    )

    result = pipeline.invoke(input_data, config=config)
    return result
```

#### 2.4 LangSmithダッシュボードで確認できること

- プロンプト実行の成功/失敗率
- 平均レイテンシの推移
- エラーの詳細とスタックトレース
- 特定の入力パターンでの出力品質

### 成果物

- [ ] LangSmith APIキー取得・Secret Manager登録
- [ ] `src/config.py` にLangSmith設定追加
- [ ] 各チェーンにカスタムメタデータ追加
- [ ] モニタリングダッシュボード設定

### 推定工数

- 初期設定: 0.5日
- メタデータ追加: 1日
- ダッシュボード設定: 0.5日

---

## Phase 3: ユーザーフィードバック収集

### 目的

実際のユーザーからのフィードバックを収集し、プロンプト改善に活用する。

### 実装内容

#### 3.1 フィードバックAPIの追加

```python
# src/api/main.py に追加
from pydantic import BaseModel

class FeedbackRequest(BaseModel):
    request_id: str
    feedback_type: Literal["positive", "negative"]
    feedback_category: str | None = None  # "hallucination", "style", "content", "other"
    comment: str | None = None

@app.post("/feedback")
async def submit_feedback(feedback: FeedbackRequest):
    """生成結果に対するユーザーフィードバックを受け付ける"""
    # BigQueryまたはPostgreSQLに保存
    await save_feedback(feedback)

    # LangSmithにもフィードバックを送信（トレースと紐付け）
    if settings.langchain_api_key:
        client = Client()
        client.create_feedback(
            run_id=feedback.request_id,
            key="user_feedback",
            score=1 if feedback.feedback_type == "positive" else 0,
            comment=feedback.comment,
        )

    return {"status": "ok"}
```

#### 3.2 UIへのフィードバックボタン追加

```python
# src/ui/app.py の生成結果表示部分に追加
col1, col2 = st.columns(2)
with col1:
    if st.button("👍 良い", key=f"good_{request_id}"):
        send_feedback(request_id, "positive")
        st.success("フィードバックありがとうございます！")
with col2:
    if st.button("👎 改善が必要", key=f"bad_{request_id}"):
        send_feedback(request_id, "negative")
        st.info("フィードバックを受け付けました。改善に活用します。")
```

#### 3.3 フィードバックデータの保存先

**オプションA: PostgreSQL（シンプル）**

```sql
-- schemas/schema.sql に追加
CREATE TABLE feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL,
    feedback_type VARCHAR(20) NOT NULL,
    feedback_category VARCHAR(50),
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_feedback_request_id ON feedback(request_id);
CREATE INDEX idx_feedback_created_at ON feedback(created_at);
```

**オプションB: BigQuery（大規模分析向け）**

```sql
-- BigQueryテーブル定義
CREATE TABLE `project.dataset.feedback` (
    request_id STRING,
    feedback_type STRING,
    feedback_category STRING,
    comment STRING,
    created_at TIMESTAMP
)
PARTITION BY DATE(created_at);
```

### 成果物

- [ ] `/feedback` APIエンドポイント
- [ ] UIにフィードバックボタン追加
- [ ] フィードバック保存テーブル（PostgreSQL or BigQuery）
- [ ] LangSmithとの連携

### 推定工数

- API実装: 0.5日
- UI実装: 0.5日
- データベース設定: 0.5日

---

## Phase 4: プロンプトバージョン管理（将来検討）

### 目的

プロンプトの変更履歴を追跡し、問題発生時にロールバック可能にする。

### 実装オプション

#### オプションA: ファイルベース管理

```
prompts/
  article_classifier/
    v1.0.0/
      system.txt
      user.txt
    v1.1.0/
      system.txt
      user.txt
  title_generator/
    v1.0.0/
      system.txt
```

```python
# src/prompts/loader.py
def load_prompt(chain_name: str, version: str = "latest") -> tuple[str, str]:
    """指定バージョンのプロンプトを読み込む"""
    base_path = Path("prompts") / chain_name
    if version == "latest":
        version = get_latest_version(base_path)

    system = (base_path / version / "system.txt").read_text()
    user = (base_path / version / "user.txt").read_text()
    return system, user
```

#### オプションB: LangSmith Hub

```python
from langsmith import hub

# プロンプトをHubから取得
prompt = hub.pull("etude-rag2/article-classifier:v1.1")

# チェーンで使用
chain = prompt | llm | parser
```

### 現時点での推奨

Phase 1-3を優先し、プロンプトバージョン管理は運用が安定してから検討する。
現状はGitでのコード管理で十分追跡可能。

---

## ツール比較

| ツール | 用途 | 導入コスト | このプロジェクトとの相性 |
|--------|------|-----------|------------------------|
| **LangSmith** | トレース + Evals + Hub | 低 | ◎ LangChain使用中なので最適 |
| **RAGAS** | RAG特化評価 | 中 | ○ Retriever評価に有用 |
| **DeepEval** | 汎用LLM評価 | 中 | ○ 多様な評価メトリクス |
| **Phoenix (Arize)** | トレース + 分析 | 中 | ○ OSS代替として検討可 |
| **BigQuery** | ログ分析 | 中 | ○ GCP統合済み |
| **pytest + 自作** | 基本評価 | 低 | ◎ すぐ始められる |

---

## 実装ロードマップ

```
Phase 1: オフライン評価基盤
├── Week 1-2: ゴールデンデータセット作成
├── Week 2-3: 評価スクリプト実装
└── Week 3: CI/CD統合

Phase 2: オンラインモニタリング
├── Week 4: LangSmith設定
└── Week 4-5: メタデータ追加・ダッシュボード

Phase 3: ユーザーフィードバック
├── Week 5-6: API・UI実装
└── Week 6: データ保存・分析基盤

Phase 4: プロンプトバージョン管理（将来）
└── 運用安定後に検討
```

---

## 参考リンク

- [LangSmith Documentation](https://docs.smith.langchain.com/)
- [LangSmith Evaluation Guide](https://docs.smith.langchain.com/evaluation)
- [RAGAS Documentation](https://docs.ragas.io/)
- [DeepEval Documentation](https://docs.confident-ai.com/)

---

## 変更履歴

| 日付 | バージョン | 変更内容 |
|------|-----------|---------|
| 2025-12-08 | 1.0 | 初版作成 |
