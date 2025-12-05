#!/bin/bash
# Full Deployment Script (Backend + Frontend + Ingester)
# Usage: ./scripts/deploy-all.sh [--rebuild-base] [--include-ingester]
#
# By default, deploys Backend and Frontend in parallel.
# Options:
#   --rebuild-base     Rebuild base images before deploying (use when dependencies changed)
#   --include-ingester Also deploy the Ingester job

set -e

# Record start time
START_TIME=$(date +%s)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGION="us-central1"
ENVIRONMENT="${ENVIRONMENT:-dev}"
INCLUDE_INGESTER=false
REBUILD_BASE=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --include-ingester)
            INCLUDE_INGESTER=true
            shift
            ;;
        --rebuild-base)
            REBUILD_BASE=true
            shift
            ;;
    esac
done

echo "=========================================="
echo "Full Deployment (Parallel Execution)"
echo "=========================================="
echo "Rebuild Base: ${REBUILD_BASE}"
echo "Backend: Yes"
echo "Frontend: Yes"
echo "Ingester: ${INCLUDE_INGESTER}"
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

# Create temporary directory for logs
LOG_DIR=$(mktemp -d)
trap 'rm -rf "${LOG_DIR}"' EXIT

# Rebuild base images if requested
if [ "${REBUILD_BASE}" = true ]; then
    echo ""
    echo ">>> Rebuilding base images..."
    if "${SCRIPT_DIR}/build-base-images.sh"; then
        echo "[OK] Base images rebuilt successfully."
    else
        echo "[FAILED] Base image build failed."
        notify "Full Deploy Failed" "Base image build failed" "Basso"
        exit 1
    fi
    echo ""
fi

# Record deployment start times
DEPLOY_START_TIME=$(date +%s)

# Deploy Backend in background
echo ""
echo ">>> Starting Backend deployment..."
(
    START=$(date +%s)
    "${SCRIPT_DIR}/deploy-backend.sh" > "${LOG_DIR}/backend.log" 2>&1
    EXIT_CODE=$?
    END=$(date +%s)
    echo $((END - START)) > "${LOG_DIR}/backend.time"
    exit $EXIT_CODE
) &
BACKEND_PID=$!

# Deploy Frontend in background
echo ">>> Starting Frontend deployment..."
(
    START=$(date +%s)
    "${SCRIPT_DIR}/deploy-frontend.sh" > "${LOG_DIR}/frontend.log" 2>&1
    EXIT_CODE=$?
    END=$(date +%s)
    echo $((END - START)) > "${LOG_DIR}/frontend.time"
    exit $EXIT_CODE
) &
FRONTEND_PID=$!

# Deploy Ingester in background (if requested)
if [ "${INCLUDE_INGESTER}" = true ]; then
    echo ">>> Starting Ingester deployment..."
    (
        START=$(date +%s)
        "${SCRIPT_DIR}/deploy-ingester.sh" > "${LOG_DIR}/ingester.log" 2>&1
        EXIT_CODE=$?
        END=$(date +%s)
        echo $((END - START)) > "${LOG_DIR}/ingester.time"
        exit $EXIT_CODE
    ) &
    INGESTER_PID=$!
fi

echo ""
echo ">>> All deployments started in parallel. Waiting for completion..."
echo ""

# Track failures
FAILED=false
FAILED_COMPONENTS=""

# Wait for Backend
if wait ${BACKEND_PID}; then
    echo "[OK] Backend deployment completed."
else
    echo "[FAILED] Backend deployment failed."
    FAILED=true
    FAILED_COMPONENTS="${FAILED_COMPONENTS} Backend"
fi

# Wait for Frontend
if wait ${FRONTEND_PID}; then
    echo "[OK] Frontend deployment completed."
else
    echo "[FAILED] Frontend deployment failed."
    FAILED=true
    FAILED_COMPONENTS="${FAILED_COMPONENTS} Frontend"
fi

# Wait for Ingester (if started)
if [ "${INCLUDE_INGESTER}" = true ]; then
    if wait ${INGESTER_PID}; then
        echo "[OK] Ingester deployment completed."
    else
        echo "[FAILED] Ingester deployment failed."
        FAILED=true
        FAILED_COMPONENTS="${FAILED_COMPONENTS} Ingester"
    fi
fi

# Calculate elapsed time
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
MINUTES=$((ELAPSED / 60))
SECONDS=$((ELAPSED % 60))

echo ""
echo "=========================================="

# Helper function to format time
format_time() {
    local secs=$1
    local mins=$((secs / 60))
    local secs=$((secs % 60))
    echo "${mins}m ${secs}s"
}

# Read individual deployment times
BACKEND_TIME=$(cat "${LOG_DIR}/backend.time" 2>/dev/null || echo "0")
FRONTEND_TIME=$(cat "${LOG_DIR}/frontend.time" 2>/dev/null || echo "0")
if [ "${INCLUDE_INGESTER}" = true ]; then
    INGESTER_TIME=$(cat "${LOG_DIR}/ingester.time" 2>/dev/null || echo "0")
fi

# Get service URLs
BACKEND_URL=$(gcloud run services describe "etude-rag2-api-${ENVIRONMENT}" --region "${REGION}" --format="value(status.url)" 2>/dev/null || echo "N/A")
FRONTEND_URL=$(gcloud run services describe "etude-rag2-streamlit-${ENVIRONMENT}" --region "${REGION}" --format="value(status.url)" 2>/dev/null || echo "N/A")

# Show results
if [ "${FAILED}" = true ]; then
    echo "Deployment FAILED for:${FAILED_COMPONENTS}"
    echo "=========================================="
    echo ""
    echo "--- Deployment Times ---"
    echo "  Backend:  $(format_time ${BACKEND_TIME})"
    echo "  Frontend: $(format_time ${FRONTEND_TIME})"
    if [ "${INCLUDE_INGESTER}" = true ]; then
        echo "  Ingester: $(format_time ${INGESTER_TIME})"
    fi
    echo ""
    echo "--- Failed deployment logs ---"
    for component in ${FAILED_COMPONENTS}; do
        log_file="${LOG_DIR}/$(echo "${component}" | tr '[:upper:]' '[:lower:]').log"
        if [ -f "${log_file}" ]; then
            echo ""
            echo "=== ${component} Log ==="
            cat "${log_file}"
        fi
    done
    echo ""
    echo "Total elapsed time: ${MINUTES}m ${SECONDS}s"
    echo "=========================================="
    notify "Full Deploy Failed" "Failed:${FAILED_COMPONENTS}" "Basso"
    exit 1
else
    echo "All deployments completed successfully!"
    echo "=========================================="
    echo ""
    echo "Deployment Times:"
    echo "  Backend:  $(format_time ${BACKEND_TIME})"
    echo "  Frontend: $(format_time ${FRONTEND_TIME})"
    if [ "${INCLUDE_INGESTER}" = true ]; then
        echo "  Ingester: $(format_time ${INGESTER_TIME})"
    fi
    echo ""
    echo "Service URLs:"
    echo "  Backend:  ${BACKEND_URL}"
    echo "  Frontend: ${FRONTEND_URL}"
    echo ""
    echo "Total elapsed time: ${MINUTES}m ${SECONDS}s"
    echo "=========================================="
    if [ "${INCLUDE_INGESTER}" = true ]; then
        notify "Full Deploy Success" "Backend, Frontend, and Ingester deployed!" "Glass"
    else
        notify "Full Deploy Success" "Backend and Frontend deployed!" "Glass"
    fi
fi
