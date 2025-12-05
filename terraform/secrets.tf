# Secret Manager resources

# Google Drive folder ID secret
resource "google_secret_manager_secret" "drive_folder_id" {
  secret_id = "etude-rag2-drive-folder-id-${var.environment}"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.services]
}

resource "google_secret_manager_secret_version" "drive_folder_id" {
  secret      = google_secret_manager_secret.drive_folder_id.id
  secret_data = var.target_folder_id
}

# Email address secret
resource "google_secret_manager_secret" "my_email" {
  secret_id = "etude-rag2-my-email-${var.environment}"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.services]
}

resource "google_secret_manager_secret_version" "my_email" {
  secret      = google_secret_manager_secret.my_email.id
  secret_data = var.my_email
}

# Service account key secret (placeholder - key should be uploaded manually)
# NOTE: For security, the actual key file should be uploaded manually to Secret Manager
# This resource creates the secret placeholder
resource "google_secret_manager_secret" "service_account_key" {
  secret_id = "etude-rag2-service-account-key-${var.environment}"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.services]
}

# IAM bindings for secrets
resource "google_secret_manager_secret_iam_member" "db_password_accessor" {
  secret_id = google_secret_manager_secret.db_password.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run.email}"
  project   = var.project_id
}

resource "google_secret_manager_secret_iam_member" "drive_folder_id_accessor" {
  secret_id = google_secret_manager_secret.drive_folder_id.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run.email}"
  project   = var.project_id
}

resource "google_secret_manager_secret_iam_member" "my_email_accessor" {
  secret_id = google_secret_manager_secret.my_email.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run.email}"
  project   = var.project_id
}

resource "google_secret_manager_secret_iam_member" "service_account_key_accessor" {
  secret_id = google_secret_manager_secret.service_account_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run.email}"
  project   = var.project_id
}

# =============================================================================
# Non-secret configuration stored in Secret Manager for single-source-of-truth
# This eliminates .env/tfvars duplication
# =============================================================================

# Application configuration (non-sensitive but centralized)
resource "google_secret_manager_secret" "app_config" {
  secret_id = "etude-rag2-app-config-${var.environment}"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.services]
}

resource "google_secret_manager_secret_version" "app_config" {
  secret = google_secret_manager_secret.app_config.id
  secret_data = jsonencode({
    # Vertex AI settings
    embedding_model  = var.embedding_model
    llm_model        = var.llm_model
    llm_temperature  = var.llm_temperature

    # Reranker settings
    reranker_model = var.reranker_model

    # Hybrid search settings
    hybrid_search_k = var.hybrid_search_k
    rrf_k           = var.rrf_k
  })
}

resource "google_secret_manager_secret_iam_member" "app_config_accessor" {
  secret_id = google_secret_manager_secret.app_config.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run.email}"
  project   = var.project_id
}
