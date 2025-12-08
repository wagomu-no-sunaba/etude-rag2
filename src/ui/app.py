"""Streamlit web application for article draft generation."""

import streamlit as st

from src.ui.api_client import APIClient, ProgressUpdate, StreamResult
from src.ui.utils import (
    create_download_markdown,
    parse_sections_to_body,
)

# Page configuration
st.set_page_config(
    page_title="Note記事ドラフト生成",
    page_icon="📝",
    layout="wide",
)

# Initialize API client
api_client = APIClient()


def init_session_state():
    """Initialize session state variables."""
    if "input_material" not in st.session_state:
        st.session_state.input_material = ""
    if "selected_article_type" not in st.session_state:
        st.session_state.selected_article_type = None
    if "generated_draft" not in st.session_state:
        st.session_state.generated_draft = None
    if "is_processing" not in st.session_state:
        st.session_state.is_processing = False


def render_sidebar():
    """Render sidebar with settings."""
    with st.sidebar:
        st.title("⚙️ 設定")

        # Article type selection
        st.subheader("記事タイプ")
        article_types = {
            "自動判定": None,
            "お知らせ": "ANNOUNCEMENT",
            "イベントレポート": "EVENT_REPORT",
            "インタビュー": "INTERVIEW",
            "カルチャー": "CULTURE",
        }
        selected = st.selectbox(
            "記事タイプを選択",
            options=list(article_types.keys()),
            index=0,
        )
        st.session_state.selected_article_type = article_types[selected]

        # API health check
        st.subheader("API状態")
        if api_client.health_check():
            st.success("✅ API接続OK")
        else:
            st.error("❌ API接続エラー")
            st.caption("APIサーバーを起動してください")

        st.divider()
        st.caption("Note記事ドラフト生成 v0.1.0")


def render_input_section():
    """Render input material section."""
    st.header("📝 入力素材")

    st.session_state.input_material = st.text_area(
        "入力素材を入力してください",
        value=st.session_state.input_material,
        height=300,
        placeholder="""テーマ: 新入社員の紹介
名前: 山田太郎
役職: エンジニア

キーポイント:
- 入社の経緯
- 担当業務
- 今後の抱負

インタビュー引用:
「チームの雰囲気がとても良いです」
「技術的な成長を感じています」""",
    )

    col1, col2 = st.columns([1, 4])
    with col1:
        is_disabled = not st.session_state.input_material or st.session_state.is_processing
        generate_button = st.button(
            "🚀 記事を生成",
            type="primary",
            disabled=is_disabled,
        )

    if generate_button:
        generate_article()


def generate_article():
    """Generate article using streaming API with progress bar."""
    st.session_state.is_processing = True
    progress_container = st.empty()
    status_container = st.empty()

    status_container.info("🔄 記事を生成中...")

    try:
        stream = api_client.generate_stream(
            input_material=st.session_state.input_material,
            article_type=st.session_state.selected_article_type,
        )

        for update in stream:
            if isinstance(update, ProgressUpdate):
                progress_container.progress(
                    update.percentage / 100,
                    text=f"ステップ {update.step_number}/{update.total_steps}: {update.step_name}",
                )
            elif isinstance(update, StreamResult):
                progress_container.empty()
                status_container.empty()

                if update.success:
                    st.session_state.generated_draft = update.result
                    st.success("✅ 記事生成完了!")
                else:
                    st.error(f"❌ エラーが発生しました: {update.error}")
                return

    except Exception as e:
        progress_container.empty()
        status_container.empty()
        st.error(f"❌ エラーが発生しました: {e}")
    finally:
        st.session_state.is_processing = False


def render_output_section():
    """Render generated output section."""
    if st.session_state.generated_draft is None:
        st.info("👆 入力素材を入力して「記事を生成」をクリックしてください")
        return

    draft = st.session_state.generated_draft

    st.header("📄 生成結果")

    # Article type badge
    article_type_ja = draft.get("article_type_ja", "不明")
    st.markdown(f"**記事タイプ**: {article_type_ja}")

    # Tabs for different sections
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["タイトル案", "リード文", "本文", "締め", "マークダウン"]
    )

    with tab1:
        st.subheader("タイトル案（3つ）")
        for i, title in enumerate(draft.get("titles", []), 1):
            st.markdown(f"**{i}.** {title}")

    with tab2:
        st.subheader("リード文")
        st.markdown(draft.get("lead", ""))

    with tab3:
        st.subheader("本文")
        body = parse_sections_to_body(draft.get("sections", []))
        st.markdown(body)

    with tab4:
        st.subheader("締め")
        st.markdown(draft.get("closing", ""))

    with tab5:
        st.subheader("マークダウン形式")
        markdown_content = draft.get("markdown", create_download_markdown(draft))
        st.code(markdown_content, language="markdown")

        # Download button
        st.download_button(
            label="📥 マークダウンをダウンロード",
            data=markdown_content,
            file_name="article_draft.md",
            mime="text/markdown",
        )


def render_verification_section():
    """Render verification section."""
    if st.session_state.generated_draft is None:
        return

    st.header("🔍 検証")

    col1, col2 = st.columns(2)
    is_disabled = st.session_state.is_processing

    with col1:
        if st.button("ハルシネーション検証", type="secondary", disabled=is_disabled):
            verify_content("hallucination")

    with col2:
        if st.button("文体検証", type="secondary", disabled=is_disabled):
            verify_content("style")


def verify_content(check_type: str):
    """Verify content using API."""
    draft = st.session_state.generated_draft
    if draft is None:
        return

    st.session_state.is_processing = True
    try:
        with st.spinner("検証中..."):
            body = parse_sections_to_body(draft.get("sections", []))
            result = api_client.verify(
                lead=draft.get("lead", ""),
                body=body,
                closing=draft.get("closing", ""),
                input_material=st.session_state.input_material,
            )

            if check_type == "hallucination":
                render_hallucination_result(result.get("hallucination", {}))
            else:
                render_style_result(result.get("style", {}))

    except Exception as e:
        st.error(f"❌ 検証エラー: {e}")
    finally:
        st.session_state.is_processing = False


def render_hallucination_result(result: dict):
    """Render hallucination check result."""
    st.subheader("ハルシネーション検証結果")

    has_hallucination = result.get("has_hallucination", False)
    confidence = result.get("confidence", 0)

    if has_hallucination:
        st.warning(f"⚠️ 要確認箇所あり (信頼度: {confidence:.0%})")
    else:
        st.success(f"✅ 問題なし (信頼度: {confidence:.0%})")

    # Verified facts
    verified = result.get("verified_facts", [])
    if verified:
        with st.expander("確認された事実"):
            for fact in verified:
                st.markdown(f"- {fact}")

    # Unverified claims
    unverified = result.get("unverified_claims", [])
    if unverified:
        with st.expander("未確認の主張", expanded=True):
            for claim in unverified:
                st.markdown(f"- **{claim.get('claim', '')}**")
                st.caption(f"  場所: {claim.get('location', '')}, タグ: {claim.get('tag', '')}")


def render_style_result(result: dict):
    """Render style check result."""
    st.subheader("文体検証結果")

    is_consistent = result.get("is_consistent", True)
    score = result.get("consistency_score", 0)

    if is_consistent:
        st.success(f"✅ 文体一貫 (スコア: {score:.0%})")
    else:
        st.warning(f"⚠️ 文体に問題あり (スコア: {score:.0%})")

    # Issues
    issues = result.get("issues", [])
    if issues:
        with st.expander("問題点", expanded=True):
            for issue in issues:
                st.markdown(f"- **{issue.get('issue', '')}**")
                st.caption(f"  場所: {issue.get('location', '')}")
                st.caption(f"  提案: {issue.get('suggestion', '')}")


def main():
    """Main application entry point."""
    init_session_state()

    st.title("📝 Note記事ドラフト生成")
    st.caption("RAGベースの採用note記事ドラフト生成システム")

    render_sidebar()

    # Main content
    col1, col2 = st.columns([1, 1])

    with col1:
        render_input_section()

    with col2:
        render_output_section()

    st.divider()
    render_verification_section()


if __name__ == "__main__":
    main()
