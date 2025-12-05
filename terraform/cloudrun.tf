# Cloud Run services

# =============================================================================
# FastAPI Server
# =============================================================================

resource "google_cloud_run_v2_service" "api" {
  name     = "etude-rag2-api-${var.environment}"
  location = var.region
  project  = var.project_id

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

    timeout = "300s"

    containers {
      image = "${local.api_image_base}:latest"

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

      # Startup probe with longer timeout
      startup_probe {
        initial_delay_seconds = 0
        timeout_seconds       = 240
        period_seconds        = 240
        failure_threshold     = 1
        tcp_socket {
          port = 8080
        }
      }

      # Liveness probe
      liveness_probe {
        http_get {
          path = "/health"
        }
        timeout_seconds   = 5
        period_seconds    = 30
        failure_threshold = 3
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
      env {
        name  = "EMBEDDING_MODEL"
        value = var.embedding_model
      }
      env {
        name  = "LLM_MODEL"
        value = var.llm_model
      }
      env {
        name  = "LLM_TEMPERATURE"
        value = var.llm_temperature
      }
      env {
        name  = "RERANKER_MODEL"
        value = var.reranker_model
      }
      env {
        name  = "HYBRID_SEARCH_K"
        value = var.hybrid_search_k
      }
      env {
        name  = "RRF_K"
        value = var.rrf_k
      }

      # Secrets
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
        name = "TARGET_FOLDER_ID"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.drive_folder_id.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "MY_EMAIL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.my_email.secret_id
            version = "latest"
          }
        }
      }
    }

    max_instance_request_concurrency = var.cloud_run_concurrency
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_project_service.services,
    google_sql_database_instance.postgres,
    google_secret_manager_secret_version.db_password,
    google_secret_manager_secret_version.drive_folder_id,
  ]

  lifecycle {
    ignore_changes = [
      template[0].containers[0].image,
    ]
  }
}

# Allow unauthenticated access to API (adjust based on security requirements)
resource "google_cloud_run_v2_service_iam_member" "api_public" {
  count = var.environment == "dev" ? 1 : 0

  location = google_cloud_run_v2_service.api.location
  name     = google_cloud_run_v2_service.api.name
  project  = var.project_id
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# =============================================================================
# Streamlit UI
# =============================================================================

resource "google_cloud_run_v2_service" "streamlit" {
  name     = "etude-rag2-streamlit-${var.environment}"
  location = var.region
  project  = var.project_id

  template {
    service_account = google_service_account.cloud_run.email

    scaling {
      min_instance_count = 0
      max_instance_count = var.streamlit_max_instances
    }

    vpc_access {
      connector = google_vpc_access_connector.connector.id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    timeout = "600s"

    containers {
      image = "${local.streamlit_image_base}:latest"

      resources {
        limits = {
          cpu    = var.streamlit_cpu
          memory = var.streamlit_memory
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      ports {
        container_port = 8501
      }

      # Startup probe with longer timeout for model downloads
      startup_probe {
        initial_delay_seconds = 0
        timeout_seconds       = 240
        period_seconds        = 240
        failure_threshold     = 1
        tcp_socket {
          port = 8501
        }
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
      env {
        name  = "EMBEDDING_MODEL"
        value = var.embedding_model
      }
      env {
        name  = "LLM_MODEL"
        value = var.llm_model
      }
      env {
        name  = "LLM_TEMPERATURE"
        value = var.llm_temperature
      }
      env {
        name  = "RERANKER_MODEL"
        value = var.reranker_model
      }
      env {
        name  = "HYBRID_SEARCH_K"
        value = var.hybrid_search_k
      }
      env {
        name  = "RRF_K"
        value = var.rrf_k
      }
      env {
        name  = "API_URL"
        value = google_cloud_run_v2_service.api.uri
      }

      # Secrets
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
        name = "TARGET_FOLDER_ID"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.drive_folder_id.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "MY_EMAIL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.my_email.secret_id
            version = "latest"
          }
        }
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_project_service.services,
    google_sql_database_instance.postgres,
    google_secret_manager_secret_version.db_password,
    google_cloud_run_v2_service.api,
  ]

  lifecycle {
    ignore_changes = [
      template[0].containers[0].image,
    ]
  }
}

# Allow unauthenticated access to Streamlit
resource "google_cloud_run_v2_service_iam_member" "streamlit_public" {
  count = var.environment == "dev" ? 1 : 0

  location = google_cloud_run_v2_service.streamlit.location
  name     = google_cloud_run_v2_service.streamlit.name
  project  = var.project_id
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# =============================================================================
# Drive Ingester Job
# =============================================================================

resource "google_cloud_run_v2_job" "ingester" {
  name     = "etude-rag2-ingester-${var.environment}"
  location = var.region
  project  = var.project_id

  template {
    template {
      service_account = google_service_account.cloud_run.email

      timeout = "${var.ingester_timeout}s"

      max_retries = 0

      vpc_access {
        connector = google_vpc_access_connector.connector.id
        egress    = "PRIVATE_RANGES_ONLY"
      }

      containers {
        image = "${local.ingester_image_base}:latest"

        resources {
          limits = {
            cpu    = var.ingester_cpu
            memory = var.ingester_memory
          }
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
        env {
          name  = "EMBEDDING_MODEL"
          value = var.embedding_model
        }

        # Secrets
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
          name = "TARGET_FOLDER_ID"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.drive_folder_id.secret_id
              version = "latest"
            }
          }
        }
        env {
          name = "MY_EMAIL"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.my_email.secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }

  depends_on = [
    google_project_service.services,
    google_sql_database_instance.postgres,
    google_secret_manager_secret_version.db_password,
  ]

  lifecycle {
    ignore_changes = [
      template[0].template[0].containers[0].image,
    ]
  }
}
