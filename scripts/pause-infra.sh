#!/bin/bash
# Pause Infrastructure Script
# Usage: ./scripts/pause-infra.sh [--force]
#
# Stops GCP resources to minimize costs while keeping data intact.
# Resources can be resumed with resume-infra.sh

set -e

REGION="us-central1"
ENVIRONMENT="${ENVIRONMENT:-dev}"
FORCE=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --force|-f)
            FORCE=true
            shift
            ;;
    esac
done

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to send macOS notification
notify() {
    local title="$1"
    local message="$2"
    local sound="$3"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        osascript -e "display notification \"${message}\" with title \"${title}\" sound name \"${sound}\"" 2>/dev/null || true
    fi
}

echo "=========================================="
echo "Pause Infrastructure"
echo "=========================================="
echo ""
echo -e "${YELLOW}This will stop the following resources:${NC}"
echo "  - Cloud SQL: etude-rag2-db-${ENVIRONMENT}"
echo "  - Cloud Run: etude-rag2-api-${ENVIRONMENT} (max-instances=0) - includes HTMX Web UI"
echo ""
echo -e "${GREEN}Data will be preserved. Use resume-infra.sh to restart.${NC}"
echo ""

# Confirmation prompt
if [ "$FORCE" != true ]; then
    read -p "Are you sure you want to pause the infrastructure? (y/N): " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        echo "Cancelled."
        exit 0
    fi
fi

START_TIME=$(date +%s)

echo ""
echo ">>> Stopping Cloud SQL instance (etude-rag2-db-${ENVIRONMENT})..."
if gcloud sql instances patch "etude-rag2-db-${ENVIRONMENT}" --activation-policy=NEVER --quiet 2>/dev/null; then
    echo -e "${GREEN}[OK]${NC} Cloud SQL instance stopped."
else
    echo -e "${YELLOW}[SKIP]${NC} Cloud SQL instance already stopped or not found."
fi

echo ""
echo ">>> Setting Cloud Run service to 0 max instances..."
if gcloud run services update "etude-rag2-api-${ENVIRONMENT}" --region="${REGION}" --max-instances=0 --quiet 2>/dev/null; then
    echo -e "${GREEN}[OK]${NC} etude-rag2-api-${ENVIRONMENT} set to 0 instances."
else
    echo -e "${YELLOW}[SKIP]${NC} etude-rag2-api-${ENVIRONMENT} not found or already configured."
fi

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
MINUTES=$((ELAPSED / 60))
SECONDS=$((ELAPSED % 60))

echo ""
echo "=========================================="
echo -e "${GREEN}Infrastructure paused successfully!${NC}"
echo "=========================================="
echo ""
echo "Elapsed time: ${MINUTES}m ${SECONDS}s"
echo ""
echo "To resume, run: ./scripts/resume-infra.sh"
echo "=========================================="

notify "Infrastructure Paused" "All resources have been stopped" "Glass"
