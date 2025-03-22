# Terraform configuration for the photogrammetry pipeline infrastructure

provider "google" {
  project     = var.project_id
  region      = var.region
  zone        = var.zone
}

# Create a GKE cluster for photogrammetry
resource "google_container_cluster" "photogrammetry" {
  name               = "auto-scaling-cluster"
  location           = var.region
  initial_node_count = 3
  
  autoscaling {
    min_node_count = 1
    max_node_count = 10
  }
  
  node_config {
    machine_type = "e2-medium"  # Free-tier eligible
    oauth_scopes = ["https://www.googleapis.com/auth/devstorage.read_only"]
  }
}

# Create a NodePool for GPU workloads
resource "google_container_node_pool" "gpu_nodes" {
  name       = "gpu-pool"
  cluster    = google_container_cluster.photogrammetry.name
  location   = var.region
  node_count = 1
  
  management {
    auto_repair  = true
    auto_upgrade = true
  }
  
  node_config {
    machine_type = "n1-standard-4"
    
    guest_accelerator {
      type  = "nvidia-tesla-t4"
      count = 1
    }
    
    oauth_scopes = [
      "https://www.googleapis.com/auth/devstorage.read_only",
      "https://www.googleapis.com/auth/logging.write",
      "https://www.googleapis.com/auth/monitoring",
    ]
  }
}

# Helm release for MinIO deployment
resource "helm_release" "minio" {
  name       = "photogrammetry-store"
  repository = "https://helm.min.io/"
  chart      = "minio"
  
  set {
    name  = "persistence.size"
    value = "20Gi"  # Compliant with free-tier limitations
  }
  
  set {
    name  = "service.type"
    value = "ClusterIP"
  }
  
  set {
    name  = "environment.MINIO_BROWSER_REDIRECT_URL"
    value = "https://minio.${var.domain}"
  }
}

# Helm release for Airflow deployment
resource "helm_release" "airflow" {
  name       = "airflow"
  repository = "https://airflow.apache.org"
  chart      = "airflow"
  
  set {
    name  = "executor"
    value = "KubernetesExecutor"
  }
  
  set {
    name  = "webserver.service.type"
    value = "ClusterIP"
  }
  
  set {
    name  = "webserver.defaultUser.enabled"
    value = "true"
  }
  
  set {
    name  = "webserver.defaultUser.username"
    value = "admin"
  }
  
  set {
    name  = "webserver.defaultUser.password"
    value = var.airflow_admin_password
  }
} 