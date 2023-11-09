terraform {
  required_providers {
    google = {
      version = "~> 3.90.0"
    }
  }
}

provider "google" {
  project = var.project_id
}

resource "google_service_account" "service_account" {
  account_id   = "multicloud-imagesearch"
  display_name = "Bacalhau Example Service Account"
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

    content = templatefile("${path.root}/../cloud-init/init-vm-gcp.yml", {
      app_name : var.app_name,
      bacalhau_service : filebase64("${path.root}/../node_files/bacalhau.service"),
      ipfs_service : base64encode(file("${path.module}/../node_files/ipfs.service")),
      start_bacalhau : filebase64("${path.root}/../node_files/start-bacalhau.sh"),
      ssh_key : compact(split("\n", file(var.public_key)))[0],
      tailscale_key : var.tailscale_key,
      node_name : "${var.app_tag}-${each.key}-vm",
      username : var.username,
      region : each.value.zone,
      global_bucket_name : "{var.app_tag}-{each.value.zone}-images-bucket",
      zone : each.key,
      project_id : var.project_id,
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
      image = "projects/deeplearning-platform-release/global/images/common-cu121-v20230925-ubuntu-2004-py310"
      size  = 100
    }
  }

  # Scheduling block added to disable live migration
  scheduling {
    on_host_maintenance = "TERMINATE"
    automatic_restart   = false
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

    guest_accelerator {
    type  = "${var.accelerator}"
    count = 1
    }
}

resource "google_storage_bucket" "images_bucket" {
  for_each = var.locations

  name     = "${var.app_tag}-${each.key}-images-bucket"
  location = var.locations[each.key].storage_location

  lifecycle_rule {
    condition {
      age = "3"
    }
    action {
      type = "Delete"
    }
  }

  storage_class = "STANDARD"
  force_destroy = true
}

resource "null_resource" "copy-to-node-if-worker" {
  for_each = { for k, v in google_compute_instance.gcp_instance : k => v }

  connection {
    host        = each.value.network_interface[0].access_config[0].nat_ip
    port        = 22
    user        = var.username
    private_key = file(var.private_key)
  }

  provisioner "file" {
    destination = "/home/${var.username}/bacalhau-bootstrap"
    content     = file(var.bacalhau_run_file)
  }

  provisioner "remote-exec" {
    inline = [
    "sudo mv /home/${var.username}/bacalhau-bootstrap /etc/bacalhau-bootstrap",
    "sudo systemctl daemon-reload",
    "sudo systemctl restart bacalhau.service",
    ]
  }
}
