locals {
  # More granular timestamp (YYMMDDHHmm)
  timestamp  = formatdate("YYMMDDHHmm", timestamp())
  project_id = "${var.base_project_name}-${local.timestamp}"

  # Function to sanitize label values
  sanitize_label = replace(
    lower(
      replace(
        replace(var.gcp_user_email, "@", "_at_"),
        ".", "_"
      )
    ),
    "/[^a-z0-9_-]/",
    "_"
  )

  sanitize_tag = replace(lower(var.app_tag), "/[^a-z0-9_-]/", "_")

  # Define common tags with sanitized values
  common_tags = {
    created_by = local.sanitize_label
    created_at = local.timestamp
    managed_by = "terraform"
    custom_tag = local.sanitize_tag
  }
}

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.14.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
    http = {
      source  = "hashicorp/http"
      version = "~> 3.4.0"
    }
  }

  required_version = ">= 1.0.0"
}

# Define providers first, before any resources
provider "google" {
  project = var.bootstrap_project_id
}

provider "google" {
  alias   = "bacalhau_cluster_project"
  project = google_project.bacalhau_project.project_id
}

# Create new project
resource "google_project" "bacalhau_project" {
  name            = local.project_id
  project_id      = local.project_id
  org_id          = var.org_id
  billing_account = var.gcp_billing_account_id

  auto_create_network = true     # Optional: creates default network
  deletion_policy     = "DELETE" # Explicitly allow project deletion

  lifecycle {
    prevent_destroy = false
  }
}

# Enable required APIs in new project
resource "google_project_service" "project_apis" {
  provider = google.bacalhau_cluster_project
  for_each = toset([
    "compute.googleapis.com",
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
    "billingbudgets.googleapis.com"
  ])

  project = google_project.bacalhau_project.project_id
  service = each.value

  disable_dependent_services = true
  disable_on_destroy         = false
}

# Update the project_owner IAM binding to depend on APIs being enabled
resource "google_project_iam_binding" "project_owner" {
  provider = google.bacalhau_cluster_project
  project  = google_project.bacalhau_project.project_id
  role     = "roles/owner"
  members = [
    "user:${var.gcp_user_email}"
  ]
  depends_on = [google_project_service.project_apis] # Updated dependency
}

resource "google_service_account" "service_account" {
  provider     = google.bacalhau_cluster_project
  account_id   = "${local.project_id}-sa"
  display_name = "${local.project_id} Service Account"
  project      = google_project.bacalhau_project.project_id
  depends_on   = [google_project_iam_binding.project_owner]
}

resource "google_project_iam_member" "member_role" {
  provider = google.bacalhau_cluster_project
  for_each = toset([
    "roles/iam.serviceAccountUser",
    "roles/storage.admin",
  ])
  role    = each.key
  member  = "serviceAccount:${google_service_account.service_account.email}"
  project = google_project.bacalhau_project.project_id
}

data "cloudinit_config" "user_data" {

  for_each = var.locations

  gzip          = false
  base64_encode = false

  part {
    filename     = "cloud-config.yaml"
    content_type = "text/cloud-config"

    content = templatefile("${path.root}/cloud-init/init-vm.yml", {
      node_name : "${local.project_id}-${each.key}-vm",
      username : var.username,
      region : each.key,
      zone : each.value.zone,
      project_id : google_project.bacalhau_project.project_id,
      bacalhau_startup_service_file : filebase64("${path.root}/scripts/bacalhau-startup.service"),
      bacalhau_startup_script_file : filebase64("${path.root}/scripts/startup.sh"),
      bacalhau_config_file : filebase64("${path.root}/config/config.yaml"),
      bacalhau_docker_compose_file : filebase64("${path.root}/config/docker-compose.yml"),
      bacalhau_data_dir : var.bacalhau_data_dir,
      bacalhau_node_dir : var.bacalhau_node_dir,
      ssh_key : compact(split("\n", file(var.public_key)))[0],
      healthz_web_server_script_file : filebase64("${path.root}/scripts/healthz-web-server.py"),
      healthz_service_file : filebase64("${path.root}/scripts/healthz-web.service"),
    })
  }
}

resource "google_compute_firewall" "allow_ssh_nats" {
  provider = google.bacalhau_cluster_project
  project  = google_project.bacalhau_project.project_id
  name     = "${local.project_id}-allow-ssh-nats"
  network  = "default"

  allow {
    protocol = "tcp"
    ports    = ["22", "4222", "80"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["${local.project_id}-instance"]

  depends_on = [google_project_service.project_apis]
}

resource "google_compute_instance" "gcp_instance" {
  provider   = google.bacalhau_cluster_project
  project    = google_project.bacalhau_project.project_id
  depends_on = [google_project_iam_member.member_role]

  for_each = var.locations

  name         = "${local.project_id}-${each.key}-vm"
  machine_type = each.value.machine_type
  zone         = each.value.zone
  tags         = ["${local.project_id}-instance"]

  boot_disk {
    initialize_params {
      image = "projects/ubuntu-os-cloud/global/images/family/ubuntu-2410-amd64"
      size  = 50
    }
  }

  network_interface {
    network = "default"
    access_config {
      // Ephemeral IP
    }
  }

  service_account {
    email  = google_service_account.service_account.email
    scopes = ["cloud-platform"]
  }

  metadata = {
    user-data = "${data.cloudinit_config.user_data[each.key].rendered}",
    ssh-keys  = "${var.username}:${file(var.public_key)}",
  }

  labels = local.common_tags
}

# Health check for each instance
resource "time_sleep" "wait_for_startup" {
  depends_on      = [google_compute_instance.gcp_instance]
  create_duration = "5m"
}

data "http" "healthcheck" {
  for_each   = var.locations
  depends_on = [time_sleep.wait_for_startup]

  url = "http://${google_compute_instance.gcp_instance[each.key].network_interface[0].access_config[0].nat_ip}/healthz"

  retry {
    attempts     = 35
    min_delay_ms = 10000 # 10 seconds
    max_delay_ms = 10000 # 10 seconds
  }
}

output "deployment_status" {
  description = "Deployment status including health checks"
  value = {
    for k, v in google_compute_instance.gcp_instance : k => {
      name         = v.name
      external_ip  = v.network_interface[0].access_config[0].nat_ip
      health_check = try(data.http.healthcheck[k].status_code == 200, false) ? "healthy" : "failed"
    }
  }
}

# Add random string resource at the top level
resource "random_string" "suffix" {
  length  = 4
  special = false
  upper   = false
}
