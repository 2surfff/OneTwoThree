variable "project_id" {
  description = "Google Cloud Project ID"
  type        = string
  default     = "spry-anton-2026"
}

variable "region" {
  description = "Primary GCP region for Cloud Run, Cloud SQL, and Artifact Registry"
  type        = string
  default     = "us-central1"
}

variable "project_name" {
  description = "Application name prefix used for naming GCP resources"
  type        = string
  default     = "spry"
}

variable "environment" {
  description = "Deployment environment name (e.g. dev, prod)"
  type        = string
  default     = "dev"
}

variable "container_image" {
  description = "Full Docker image URI in Artifact Registry for Cloud Run backend"
  type        = string
  default     = "us-central1-docker.pkg.dev/spry-anton-2026/spry-repo/backend:latest"
}

variable "db_name" {
  description = "PostgreSQL database name in Cloud SQL"
  type        = string
  default     = "spry"
}

variable "db_user" {
  description = "PostgreSQL application username in Cloud SQL"
  type        = string
  default     = "spry_user"
}
