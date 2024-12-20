terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~>6.13.0"
    }
  }
}

provider "google" {
  project = var.project_id
}

# Validate required files exist
locals {
  required_files = {
    # Bacalhau files
    bacalhau_service    = fileexists("${path.module}/node_files/bacalhau.service")
    start_bacalhau      = fileexists("${path.module}/node_files/start_bacalhau.sh")
    orchestrator_config = fileexists("${path.module}/node_files/orchestrator-config.yaml")
  }

  # Check if any required files are missing
  missing_files = [for name, exists in local.required_files : name if !exists]

  # Fail if any files are missing
  validate_files = length(local.missing_files) == 0 ? true : tobool(
    "Missing required files: ${join(", ", local.missing_files)}"
  )
}

# Debug outputs to verify file reading
output "debug_files" {
  value = {
    files_exist = local.required_files
    file_contents = {
      bacalhau_service = fileexists("${path.module}/node_files/bacalhau.service") ? filebase64("${path.module}/node_files/bacalhau.service") : "missing"
    }
  }
}

# Service account for GCP resources
resource "google_service_account" "service_account" {
  account_id   = "${var.project_id}-sa"
  display_name = "Bacalhau Service Account"
}

# Service account needs both serviceAccountUser and storage.admin roles
resource "google_project_iam_member" "member_role" {
  for_each = toset([
    "roles/iam.serviceAccountUser",
    "roles/storage.admin",
  ])
  role    = each.key
  member  = "serviceAccount:${google_service_account.service_account.email}"
  project = var.project_id
}

# Cloud-init configuration
data "cloudinit_config" "user_data" {
  for_each = var.locations

  gzip          = false
  base64_encode = false

  part {
    filename     = "cloud-config.yaml"
    content_type = "text/cloud-config"

    content = templatefile("${path.module}/cloud-init/init-vm.yml", {
      # Instance configuration
      bacalhau_service         = filebase64("${path.module}/node_files/bacalhau.service")
      start_bacalhau           = filebase64("${path.module}/node_files/start_bacalhau.sh")
      orchestrator_config      = filebase64("${path.module}/node_files/orchestrator-config.yaml")
      bacalhau_installation_id = var.bacalhau_installation_id
      ssh_key                  = compact(split("\n", file(var.public_key)))[0]
      username                 = var.username
      region                   = each.value.region
      zone                     = each.key
      project_id               = var.project_id
      global_bucket_name       = "${var.project_id}-global-archive-bucket"
    })
  }
}

# Compute instance
resource "google_compute_instance" "gcp_instance" {
  depends_on = [google_project_iam_member.member_role]

  for_each = var.locations

  name         = "${var.app_name}-${each.key}-vm"
  machine_type = var.machine_type
  zone         = each.key

  boot_disk {
    initialize_params {
      image = "projects/ubuntu-os-cloud/global/images/family/ubuntu-2204-lts"
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
    user-data = data.cloudinit_config.user_data[each.key].rendered
    ssh-keys  = "${var.username}:${file(var.public_key)}"
  }
}

# Storage buckets
resource "google_storage_bucket" "node_bucket" {
  for_each = var.locations

  name     = "${var.project_id}-${each.key}-archive-bucket"
  location = regex("^([a-z]+-[a-z]+[0-9])", each.key)[0]

  lifecycle_rule {
    condition {
      age = "3"
    }
    action {
      type = "Delete"
    }
  }

  uniform_bucket_level_access = true
  storage_class               = "ARCHIVE"
  force_destroy               = true
}

resource "google_storage_bucket" "global_archive_bucket" {
  for_each = { for k, v in var.locations : k => v if k == keys(var.locations)[0] }

  name     = "${var.project_id}-global-archive-bucket"
  location = regex("^([a-z]+-[a-z]+[0-9])", each.key)[0]

  lifecycle_rule {
    condition {
      age = "3"
    }
    action {
      type = "Delete"
    }
  }

  storage_class               = "ARCHIVE"
  force_destroy               = true
  uniform_bucket_level_access = true
}

