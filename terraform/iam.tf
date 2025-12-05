# IAM resources: Service accounts and Workload Identity Federation

# =============================================================================
# Deploy Service Account (for GitHub Actions)
# =============================================================================

resource "google_service_account" "deploy" {
  account_id   = "etude-rag2-deploy-${var.environment}"
  display_name = "etude-rag2 Deploy Service Account (${var.environment})"
  description  = "Service account for GitHub Actions deployment"
  project      = var.project_id

  depends_on = [google_project_service.services]
}

# IAM roles for deploy service account
resource "google_project_iam_member" "deploy_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_project_iam_member" "deploy_cloudbuild_editor" {
  project = var.project_id
  role    = "roles/cloudbuild.builds.editor"
  member  = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_project_iam_member" "deploy_artifactregistry_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_project_iam_member" "deploy_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${google_service_account.deploy.email}"
}

# Allow deploy service account to act as Cloud Run service account
resource "google_service_account_iam_member" "deploy_act_as_cloud_run" {
  service_account_id = google_service_account.cloud_run.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deploy.email}"
}

# =============================================================================
# Workload Identity Federation for GitHub Actions
# =============================================================================

resource "google_iam_workload_identity_pool" "github" {
  provider = google-beta
  project  = var.project_id

  workload_identity_pool_id = "github-pool-${var.environment}"
  display_name              = "GitHub Actions Pool (${var.environment})"
  description               = "Workload Identity Pool for GitHub Actions"

  depends_on = [google_project_service.services]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  provider = google-beta
  project  = var.project_id

  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"
  display_name                       = "GitHub Actions Provider"
  description                        = "OIDC provider for GitHub Actions"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }

  attribute_condition = "assertion.repository == '${var.github_repo}'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# Allow GitHub Actions to impersonate the deploy service account
resource "google_service_account_iam_member" "workload_identity_user" {
  service_account_id = google_service_account.deploy.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repo}"
}
