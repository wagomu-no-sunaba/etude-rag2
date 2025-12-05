# Artifact Registry for Docker images

resource "google_artifact_registry_repository" "main" {
  location      = var.region
  repository_id = "etude-rag2-repo"
  description   = "Docker repository for etude-rag2 images"
  format        = "DOCKER"
  project       = var.project_id

  cleanup_policies {
    id     = "keep-recent-versions"
    action = "KEEP"

    most_recent_versions {
      keep_count = 10
    }
  }

  depends_on = [google_project_service.services]
}

# Local values for image URIs
locals {
  api_image_base       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.main.repository_id}/api-server"
  streamlit_image_base = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.main.repository_id}/streamlit-ui"
  ingester_image_base  = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.main.repository_id}/ingester"
}
