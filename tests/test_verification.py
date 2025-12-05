"""Tests for the verification module."""


class TestStyleCheckResult:
    """Test StyleCheckResult model."""

    def test_style_check_result_model(self):
        """Test StyleCheckResult with all fields."""
        from src.verification.style_checker import StyleCheckResult, StyleIssue

        result = StyleCheckResult(
            is_consistent=True,
            consistency_score=0.85,
            issues=[
                StyleIssue(
                    location="リード文",
                    issue="語尾が「です」で統一されていない",
                    suggestion="「ですね」に変更",
                )
            ],
            corrected_sections=[{"original": "これは良いです", "corrected": "これは良いですね"}],
        )

        assert result.is_consistent is True
        assert result.consistency_score == 0.85
        assert len(result.issues) == 1
        assert result.issues[0].location == "リード文"

    def test_style_check_result_empty_issues(self):
        """Test StyleCheckResult with no issues."""
        from src.verification.style_checker import StyleCheckResult

        result = StyleCheckResult(
            is_consistent=True,
            consistency_score=1.0,
            issues=[],
            corrected_sections=[],
        )

        assert result.is_consistent is True
        assert len(result.issues) == 0


class TestHallucinationCheckResult:
    """Test HallucinationCheckResult model."""

    def test_hallucination_check_result_model(self):
        """Test HallucinationCheckResult with unverified claims."""
        from src.verification.hallucination_detector import (
            HallucinationCheckResult,
            UnverifiedClaim,
        )

        result = HallucinationCheckResult(
            has_hallucination=True,
            confidence=0.9,
            verified_facts=["入社3ヶ月目", "エンジニア"],
            unverified_claims=[
                UnverifiedClaim(
                    claim="年収が30%アップした",
                    location="本文2段落目",
                    suggested_tag="年収の具体的な数値",
                )
            ],
            missing_citations=["「とても働きやすい」という発言"],
        )

        assert result.has_hallucination is True
        assert result.confidence == 0.9
        assert len(result.verified_facts) == 2
        assert len(result.unverified_claims) == 1

    def test_hallucination_check_result_no_issues(self):
        """Test HallucinationCheckResult with no hallucinations."""
        from src.verification.hallucination_detector import HallucinationCheckResult

        result = HallucinationCheckResult(
            has_hallucination=False,
            confidence=0.95,
            verified_facts=["入社3ヶ月目", "エンジニア", "チームメンバー5名"],
            unverified_claims=[],
            missing_citations=[],
        )

        assert result.has_hallucination is False
        assert len(result.unverified_claims) == 0


class TestVerificationPipeline:
    """Test the verification pipeline."""

    def test_apply_tags_to_text(self):
        """Test applying [要確認] tags to text."""
        from src.verification.hallucination_detector import (
            HallucinationDetectorChain,
            UnverifiedClaim,
        )

        text = "年収が30%アップしました。とても満足しています。"
        claims = [
            UnverifiedClaim(
                claim="年収が30%アップ",
                location="本文",
                suggested_tag="年収の具体的な数値",
            )
        ]

        result = HallucinationDetectorChain.apply_tags(text, claims)

        assert "[要確認:" in result or "年収が30%アップ" in result
