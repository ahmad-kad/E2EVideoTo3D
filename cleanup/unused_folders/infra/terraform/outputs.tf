output "kubernetes_cluster_name" {
  value       = google_container_cluster.photogrammetry.name
  description = "The name of the GKE cluster"
}

output "kubernetes_cluster_endpoint" {
  value       = google_container_cluster.photogrammetry.endpoint
  description = "The endpoint for the GKE cluster"
  sensitive   = true
}

output "minio_endpoint" {
  value       = "http://photogrammetry-store-minio.default.svc.cluster.local:9000"
  description = "The internal endpoint for MinIO"
}

output "airflow_endpoint" {
  value       = "http://airflow-webserver.default.svc.cluster.local:8080"
  description = "The internal endpoint for Airflow"
} 