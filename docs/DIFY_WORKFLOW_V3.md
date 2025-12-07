# note記事ドラフト生成ワークフロー v3

Difyプラットフォーム上で動作するnote記事自動生成ワークフローの技術ドキュメント。

## 概要

### 目的
株式会社ギグーの採用広報note記事のドラフトを自動生成するワークフロー。

### v3の特徴
1. **カテゴリ別ナレッジベース分離** - CONTENT_KB × STYLE_KB の分離構成
2. **2層スタイル取得** - STYLE_PROFILE（文体ルール）+ STYLE_EXCERPTS（文体見本）
3. **2段階生成** - アウトライン生成 → 本文生成
4. **文体整合性チェック** - 自動リライト機能付き
5. **ハルシネーション検知** - [要確認]タグ自動挿入

### 対象
株式会社ギグー 採用広報note記事

---

## 対応カテゴリ

| カテゴリ | 説明 | 用途例 |
|---------|------|--------|
| `interview` | 社員インタビュー | 入社エントリ、人物フォーカス記事 |
| `event` | イベントレポート | 勉強会、セミナー報告 |
| `announcement` | お知らせ・リリース | 新サービス発表、プレスリリース |
| `story` | カルチャー・ストーリー | 企業文化、制度紹介 |

---

## 処理フロー概要

```
[ユーザー入力]
       │
       ▼
┌─────────────────┐
│ 1. 素材入力      │  node_start
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 2. 入力情報収集  │  node_collect_inputs (gpt-4o)
│   カテゴリ/テーマ │
│   読者/目的抽出  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 3. カテゴリ分岐  │  node_category_switch
└──┬──┬──┬──┬─────┘
   │  │  │  │
   ▼  ▼  ▼  ▼
┌──────────────────────────────────────────────────┐
│ 4. クエリ生成（カテゴリ別並列）                      │
│  interview / event / announcement / story        │
│  (gpt-4o-mini)                                   │
└──────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────┐
│ 5. ナレッジ検索（3層 × 4カテゴリ = 12ノード）        │
│                                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│  │ CONTENT_KB  │→│STYLE_PROFILE│→│STYLE_EXCERPTS│ │
│  │  (top_k=15) │ │  (top_k=1)  │ │  (top_k=5)  │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ │
└──────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│ 6. 結果マージ    │  node_merge_results (JavaScript)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 7. アウトライン  │  node_generate_outline (gpt-4o)
│    生成         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 8. 本文生成      │  node_generate_article (gpt-4o)
└────────┬────────┘
         │
         ▼
┌──────────────────────────────────────────────────┐
│ 9. 品質保証パイプライン                            │
│                                                  │
│  文体チェック → 自動リライト → ハルシネーション検知  │
│  (gpt-4o-mini)   (gpt-4o)     (gpt-4o-mini)      │
│                      │                          │
│                      ▼                          │
│               [要確認]タグ挿入                    │
└──────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│10. 最終整形      │  node_final_format (JavaScript)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│11. ドラフト出力  │  node_answer
└─────────────────┘
```

---

## 各フェーズの詳細

### フェーズ1: 入力処理

#### node_start（素材入力）
- **タイプ**: start
- **役割**: ユーザーから記事素材と設定を受け取る開始ノード
- **入力**: ユーザーが提供する記事素材（テーマ、メモ、インタビュー内容等）

#### node_collect_inputs（入力情報収集）
- **タイプ**: LLM
- **モデル**: gpt-4o (temperature: 0.2)
- **役割**: ユーザー入力からカテゴリ、テーマ、読者、目的、希望文字数を抽出して構造化

**抽出項目:**
| 項目 | 説明 |
|------|------|
| `category` | 記事カテゴリ（interview/event/announcement/story） |
| `theme` | 記事のテーマ・主旨（1文で要約） |
| `audience` | 想定読者 |
| `goal` | 記事の目的 |
| `desired_length` | 希望文字数（デフォルト: 2000） |
| `key_points` | 重要ポイント |
| `interview_quotes` | インタビュー発言（speaker + quote） |
| `data_facts` | 具体的な数値やデータ |
| `keywords` | 検索用キーワード（5-10個） |

---

### フェーズ2: カテゴリ分岐

#### node_category_switch（カテゴリ分岐）
- **タイプ**: if-else
- **役割**: カテゴリに応じて適切なナレッジベースへ振り分け
- **分岐条件**: `node_collect_inputs.structured_output.category`

| 条件値 | 出力ハンドル |
|--------|-------------|
| `interview` | interview |
| `event` | event |
| `announcement` | announcement |
| `story` | story |

---

### フェーズ3: クエリ生成

各カテゴリ専用の検索クエリを生成（4ノード並列）。

| ノード | カテゴリ | モデル |
|--------|---------|--------|
| node_query_gen_interview | インタビュー | gpt-4o-mini (temp: 0.3) |
| node_query_gen_event | イベントレポート | gpt-4o-mini (temp: 0.3) |
| node_query_gen_announcement | アナウンスメント | gpt-4o-mini (temp: 0.3) |
| node_query_gen_story | カルチャー | gpt-4o-mini (temp: 0.3) |

**入力変数:**
- `theme`, `audience`, `goal`, `keywords` （node_collect_inputsから）

**出力:**
- `search_query`: 検索クエリ（スペース区切り）

---

### フェーズ4: ナレッジ検索

3種類のナレッジベース × 4カテゴリ = 12ノード

#### CONTENT_KB（コンテンツナレッジベース）

過去記事のコンテンツを検索。

| ノード | カテゴリ | データセット |
|--------|---------|-------------|
| node_content_kb_interview | インタビュー | KB_interview_all |
| node_content_kb_event | イベント | KB_event_all |
| node_content_kb_announcement | アナウンスメント | KB_announcement_all |
| node_content_kb_story | カルチャー | KB_story_all |

**検索設定:**
- `retrieval_mode`: multiple
- `top_k`: 15
- `score_threshold`: 0.2
- `reranking_model`: cohere/rerank-multilingual-v3.0
- `vector_weight`: 0.7 / `keyword_weight`: 0.3
- `embedding`: text-embedding-3-large

#### STYLE_PROFILE（文体プロファイル）

文体ルール定義を取得。

| ノード | カテゴリ |
|--------|---------|
| node_style_profile_interview | インタビュー |
| node_style_profile_event | イベント |
| node_style_profile_announcement | アナウンスメント |
| node_style_profile_story | カルチャー |

**検索設定:**
- `top_k`: 1
- `score_threshold`: 0.1
- `reranking_model`: cohere/rerank-english-v3.0
- クエリ: `category`（カテゴリ名そのもの）

#### STYLE_EXCERPTS（文体抜粋）

文体見本となる記事抜粋を取得。

| ノード | カテゴリ |
|--------|---------|
| node_style_excerpts_interview | インタビュー |
| node_style_excerpts_event | イベント |
| node_style_excerpts_announcement | アナウンスメント |
| node_style_excerpts_story | カルチャー |

**検索設定:**
- `top_k`: 5
- `score_threshold`: 0.1
- `reranking_model`: cohere/rerank-multilingual-v3.0
- クエリ: `theme`（テーマで類似記事を検索）

---

### フェーズ5: 結果マージ

#### node_merge_results（結果マージ）
- **タイプ**: code (JavaScript)
- **役割**: カテゴリに応じて適切な検索結果を選択・統合

**入力変数（12個）:**
- `content_interview/event/announcement/story`
- `style_profile_interview/event/announcement/story`
- `style_excerpts_interview/event/announcement/story`

**出力:**
- `content_chunks`: 選択されたコンテンツ
- `style_profile`: 選択された文体プロファイル
- `style_excerpts`: 選択された文体抜粋

---

### フェーズ6: 2段階生成

#### node_generate_outline（アウトライン生成）
- **タイプ**: LLM
- **モデル**: gpt-4o (temperature: 0.5)
- **役割**: STYLE_PROFILEに従いH2/H3見出し構成を生成

**入力コンテキスト:**
- STYLE_PROFILE（文体ルール）
- STYLE_EXCERPTS（文体見本）
- CONTENT_CHUNKS（参照コンテンツ）

**出力（structured_output）:**
```json
{
  "headings": [
    {
      "level": "H2/H3",
      "title": "見出しテキスト",
      "content_summary": "セクション概要",
      "key_sources": ["使用する情報"],
      "target_length": 500
    }
  ],
  "total_target_length": 2000
}
```

#### node_generate_article（本文生成）
- **タイプ**: LLM
- **モデル**: gpt-4o (temperature: 0.6)
- **役割**: アウトラインを維持しながらSTYLE_PROFILEに忠実に本文を生成

**制約:**
- 文体: STYLE_PROFILEに忠実
- 長さ: 希望文字数程度
- 過剰な煽り禁止、丁寧で親しみやすい調子
- CONTENT_CHUNKSの内容のみを利用
- 外部知識を使わない

**出力形式:**
- タイトル案（3つ）
- リード文（100-150字）
- 本文（見出しを含む）
- 締めの文章

---

### フェーズ7: 品質保証

#### node_style_check（文体整合性チェック）
- **タイプ**: LLM
- **モデル**: gpt-4o-mini (temperature: 0.2)
- **役割**: STYLE_PROFILEとの一致度を判定し、ズレを指摘

**出力（structured_output）:**
```json
{
  "consistency_score": 0.85,
  "issues": [
    {
      "location": "第2段落",
      "description": "敬語が不統一",
      "severity": "medium"
    }
  ],
  "corrected_sections": [
    {
      "original": "修正前テキスト",
      "corrected": "修正後テキスト",
      "reason": "修正理由"
    }
  ]
}
```

#### node_auto_rewrite（自動リライト）
- **タイプ**: LLM
- **モデル**: gpt-4o (temperature: 0.5)
- **役割**: 文体チェック結果を反映して本文を完全リライト

**入力:**
- 元の記事テキスト
- 一貫性スコア
- 問題点リスト
- 修正案

#### node_hallucination_detect（ハルシネーション検知）
- **タイプ**: LLM
- **モデル**: gpt-4o-mini (temperature: 0.1)
- **役割**: CONTENT_CHUNKSにない事実を検出

**チェック対象:**
- 具体的な数値、日付、固有名詞
- 事実の主張（〇〇した、〇〇である）
- 引用やコメント

**出力（structured_output）:**
```json
{
  "unverified_claims": [
    {
      "claim": "該当する主張",
      "reason": "検証不能な理由",
      "suggested_tag": "推奨される確認内容"
    }
  ],
  "confidence": 0.9
}
```

#### node_tag_inserter（タグ挿入）
- **タイプ**: code (JavaScript)
- **役割**: 検証不能な主張に`[要確認: xxx]`タグを挿入

**出力:**
- `tagged_article`: タグ挿入済み記事
- `tag_count`: 挿入されたタグ数

---

### フェーズ8: 出力

#### node_final_format（最終整形）
- **タイプ**: code (JavaScript)
- **役割**: 最終的なドラフトをメタ情報付きで整形

**出力に含まれるメタ情報:**
- 記事カテゴリ（日本語表記）
- テーマ
- 総文字数（目標との比較）
- [要確認]タグの箇所数
- 文体一貫性スコア（%）
- 事実検証信頼度（%）

**次のステップ案内:**
1. [要確認] タグがある箇所は事実確認
2. タイトルは3案から選択または調整
3. 必要に応じて文章を微調整

#### node_answer（ドラフト出力）
- **タイプ**: answer
- **役割**: 最終ドラフトをユーザーに出力

---

## ナレッジベース構成

### コンテンツKB（KB_xxx_all）

カテゴリ別の過去記事コンテンツを格納。

| KB名 | 用途 |
|------|------|
| KB_interview_all | インタビュー記事全文 |
| KB_event_all | イベントレポート記事全文 |
| KB_announcement_all | アナウンスメント記事全文 |
| KB_story_all | カルチャー/ストーリー記事全文 |

### スタイルKB（KB_xxx_style）

文体ルールと見本を格納。2つのドキュメントタイプを含む。

| タイプ | 説明 | 取得件数 |
|--------|------|---------|
| `style_profile` | 文体ルール定義 | top_k=1 |
| `style_excerpt` | 文体見本（記事抜粋） | top_k=5 |

---

## 使用モデル一覧

### LLMモデル

| モデル | 用途 | temperature |
|--------|------|-------------|
| gpt-4o | 入力情報収集 | 0.2 |
| gpt-4o | アウトライン生成 | 0.5 |
| gpt-4o | 本文生成 | 0.6 |
| gpt-4o | 自動リライト | 0.5 |
| gpt-4o-mini | クエリ生成 | 0.3 |
| gpt-4o-mini | 文体整合性チェック | 0.2 |
| gpt-4o-mini | ハルシネーション検知 | 0.1 |

### Embeddingモデル

| モデル | 用途 |
|--------|------|
| text-embedding-3-large | ベクトル検索 |

### Rerankingモデル

| モデル | 用途 |
|--------|------|
| cohere/rerank-multilingual-v3.0 | コンテンツ検索、文体抜粋検索 |
| cohere/rerank-english-v3.0 | 文体プロファイル検索 |

---

## 出力形式

最終出力には以下が含まれる：

### 記事本文
- タイトル案（3つ）
- リード文（100-150字）
- 本文（H2/H3見出し付き）
- 締めの文章

### メタ情報
```
---

### メタ情報

- **記事カテゴリ**: インタビュー
- **テーマ**: 〇〇について
- **総文字数**: 約2100字（目標: 2000字）
- **[要確認]タグ**: 2箇所
- **文体一貫性スコア**: 85%
- **事実検証信頼度**: 90%

### 次のステップ

1. [要確認] タグがある箇所は事実確認してください
2. タイトルは3案から選択または調整してください
3. 必要に応じて文章を微調整してください
```

---

## 依存プラグイン

| プラグイン | バージョン |
|-----------|-----------|
| langgenius/openai | 0.2.7 |
| langgenius/cohere | 0.0.8 |
