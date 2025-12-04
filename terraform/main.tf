# Enable required APIs
resource "google_project_service" "services" {
  for_each = toset([
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "aiplatform.googleapis.com",
    "cloudbuild.googleapis.com",
    "secretmanager.googleapis.com",
    "vpcaccess.googleapis.com",
  ])

  service            = each.value
  disable_on_destroy = false
}

# Service account for Cloud Run
resource "google_service_account" "cloud_run" {
  account_id   = "etude-rag2-${var.environment}"
  display_name = "etude-rag2 Cloud Run Service Account (${var.environment})"
}

# IAM: Allow Cloud Run service account to access Vertex AI
resource "google_project_iam_member" "vertex_ai_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

# IAM: Allow Cloud Run service account to access Cloud SQL
resource "google_project_iam_member" "cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

# IAM: Allow Cloud Run service account to access Secret Manager
resource "google_project_iam_member" "secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

# VPC for private Cloud SQL connection
resource "google_compute_network" "vpc" {
  name                    = "etude-rag2-vpc-${var.environment}"
  auto_create_subnetworks = false

  depends_on = [google_project_service.services["vpcaccess.googleapis.com"]]
}

resource "google_compute_subnetwork" "subnet" {
  name          = "etude-rag2-subnet-${var.environment}"
  ip_cidr_range = "10.0.0.0/24"
  region        = var.region
  network       = google_compute_network.vpc.id
}

# VPC Connector for Cloud Run to Cloud SQL
resource "google_vpc_access_connector" "connector" {
  name          = "etude-rag2-vpc-${var.environment}"
  region        = var.region
  ip_cidr_range = "10.8.0.0/28"
  network       = google_compute_network.vpc.name

  depends_on = [google_project_service.services["vpcaccess.googleapis.com"]]
}

# Private IP for Cloud SQL
resource "google_compute_global_address" "private_ip" {
  name          = "etude-rag2-db-ip-${var.environment}"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc.id
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip.name]
}
