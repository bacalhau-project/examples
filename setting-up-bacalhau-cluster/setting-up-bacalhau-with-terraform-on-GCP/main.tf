locals {
  # More granular timestamp (YYMMDDHHmm)
  timestamp  = formatdate("YYMMDDHHmm", timestamp())
  project_id = "${var.base_project_name}-${local.timestamp}"

  # Simplified sanitize label function - just replace non-compliant chars with "-"
  sanitize_label = replace(lower(var.gcp_user_email), "/[^a-z0-9-]/", "-")
  sanitize_tag   = replace(lower(var.app_tag), "/[^a-z0-9-]/", "-")

  # Define common tags with sanitized values
  common_tags = {
    created_by = local.sanitize_label
    created_at = local.timestamp
    managed_by = "terraform"
    custom_tag = local.sanitize_tag
  }

  # Flatten the VM instances based on count per zone from locations variable
  vm_instances = flatten([
    for zone_key, config in var.locations : [
      for i in range(lookup(config, "node_count", 1)) : {
        zone_key     = zone_key
        index        = i
        zone         = config.zone
        machine_type = config.machine_type
      }
    ]
  ])

  # Convert to map with unique keys
  vm_instances_map = {
    for instance in local.vm_instances :
    "${instance.zone_key}-${instance.index}" => instance
  }
}

terraform {
  required_providers {
    google = {
      source = "hashicorp/google"
    }
    random = {
      source = "hashicorp/random"
    }
    http = {
      source = "hashicorp/http"
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

# Link billing account to project
resource "google_billing_project_info" "billing_info" {
  project         = google_project.bacalhau_project.project_id
  billing_account = var.gcp_billing_account_id
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

  project                    = google_project.bacalhau_project.project_id
  service                    = each.value
  disable_dependent_services = true
  disable_on_destroy         = false
  depends_on                 = [google_billing_project_info.billing_info]

  # Add timeouts to give more time for API enablement
  timeouts {
    create = "30m"
    update = "40m"
  }
}

# Add explicit dependency on compute API
resource "time_sleep" "wait_for_apis" {
  depends_on = [google_project_service.project_apis]

  # Wait for 2 minutes after enabling APIs
  create_duration = "120s"
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

# Update random string to use the new map
resource "random_string" "vm_name" {
  for_each = local.vm_instances_map
  length   = 8
  special  = false
  upper    = false
}

# Update the instance and cloud-init resources to use the new map
data "cloudinit_config" "user_data" {
  for_each = local.vm_instances_map

  gzip          = false
  base64_encode = false

  part {
    filename     = "cloud-config.yaml"
    content_type = "text/cloud-config"

    content = templatefile("${path.root}/cloud-init/init-vm.yml", {
      node_name : "${replace(lower(each.value.zone), "/[^a-z0-9-]/", "-")}-${random_string.vm_name[each.key].result}-vm",
      username : var.username,
      region : each.value.zone_key,
      zone : each.value.zone,
      project_id : google_project.bacalhau_project.project_id,
      bacalhau_startup_service_file : filebase64("${path.root}/scripts/bacalhau-startup.service"),
      bacalhau_startup_script_file : filebase64("${path.root}/scripts/startup.sh"),
      bacalhau_config_file : filebase64("${path.root}/config/config.yaml"),
      docker_compose_file : filebase64("${path.root}/config/docker-compose.yml"),
      docker_install_script_file : filebase64("${path.root}/scripts/install_docker.sh"),
      bacalhau_data_dir : var.bacalhau_data_dir,
      bacalhau_node_dir : var.bacalhau_node_dir,
      public_ssh_key : compact(split("\n", file(var.public_ssh_key_path)))[0],
      healthz_web_server_script_file : filebase64("${path.root}/scripts/healthz-web-server.py"),
      healthz_service_file : filebase64("${path.root}/scripts/healthz-web.service"),
      install_docker_script_file : filebase64("${path.root}/scripts/install_docker.sh"),
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

  depends_on = [time_sleep.wait_for_apis] # Wait for APIs to be fully enabled
}

resource "google_compute_instance" "gcp_instance" {
  provider   = google.bacalhau_cluster_project
  project    = google_project.bacalhau_project.project_id
  depends_on = [google_project_iam_member.member_role]

  for_each = local.vm_instances_map

  name         = "${replace(lower(each.value.zone), "/[^a-z0-9-]/", "-")}-${random_string.vm_name[each.key].result}-vm"
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
    ssh-keys  = "${var.username}:${file(var.public_ssh_key_path)}",
  }

  labels = local.common_tags
}
