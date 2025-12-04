# Cloud Run service for API
resource "google_cloud_run_v2_service" "api" {
  name     = "etude-rag2-api-${var.environment}"
  location = var.region

  template {
    service_account = google_service_account.cloud_run.email

    scaling {
      min_instance_count = var.cloud_run_min_instances
      max_instance_count = var.cloud_run_max_instances
    }

    vpc_access {
      connector = google_vpc_access_connector.connector.id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    containers {
      image = var.container_image != "" ? var.container_image : "gcr.io/${var.project_id}/etude-rag2:latest"

      resources {
        limits = {
          cpu    = var.cloud_run_cpu
          memory = var.cloud_run_memory
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      ports {
        container_port = 8080
      }

      # Environment variables
      env {
        name  = "GOOGLE_PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "GOOGLE_LOCATION"
        value = var.region
      }

      env {
        name  = "DB_HOST"
        value = google_sql_database_instance.postgres.private_ip_address
      }

      env {
        name  = "DB_PORT"
        value = "5432"
      }

      env {
        name  = "DB_NAME"
        value = var.db_name
      }

      env {
        name  = "DB_USER"
        value = var.db_user
      }

      # Database password from Secret Manager
      env {
        name = "DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.db_password.secret_id
            version = "latest"
          }
        }
      }

      env {
        name  = "EMBEDDING_MODEL"
        value = "text-embedding-004"
      }

      env {
        name  = "LLM_MODEL"
        value = "gemini-1.5-pro"
      }

      env {
        name  = "LLM_TEMPERATURE"
        value = "0.3"
      }

      startup_probe {
        http_get {
          path = "/health"
        }
        initial_delay_seconds = 10
        timeout_seconds       = 5
        period_seconds        = 10
        failure_threshold     = 3
      }

      liveness_probe {
        http_get {
          path = "/health"
        }
        timeout_seconds   = 5
        period_seconds    = 30
        failure_threshold = 3
      }
    }

    max_instance_request_concurrency = var.cloud_run_concurrency
    timeout                          = "300s"
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_project_service.services["run.googleapis.com"],
    google_secret_manager_secret_version.db_password,
  ]
}

# Allow unauthenticated access (adjust based on security requirements)
resource "google_cloud_run_v2_service_iam_member" "public" {
  count = var.environment == "dev" ? 1 : 0

  location = google_cloud_run_v2_service.api.location
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
