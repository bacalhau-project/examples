terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~>5.7.0"
    }
  }
}

provider "google" {
  project = var.project_id
}

locals {
  username = "${var.app_name}runner"
  appdir   = "/home/${local.username}/${var.app_name}app"
}


resource "google_service_account" "service_account" {
  account_id   = "${var.project_id}-sa"
  display_name = "Hydra Example Service Account"
}

resource "google_project_iam_member" "member_role" {
  for_each = toset([
    "roles/iam.serviceAccountUser",
    "roles/storage.admin",
  ])
  role    = each.key
  member  = "serviceAccount:${google_service_account.service_account.email}"
  project = var.project_id
}

data "cloudinit_config" "user_data" {

  for_each = var.locations

  gzip          = false
  base64_encode = false

  part {
    filename     = "cloud-config.yaml"
    content_type = "text/cloud-config"

    content = templatefile("cloud-init/init-vm.yml", {
      app_name : var.app_name,
      siteurl : var.siteurl

      bacalhau_service : filebase64("${path.root}/node_files/bacalhau.service"),
      start_bacalhau : filebase64("${path.root}/node_files/start_bacalhau.sh"),
      install_gunicorn_services : filebase64("${path.root}/node_files/install_gunicorn_services.sh"),
      setup_venv : filebase64("${path.root}/node_files/setup_venv.sh"),

      bacalhau_bootstrap : filebase64("${path.root}/bacalhau.run"),

      # Need to do the below to remove spaces and newlines from public key
      ssh_key : compact(split("\n", file(var.public_key)))[0],

      node_name : "${var.app_tag}-${each.key}-vm",
      username : "${local.username}",
      appdir: "${local.appdir}",
      region : each.value.region,
      zone : each.key,
      project_id : var.project_id,
      relativecodeinrepodir : var.relativecodeinrepodir,
      token : var.token,
    })
  }
}

resource "google_compute_instance" "gcp_instance" {
  depends_on = [google_project_iam_member.member_role]

  for_each = var.locations

  name         = "${var.app_name}-${each.key}-vm"
  machine_type = var.machine_type
  zone         = each.key

  boot_disk {
    initialize_params {
      image = "projects/ubuntu-os-cloud/global/images/family/ubuntu-2204-lts"
      size  = 10
    }
  }

  network_interface {
    network = "global-network"
    access_config {
      // Ephemeral IP
    }
  }

  service_account {
    email  = google_service_account.service_account.email
    scopes = ["cloud-platform"]
  }

  metadata = {
    enable-oslogin = "true"
    user-data = "${data.cloudinit_config.user_data[each.key].rendered}",
    ssh-keys  = "${local.username}:${file(var.public_key)}",
  }

  scheduling {
    preemptible  = false
    automatic_restart = true
    on_host_maintenance = "MIGRATE"
  }


  shielded_instance_config {
    enable_secure_boot = false
    enable_vtpm        = true
    enable_integrity_monitoring = true
  }

  labels = {
    goog-ec-src = "vm_add-gcloud"
  }

  allow_stopping_for_update = true

  tags = ["allow-ssh", "allow-bacalhau", "default-allow-internal"]
}
