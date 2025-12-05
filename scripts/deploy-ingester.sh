#!/bin/bash
# Ingester (Data Ingestion Job) Deployment Script
# Usage: ./scripts/deploy-ingester.sh

set -e

# Record start time
START_TIME=$(date +%s)

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
REGION="us-central1"
ENVIRONMENT="${ENVIRONMENT:-dev}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/etude-rag2/ingester:latest"
JOB_NAME="etude-rag2-ingester-${ENVIRONMENT}"

echo "=========================================="
echo "Ingester (Data Ingestion Job) Deployment"
echo "=========================================="
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Image: ${IMAGE}"
echo "Job: ${JOB_NAME}"
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

# Build and push Docker image using cloudbuild-ingester.yaml with cache strategy
echo ""
echo "[1/2] Building and pushing Docker image (with cache)..."
if gcloud builds submit --config=cloudbuild-ingester.yaml .; then
    echo "Docker image built and pushed successfully."
else
    notify "Ingester Deploy Failed" "Docker build failed" "Basso"
    echo "ERROR: Docker build failed!"
    exit 1
fi

# Update Cloud Run Job
echo ""
echo "[2/2] Updating Cloud Run Job..."
if gcloud run jobs update "${JOB_NAME}" \
    --region "${REGION}" \
    --image "${IMAGE}"; then

    echo ""
    echo "=========================================="
    echo "Deployment completed successfully!"
    echo "Job: ${JOB_NAME}"
    echo "=========================================="
    echo ""
    echo "To execute the job, run:"
    echo "  gcloud run jobs execute ${JOB_NAME} --region ${REGION}"

    # Calculate and display elapsed time
    END_TIME=$(date +%s)
    ELAPSED=$((END_TIME - START_TIME))
    MINUTES=$((ELAPSED / 60))
    SECONDS=$((ELAPSED % 60))

    echo ""
    echo "Elapsed time: ${MINUTES}m ${SECONDS}s"
    echo "=========================================="

    notify "Ingester Deploy Success" "Ingester job updated successfully!" "Glass"
else
    notify "Ingester Deploy Failed" "Cloud Run Job update failed" "Basso"
    echo "ERROR: Cloud Run Job update failed!"
    exit 1
fi
