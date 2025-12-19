"""Tests for HTMX form components."""

from fastapi.testclient import TestClient


class TestIndexPage:
    """Test index page content and structure."""

    def test_page_title(self):
        """GET / returns page with title 'Note記事ドラフト生成'."""
        from src.api.main import app

        client = TestClient(app)
        response = client.get("/")

        assert response.status_code == 200
        html = response.text

        # Check page title in <title> tag
        assert "Note記事ドラフト生成" in html

    def test_main_content_area(self):
        """GET / returns page with main content area."""
        from src.api.main import app

        client = TestClient(app)
        response = client.get("/")

        assert response.status_code == 200
        html = response.text

        # Check main content area exists
        assert "<main" in html
        assert "<h1>" in html and "Note記事ドラフト生成" in html


class TestArticleTypeDropdown:
    """Test article type selection dropdown."""

    def test_article_type_options(self):
        """Index page contains select element with 5 options for article types."""
        from src.api.main import app

        client = TestClient(app)
        response = client.get("/")

        assert response.status_code == 200
        html = response.text

        # Check select element exists
        assert "<select" in html
        assert 'name="article_type"' in html

        # Check all 5 options exist
        assert "自動判定" in html
        assert "お知らせ" in html
        assert "イベントレポート" in html
        assert "インタビュー" in html
        assert "カルチャー" in html


class TestInputTextarea:
    """Test input material textarea."""

    def test_input_textarea(self):
        """Index page contains textarea with name='input_material' and placeholder."""
        from src.api.main import app

        client = TestClient(app)
        response = client.get("/")

        assert response.status_code == 200
        html = response.text

        # Check textarea exists with correct name
        assert "<textarea" in html
        assert 'name="input_material"' in html

        # Check placeholder exists (in Japanese)
        assert "placeholder=" in html


class TestGenerateButton:
    """Test generate button with HTMX attributes."""

    def test_generate_button_htmx_attrs(self):
        """Form has button with hx-post, hx-target, hx-swap attributes."""
        from src.api.main import app

        client = TestClient(app)
        response = client.get("/")

        assert response.status_code == 200
        html = response.text

        # Check HTMX attributes on form or button
        assert "hx-post=" in html
        assert "hx-target=" in html
        assert "hx-swap=" in html

        # Check result container exists
        assert 'id="result"' in html
