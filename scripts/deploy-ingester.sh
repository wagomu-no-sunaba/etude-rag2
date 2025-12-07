#!/bin/bash
# Ingester (Data Ingestion Job) Deployment Script
# Usage: ./scripts/deploy-ingester.sh

set -e

# Record start time
START_TIME=$(date +%s)

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
REGION="us-central1"
ENVIRONMENT="${ENVIRONMENT:-dev}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/etude-rag2-repo/ingester:latest"
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

# Deploy Cloud Run Job
echo ""
echo "[2/2] Deploying Cloud Run Job..."

# Check if job exists and deploy accordingly
if gcloud run jobs describe "${JOB_NAME}" --region "${REGION}" &>/dev/null; then
    echo "Updating existing job..."
    DEPLOY_CMD="gcloud run jobs update ${JOB_NAME} --region ${REGION} --image ${IMAGE}"
else
    echo "Creating new job..."
    DEPLOY_CMD="gcloud run jobs create ${JOB_NAME} --region ${REGION} --image ${IMAGE}"
fi

if ${DEPLOY_CMD}; then
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

    notify "Ingester Deploy Success" "Ingester job deployed successfully!" "Glass"
else
    notify "Ingester Deploy Failed" "Cloud Run Job deployment failed" "Basso"
    echo "ERROR: Cloud Run Job deployment failed!"
    exit 1
fi
