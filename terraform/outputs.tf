# Terraform outputs

# =============================================================================
# Project Info
# =============================================================================

output "project_id" {
  description = "GCP Project ID"
  value       = var.project_id
}

output "region" {
  description = "GCP Region"
  value       = var.region
}

# =============================================================================
# Cloud Run Service URLs
# =============================================================================

output "api_service_url" {
  description = "URL of the FastAPI Cloud Run service"
  value       = google_cloud_run_v2_service.api.uri
}

# Streamlit output disabled - Web UI is now integrated into FastAPI with HTMX
# output "streamlit_service_url" {
#   description = "URL of the Streamlit Cloud Run service"
#   value       = google_cloud_run_v2_service.streamlit.uri
# }

output "ingester_job_name" {
  description = "Name of the Ingester Cloud Run Job"
  value       = google_cloud_run_v2_job.ingester.name
}

# =============================================================================
# Cloud SQL
# =============================================================================

output "cloud_sql_connection_name" {
  description = "Cloud SQL instance connection name"
  value       = google_sql_database_instance.postgres.connection_name
}

output "cloud_sql_instance_name" {
  description = "Cloud SQL instance name"
  value       = google_sql_database_instance.postgres.name
}

output "cloud_sql_private_ip" {
  description = "Cloud SQL private IP address"
  value       = google_sql_database_instance.postgres.private_ip_address
}

# For sync-env-from-secrets.sh script
output "db_private_ip" {
  description = "Database private IP (alias for scripts)"
  value       = google_sql_database_instance.postgres.private_ip_address
}

output "db_name" {
  description = "Database name"
  value       = var.db_name
}

output "db_user" {
  description = "Database user"
  value       = var.db_user
}

# =============================================================================
# Secret Manager
# =============================================================================

output "db_password_secret_id" {
  description = "Secret Manager secret ID for database password"
  value       = google_secret_manager_secret.db_password.secret_id
}

# =============================================================================
# Artifact Registry
# =============================================================================

output "artifact_registry_repository" {
  description = "Artifact Registry repository URL"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.main.repository_id}"
}

output "api_image_uri" {
  description = "Docker image URI for FastAPI server"
  value       = "${local.api_image_base}:latest"
}

# Streamlit output disabled - Web UI is now integrated into FastAPI with HTMX
# output "streamlit_image_uri" {
#   description = "Docker image URI for Streamlit UI"
#   value       = "${local.streamlit_image_base}:latest"
# }

output "ingester_image_uri" {
  description = "Docker image URI for Drive Ingester"
  value       = "${local.ingester_image_base}:latest"
}

# =============================================================================
# Service Accounts
# =============================================================================

output "cloud_run_service_account_email" {
  description = "Service account email for Cloud Run services"
  value       = google_service_account.cloud_run.email
}

output "deploy_service_account_email" {
  description = "Service account email for GitHub Actions deployment"
  value       = google_service_account.deploy.email
}

# =============================================================================
# Workload Identity Federation
# =============================================================================

output "workload_identity_provider" {
  description = "Workload Identity Provider for GitHub Actions"
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "workload_identity_pool" {
  description = "Workload Identity Pool name"
  value       = google_iam_workload_identity_pool.github.name
}

# =============================================================================
# VPC
# =============================================================================

output "vpc_connector_id" {
  description = "VPC connector ID"
  value       = google_vpc_access_connector.connector.id
}

# =============================================================================
# GitHub Actions Configuration (for reference)
# =============================================================================

output "github_actions_config" {
  description = "Configuration values for GitHub Actions secrets"
  value = {
    GCP_PROJECT_ID             = var.project_id
    GCP_REGION                 = var.region
    WORKLOAD_IDENTITY_PROVIDER = google_iam_workload_identity_pool_provider.github.name
    DEPLOY_SERVICE_ACCOUNT     = google_service_account.deploy.email
    ARTIFACT_REGISTRY          = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.main.repository_id}"
  }
}
