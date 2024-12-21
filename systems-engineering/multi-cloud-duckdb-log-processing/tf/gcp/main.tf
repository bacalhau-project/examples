terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~>6.13.0"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
}

locals {
  required_files = {
    bacalhau_service    = fileexists("${path.module}/node_files/bacalhau.service")
    start_bacalhau      = fileexists("${path.module}/node_files/start_bacalhau.sh")
    orchestrator_config = fileexists(var.orchestrator_config_path)
  }

  missing_files = [for name, exists in local.required_files : name if !exists]

  validate_files = length(local.missing_files) == 0 ? true : tobool(
    "Missing required files: ${join(", ", local.missing_files)}"
  )
}

resource "google_service_account" "service_account" {
  account_id   = "${var.app_name}-sa"
  display_name = "Bacalhau Service Account"
}

resource "google_project_iam_member" "member_role" {
  for_each = toset([
    "roles/iam.serviceAccountUser",
    "roles/storage.admin",
  ])
  role    = each.key
  member  = "serviceAccount:${google_service_account.service_account.email}"
  project = var.gcp_project_id
}

data "cloudinit_config" "user_data" {
  for_each = toset(var.gcp_regions)

  gzip          = false
  base64_encode = false

  part {
    filename     = "cloud-config.yaml"
    content_type = "text/cloud-config"

    content = templatefile("${path.module}/../cloud-init/init-vm.yml", {
      bacalhau_service         = filebase64("${path.module}/node_files/bacalhau.service")
      start_bacalhau          = filebase64("${path.module}/node_files/start_bacalhau.sh")
      orchestrator_config     = filebase64(var.orchestrator_config_path)
      bacalhau_installation_id = var.bacalhau_installation_id
      ssh_key                = compact(split("\n", file(var.public_key)))[0]
      username              = var.username
      region               = each.value
      project_id           = var.gcp_project_id
      central_bucket_name  = var.central_logging_bucket
    })
  }
}

resource "google_compute_instance" "gcp_instance" {
  count = var.instances_per_region * length(var.gcp_regions)

  name         = "${var.app_name}-${var.gcp_regions[floor(count.index / var.instances_per_region)]}-vm-${count.index % var.instances_per_region + 1}"
  machine_type = var.gcp_machine_type
  zone         = "${var.gcp_regions[floor(count.index / var.instances_per_region)]}-a"
  tags         = ["${var.app_name}"]

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
    user-data = data.cloudinit_config.user_data[var.gcp_regions[floor(count.index / var.instances_per_region)]].rendered
    ssh-keys  = "${var.username}:${file(var.public_key)}"
  }
}

resource "google_storage_bucket" "node_bucket" {
  count = var.buckets_per_region * length(var.gcp_regions)

  name     = "${var.gcp_project_id}-${var.gcp_regions[floor(count.index / var.buckets_per_region)]}-bucket-${count.index % var.buckets_per_region + 1}"
  location = var.gcp_regions[floor(count.index / var.buckets_per_region)]

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
  force_destroy              = true
}

resource "google_compute_firewall" "allow_storage" {
  name    = "${var.app_name}-allow-storage"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["443"]
  }

  direction = "EGRESS"
  destination_ranges = [
    "storage.googleapis.com",
    "*.storage.googleapis.com"
  ]

  target_tags = ["${var.app_name}"]
}

resource "google_storage_bucket" "central_logging_bucket" {
  count    = 1
  name     = var.central_logging_bucket
  location = var.central_logging_region

  lifecycle_rule {
    condition {
      age = "30"
    }
    action {
      type = "Delete"
    }
  }

  uniform_bucket_level_access = true
  storage_class              = "STANDARD"
  force_destroy             = true
}

