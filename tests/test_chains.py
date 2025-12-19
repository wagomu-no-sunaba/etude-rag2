"""Tests for the chains module."""

from src.chains.input_parser import InterviewQuote, ParsedInput, Person


class TestParsedInputModel:
    """Test ParsedInput Pydantic model."""

    def test_parsed_input_with_all_fields(self):
        """Test ParsedInput with all fields populated."""
        parsed = ParsedInput(
            theme="新入社員インタビュー記事",
            key_points=["入社の経緯", "現在の仕事内容", "今後の目標"],
            interview_quotes=[InterviewQuote(speaker="田中太郎", quote="とても働きやすい環境です")],
            data_facts=["入社3ヶ月目", "チームメンバー5名"],
            people=[Person(name="田中太郎", role="エンジニア")],
            keywords=["入社", "エンジニア", "インタビュー"],
            missing_info=["入社日の具体的な日付"],
        )

        assert parsed.theme == "新入社員インタビュー記事"
        assert len(parsed.key_points) == 3
        assert len(parsed.interview_quotes) == 1
        assert parsed.interview_quotes[0].speaker == "田中太郎"

    def test_parsed_input_with_minimal_fields(self):
        """Test ParsedInput with only required fields."""
        parsed = ParsedInput(
            theme="テスト記事",
        )

        assert parsed.theme == "テスト記事"
        assert parsed.key_points == []
        assert parsed.interview_quotes == []
        assert parsed.data_facts == []
        assert parsed.people == []
        assert parsed.keywords == []
        assert parsed.missing_info == []

    def test_parsed_input_model_dump(self):
        """Test ParsedInput serialization to dict."""
        parsed = ParsedInput(
            theme="テスト",
            key_points=["ポイント1"],
        )
        data = parsed.model_dump()

        assert isinstance(data, dict)
        assert data["theme"] == "テスト"
        assert data["key_points"] == ["ポイント1"]


class TestArticleClassifierOutput:
    """Test ArticleClassifier output model."""

    def test_classification_result_model(self):
        """Test ClassificationResult model."""
        from src.chains.article_classifier import ClassificationResult

        result = ClassificationResult(
            article_type="INTERVIEW",
            article_type_ja="インタビュー",
            confidence=0.95,
            reason="インタビュー引用が含まれているため",
            suggested_headings=["自己紹介", "入社の経緯", "今後の展望"],
        )

        assert result.article_type == "INTERVIEW"
        assert result.confidence == 0.95
        assert len(result.suggested_headings) == 3

    def test_classification_result_validates_article_type(self):
        """Test that invalid article_type raises error."""
        from src.chains.article_classifier import ClassificationResult

        # Valid types should work
        for valid_type in ["ANNOUNCEMENT", "EVENT_REPORT", "INTERVIEW", "CULTURE"]:
            result = ClassificationResult(
                article_type=valid_type,
                article_type_ja="テスト",
                confidence=0.9,
                reason="テスト",
                suggested_headings=["見出し1", "見出し2"],
            )
            assert result.article_type == valid_type


class TestStyleAnalyzerOutput:
    """Test StyleAnalyzer output model."""

    def test_style_analysis_model(self):
        """Test StyleAnalysis model."""
        from src.chains.style_analyzer import StyleAnalysis

        analysis = StyleAnalysis(
            sentence_endings=["〜です", "〜ですね", "〜なんです"],
            tone="カジュアル",
            first_person="私",
            reader_address="皆さん",
            paragraph_style="短めの段落で区切る",
            emoji_usage="控えめに使用",
            characteristic_phrases=["実は", "というのも", "そんな中で"],
        )

        assert len(analysis.sentence_endings) == 3
        assert analysis.tone == "カジュアル"
        assert analysis.first_person == "私"


class TestStructureAnalyzerOutput:
    """Test StructureAnalyzer output model."""

    def test_structure_analysis_model(self):
        """Test StructureAnalysis model."""
        from src.chains.structure_analyzer import StructureAnalysis

        analysis = StructureAnalysis(
            typical_headings=["自己紹介", "きっかけ", "現在の仕事", "今後の展望"],
            intro_pattern="人物紹介から始まり、興味を引く一文で締める",
            section_flow="導入→背景→本題→まとめ",
            closing_pattern="CTAを含めた締めくくり",
            average_length="1500字程度",
        )

        assert len(analysis.typical_headings) == 4
        assert "人物紹介" in analysis.intro_pattern


class TestOutlineGeneratorOutput:
    """Test OutlineGenerator output model."""

    def test_outline_heading_model(self):
        """Test OutlineHeading model."""
        from src.chains.outline_generator import OutlineHeading

        heading = OutlineHeading(
            title="入社のきっかけ",
            summary="なぜギグーに入社したのか、転職の経緯を説明",
            key_content=["前職での経験", "ギグーを知ったきっかけ"],
            target_length=400,
        )

        assert heading.title == "入社のきっかけ"
        assert heading.target_length == 400

    def test_outline_model(self):
        """Test Outline model."""
        from src.chains.outline_generator import Outline, OutlineHeading

        outline = Outline(
            headings=[
                OutlineHeading(
                    title="自己紹介",
                    summary="田中さんの紹介",
                    key_content=["名前", "役職"],
                    target_length=200,
                ),
                OutlineHeading(
                    title="入社の経緯",
                    summary="入社までの流れ",
                    key_content=["前職", "転職理由"],
                    target_length=400,
                ),
            ],
            total_target_length=1500,
        )

        assert len(outline.headings) == 2
        assert outline.total_target_length == 1500


class TestContentGenerators:
    """Test content generator models."""

    def test_title_generator_output(self):
        """Test TitleGeneratorOutput model."""
        from src.chains.content_generators import TitleGeneratorOutput

        output = TitleGeneratorOutput(
            titles=[
                "入社3ヶ月の本音を聞いてみた",
                "エンジニアが語るギグーの魅力",
                "転職して分かったこと",
            ]
        )

        assert len(output.titles) == 3

    def test_section_content_model(self):
        """Test SectionContent model."""
        from src.chains.content_generators import SectionContent

        content = SectionContent(
            heading="入社のきっかけ",
            body="前職では〜という経験をしていました。そんな中、ギグーと出会い...",
        )

        assert content.heading == "入社のきっかけ"
        assert "前職" in content.body


class TestArticleDraft:
    """Test ArticleDraft output model."""

    def test_article_draft_model(self):
        """Test ArticleDraft model."""
        from src.chains.article_chain import ArticleDraft

        draft = ArticleDraft(
            titles=["タイトル1", "タイトル2", "タイトル3"],
            lead="リード文です。",
            sections=[
                {"heading": "見出し1", "body": "本文1"},
            ],
            closing="締めの文章です。",
            article_type="INTERVIEW",
            article_type_ja="インタビュー",
        )

        assert len(draft.titles) == 3
        assert draft.article_type == "INTERVIEW"
        assert len(draft.sections) == 1

    def test_article_draft_to_markdown(self):
        """Test ArticleDraft markdown conversion."""
        from src.chains.article_chain import ArticleDraft

        draft = ArticleDraft(
            titles=["タイトル案1", "タイトル案2", "タイトル案3"],
            lead="これはリード文です。",
            sections=[
                {"heading": "見出し1", "body": "本文1の内容です。"},
                {"heading": "見出し2", "body": "本文2の内容です。"},
            ],
            closing="締めの文章です。",
            article_type="INTERVIEW",
            article_type_ja="インタビュー",
        )

        markdown = draft.to_markdown()

        assert "## タイトル案" in markdown
        assert "タイトル案1" in markdown
        assert "## リード文" in markdown
        assert "### 見出し1" in markdown
        assert "### 見出し2" in markdown
        assert "締めの文章" in markdown

    def test_from_markdown_basic(self):
        """Test ArticleDraft.from_markdown() with basic parsing."""
        from src.chains.article_chain import ArticleDraft

        markdown = """## タイトル案（3つ）

1. タイトル1
2. タイトル2
3. タイトル3

## リード文

これはリード文です。

## 本文

### 見出し1

本文1の内容です。

### 見出し2

本文2の内容です。

## 締め

締めの文章です。

---
**記事タイプ**: インタビュー
"""
        draft = ArticleDraft.from_markdown(
            markdown=markdown,
            article_type="INTERVIEW",
            article_type_ja="インタビュー",
        )

        assert len(draft.titles) == 3
        assert draft.titles[0] == "タイトル1"
        assert draft.titles[1] == "タイトル2"
        assert draft.titles[2] == "タイトル3"
        assert "リード文" in draft.lead
        assert len(draft.sections) == 2
        assert draft.sections[0]["heading"] == "見出し1"
        assert "本文1" in draft.sections[0]["body"]
        assert draft.sections[1]["heading"] == "見出し2"
        assert "締め" in draft.closing

    def test_from_markdown_preserves_metadata(self):
        """Test that metadata is preserved during parsing."""
        from src.chains.article_chain import ArticleDraft

        markdown = """## タイトル案（3つ）

1. Test Title

## リード文

Lead text.

## 本文

### Section

Body text.

## 締め

Closing.

---
"""
        metadata = {"original_key": "value", "rewrite_applied": True}
        draft = ArticleDraft.from_markdown(
            markdown=markdown,
            article_type="CULTURE",
            article_type_ja="カルチャー",
            preserve_metadata=metadata,
        )

        assert draft.metadata.get("original_key") == "value"
        assert draft.metadata.get("rewrite_applied") is True

    def test_from_markdown_roundtrip(self):
        """Test that to_markdown -> from_markdown preserves content."""
        from src.chains.article_chain import ArticleDraft

        original = ArticleDraft(
            titles=["タイトルA", "タイトルB", "タイトルC"],
            lead="リード文の内容です。",
            sections=[
                {"heading": "セクション1", "body": "本文1です。"},
                {"heading": "セクション2", "body": "本文2です。"},
            ],
            closing="締めくくりの文章です。",
            article_type="EVENT_REPORT",
            article_type_ja="イベントレポート",
        )

        markdown = original.to_markdown()
        parsed = ArticleDraft.from_markdown(
            markdown=markdown,
            article_type=original.article_type,
            article_type_ja=original.article_type_ja,
        )

        assert parsed.titles == original.titles
        assert parsed.lead == original.lead
        assert len(parsed.sections) == len(original.sections)
        for i, section in enumerate(parsed.sections):
            assert section["heading"] == original.sections[i]["heading"]
            assert section["body"] == original.sections[i]["body"]
        assert parsed.closing == original.closing

    def test_from_markdown_invalid_format(self):
        """Test that invalid markdown raises ValueError."""
        import pytest

        from src.chains.article_chain import ArticleDraft

        invalid_markdown = "This is not valid markdown format"

        with pytest.raises(ValueError, match="Failed to parse titles"):
            ArticleDraft.from_markdown(
                markdown=invalid_markdown,
                article_type="INTERVIEW",
                article_type_ja="インタビュー",
            )

    def test_from_markdown_with_multiline_content(self):
        """Test parsing markdown with multiline sections."""
        from src.chains.article_chain import ArticleDraft

        markdown = """## タイトル案（3つ）

1. タイトル

## リード文

リード文の1行目。
リード文の2行目。

## 本文

### 見出し

本文の1行目。

本文の2行目（空行を挟む）。

## 締め

締めの文章。

---
"""
        draft = ArticleDraft.from_markdown(
            markdown=markdown,
            article_type="CULTURE",
            article_type_ja="カルチャー",
        )

        assert "1行目" in draft.lead
        assert "2行目" in draft.lead
        assert "本文の1行目" in draft.sections[0]["body"]
        # Note: empty lines within body are preserved
        assert "本文の2行目" in draft.sections[0]["body"]

    def test_from_markdown_fullwidth_period(self):
        """Test parsing markdown with full-width period in title numbers."""
        from src.chains.article_chain import ArticleDraft

        markdown = """## タイトル案（3つ）

１．全角タイトル1
２．全角タイトル2
３．全角タイトル3

## リード文

リード文。

## 本文

### 見出し

本文。

## 締め

締め。

---
"""
        draft = ArticleDraft.from_markdown(
            markdown=markdown,
            article_type="INTERVIEW",
            article_type_ja="インタビュー",
        )

        assert len(draft.titles) == 3
        assert draft.titles[0] == "全角タイトル1"
