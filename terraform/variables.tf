# Variables for etude-rag2 Terraform configuration

variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for resources"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "github_repo" {
  description = "GitHub repository in owner/repo format (e.g., wagomu-no-sunaba/etude-rag2)"
  type        = string
}

# =============================================================================
# Cloud SQL settings
# =============================================================================

variable "db_tier" {
  description = "Cloud SQL instance tier"
  type        = string
  default     = "db-f1-micro"
}

variable "db_name" {
  description = "Database name"
  type        = string
  default     = "rag_db"
}

variable "db_user" {
  description = "Database user"
  type        = string
  default     = "raguser"
}

# =============================================================================
# Application settings
# =============================================================================

variable "target_folder_id" {
  description = "Google Drive folder ID for RAG documents"
  type        = string
}

variable "my_email" {
  description = "Email address for ACL filtering"
  type        = string
}

# =============================================================================
# Cloud Run API settings
# =============================================================================

variable "cloud_run_cpu" {
  description = "CPU allocation for API Cloud Run"
  type        = string
  default     = "2"
}

variable "cloud_run_memory" {
  description = "Memory allocation for API Cloud Run"
  type        = string
  default     = "4Gi"
}

variable "cloud_run_min_instances" {
  description = "Minimum number of API Cloud Run instances"
  type        = number
  default     = 0
}

variable "cloud_run_max_instances" {
  description = "Maximum number of API Cloud Run instances"
  type        = number
  default     = 10
}

variable "cloud_run_concurrency" {
  description = "Maximum concurrent requests per API instance"
  type        = number
  default     = 80
}

# =============================================================================
# Cloud Run Streamlit settings (DISABLED - Web UI is now integrated into FastAPI)
# Uncomment this section to re-enable Streamlit UI
# =============================================================================

/*
variable "streamlit_memory" {
  description = "Memory limit for Streamlit Cloud Run service"
  type        = string
  default     = "4Gi"
}

variable "streamlit_cpu" {
  description = "CPU limit for Streamlit Cloud Run service"
  type        = string
  default     = "2"
}

variable "streamlit_max_instances" {
  description = "Maximum instances for Streamlit Cloud Run service"
  type        = number
  default     = 5
}
*/

# =============================================================================
# Ingester Job settings
# =============================================================================

variable "ingester_memory" {
  description = "Memory limit for Ingester Cloud Run Job"
  type        = string
  default     = "2Gi"
}

variable "ingester_cpu" {
  description = "CPU limit for Ingester Cloud Run Job"
  type        = string
  default     = "2"
}

variable "ingester_timeout" {
  description = "Timeout in seconds for Ingester Cloud Run Job"
  type        = number
  default     = 3600
}

# =============================================================================
# Vertex AI / LLM settings
# =============================================================================

variable "embedding_model" {
  description = "Vertex AI embedding model name"
  type        = string
  default     = "text-embedding-004"
}

variable "llm_model" {
  description = "LLM model name (high quality)"
  type        = string
  default     = "gemini-2.0-flash"
}

variable "llm_model_lite" {
  description = "LLM model name (lightweight, cost-efficient)"
  type        = string
  default     = "gemini-2.0-flash-lite"
}

variable "llm_temperature" {
  description = "LLM temperature for generation"
  type        = string
  default     = "0.3"
}

# =============================================================================
# Reranker settings
# =============================================================================

variable "reranker_model" {
  description = "BGE reranker model name"
  type        = string
  default     = "BAAI/bge-reranker-v2-m3"
}

# =============================================================================
# Hybrid search settings
# =============================================================================

variable "hybrid_search_k" {
  description = "Number of results for hybrid search"
  type        = string
  default     = "20"
}

variable "rrf_k" {
  description = "RRF fusion parameter"
  type        = string
  default     = "60"
}

# =============================================================================
# Feature Flags (Dify v3 compatible features)
# =============================================================================

variable "use_lite_model" {
  description = "Use flash-lite model for lightweight tasks"
  type        = string
  default     = "true"
}

variable "use_query_generator" {
  description = "Enable query generation chain"
  type        = string
  default     = "true"
}

variable "use_style_profile_kb" {
  description = "Enable style profile knowledge base"
  type        = string
  default     = "true"
}

variable "use_auto_rewrite" {
  description = "Enable automatic style rewriting"
  type        = string
  default     = "true"
}

# =============================================================================
# Container image (optional - for manual override)
# =============================================================================

variable "container_image" {
  description = "Container image URL (e.g., gcr.io/project/image:tag) - optional override"
  type        = string
  default     = ""
}
