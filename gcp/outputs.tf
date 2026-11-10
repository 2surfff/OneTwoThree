output "cloud_run_url" {
  description = "Public HTTPS URL of the deployed Cloud Run FastAPI backend service"
  value       = google_cloud_run_v2_service.backend.uri
}

output "artifact_registry_repo" {
  description = "Full Artifact Registry Docker repository path for docker build & push"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.backend_repo.repository_id}"
}

output "cloud_sql_connection_name" {
  description = "Cloud SQL instance connection name (project:region:instance) for Cloud SQL Auth Proxy"
  value       = google_sql_database_instance.postgres.connection_name
}

output "cloud_sql_public_ip" {
  description = "Public IPv4 address of the Cloud SQL PostgreSQL instance"
  value       = google_sql_database_instance.postgres.public_ip_address
}

output "backend_service_account_email" {
  description = "Email of the dedicated least-privilege Service Account running Cloud Run"
  value       = google_service_account.backend_sa.email
}
