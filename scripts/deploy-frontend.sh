#!/bin/bash
# Frontend (Streamlit UI) Deployment Script
# Usage: ./scripts/deploy-frontend.sh

set -e

# Record start time
START_TIME=$(date +%s)

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
REGION="us-central1"
ENVIRONMENT="${ENVIRONMENT:-dev}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/etude-rag2/streamlit-ui:latest"
SERVICE_NAME="etude-rag2-streamlit-${ENVIRONMENT}"

echo "=========================================="
echo "Frontend (Streamlit UI) Deployment"
echo "=========================================="
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Image: ${IMAGE}"
echo "Service: ${SERVICE_NAME}"
echo "=========================================="

# Function to send macOS notification
notify() {
    local title="$1"
    local message="$2"
    local sound="$3"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        osascript -e "display notification \"${message}\" with title \"${title}\" sound name \"${sound}\"" 2>/dev/null || true
    fi
}

# Build and push Docker image using cloudbuild-streamlit.yaml with cache strategy
echo ""
echo "[1/2] Building and pushing Docker image (with cache)..."
if gcloud builds submit --config=cloudbuild-streamlit.yaml .; then
    echo "Docker image built and pushed successfully."
else
    notify "Frontend Deploy Failed" "Docker build failed" "Basso"
    echo "ERROR: Docker build failed!"
    exit 1
fi

# Deploy to Cloud Run
echo ""
echo "[2/2] Deploying to Cloud Run..."
if gcloud run services update "${SERVICE_NAME}" \
    --region "${REGION}" \
    --image "${IMAGE}"; then

    # Get service URL
    SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
        --region "${REGION}" \
        --format="value(status.url)")

    echo ""
    echo "=========================================="
    echo "Deployment completed successfully!"
    echo "Service URL: ${SERVICE_URL}"
    echo "=========================================="

    # Calculate and display elapsed time
    END_TIME=$(date +%s)
    ELAPSED=$((END_TIME - START_TIME))
    MINUTES=$((ELAPSED / 60))
    SECONDS=$((ELAPSED % 60))

    echo "Elapsed time: ${MINUTES}m ${SECONDS}s"
    echo "=========================================="

    notify "Frontend Deploy Success" "Streamlit UI deployed successfully!\n${SERVICE_URL}" "Glass"
else
    notify "Frontend Deploy Failed" "Cloud Run deployment failed" "Basso"
    echo "ERROR: Cloud Run deployment failed!"
    exit 1
fi
