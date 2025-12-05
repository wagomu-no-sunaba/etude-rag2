# ============================================
# API Server Dockerfile
# ベースイメージから依存関係を継承し、アプリケーションコードのみ追加
# ============================================

ARG BASE_IMAGE=us-central1-docker.pkg.dev/etude-rag2/etude-rag2-repo/base:latest
FROM ${BASE_IMAGE}

WORKDIR /app

# アプリケーションコードをコピー
COPY src/ ./src/
COPY schemas/ ./schemas/

# 環境変数の設定
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# ヘルスチェック
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

EXPOSE 8080

# FastAPIサーバーを起動
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
