#!/bin/bash
# Build Base Images Script
# Usage: ./scripts/build-base-images.sh [--api-only | --streamlit-only]
#
# Use when pyproject.toml or uv.lock has changed

set -e

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
REGION="us-central1"
REPO="${REGION}-docker.pkg.dev/${PROJECT_ID}/etude-rag2"

# Parse arguments
BUILD_API=true
BUILD_STREAMLIT=true

if [[ "$1" == "--api-only" ]]; then
    BUILD_STREAMLIT=false
elif [[ "$1" == "--streamlit-only" ]]; then
    BUILD_API=false
fi

echo "=========================================="
echo "Building base images..."
echo "=========================================="
echo "Repository: ${REPO}"
echo "Build API base: ${BUILD_API}"
echo "Build Streamlit base: ${BUILD_STREAMLIT}"
echo "=========================================="

# Record start time
START_TIME=$(date +%s)

# API base image
if [[ "$BUILD_API" == "true" ]]; then
    echo ""
    echo "[API] Building base image..."
    API_START=$(date +%s)

    gcloud builds submit --config=cloudbuild-base.yaml .

    API_END=$(date +%s)
    API_ELAPSED=$((API_END - API_START))
    echo "[API] Base image built in ${API_ELAPSED}s"
fi

# Streamlit base image (includes BGE reranker model)
if [[ "$BUILD_STREAMLIT" == "true" ]]; then
    echo ""
    echo "[Streamlit] Building base image (includes BGE reranker model)..."
    STREAMLIT_START=$(date +%s)

    gcloud builds submit --config=cloudbuild-base-streamlit.yaml .

    STREAMLIT_END=$(date +%s)
    STREAMLIT_ELAPSED=$((STREAMLIT_END - STREAMLIT_START))
    echo "[Streamlit] Base image built in ${STREAMLIT_ELAPSED}s"
fi

# Calculate total elapsed time
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
MINUTES=$((ELAPSED / 60))
SECONDS=$((ELAPSED % 60))

echo ""
echo "=========================================="
echo "Base images built and pushed successfully!"
echo "Total time: ${MINUTES}m ${SECONDS}s"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  - Deploy backend: ./scripts/deploy-backend.sh"
echo "  - Deploy frontend: ./scripts/deploy-frontend.sh"
echo "=========================================="
