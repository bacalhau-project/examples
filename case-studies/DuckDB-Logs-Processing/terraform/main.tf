provider "google" {
  project = var.project_id
}

resource "google_service_account" "service_account" {
  account_id   = "bacalhau-duckdb-example-service-account"
  display_name = "Bacalhau DuckDB Example Service Account"
}

resource "google_service_account_iam_binding" "storage_iam" {
  service_account_id = google_service_account.service_account.id
  role               = "roles/iam.serviceAccountUser"

  members = [
    google_service_account.service_account.email,
  ]
}

data "cloudinit_config" "user_data" {
  gzip          = false
  base64_encode = false

  part {
    filename     = "cloud-config.yaml"
    content_type = "text/cloud-config"

    content = templatefile("${path.module}/cloud-init/init-vm.yml", {
      app_name : var.app_name,

      bacalhau_service : base64encode(file("${path.module}/node_files/bacalhau.service")),
      start_bacalhau : base64encode(file("${path.module}/node_files/start-bacalhau.sh")),
      logs_dir : "/var/logs/${var.app_name}_logs",
      log_generator_py : base64encode(file("${path.module}/node_files/log_generator.py")),
      logs_to_process_dir : "/var/logs/${var.app_name}_logs_to_process",

      # Need to do the below to remove spaces and newlines from public key
      ssh_key : compact(split("\n", file(var.public_key)))[0],

      tailscale_key : var.tailscale_key,
      node_name : "${var.app_tag}-${var.region}-vm",
    })
  }
}


resource "google_compute_instance" "gcp_instance" {
  for_each = local.node_configs

  name         = each.key
  machine_type = each.value.machine_type
  zone         = each.value.zone

  boot_disk {
    initialize_params {
      image = "projects/ubuntu-os-cloud/global/images/family/ubuntu-2004-lts"
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

  metadata_startup_script = {
    user-data = "${data.template_cloudinit_config.instance_user_data.rendered}"
  }
}

resource "google_storage_bucket" "node_bucket" {
  for_each = { for k, v in local.node_configs : k => v if v.create_bucket }

  name     = "${var.project_id}-${each.key}-archive-bucket"
  location = local.node_configs[each.key].storage_location

  lifecycle_rule {
    condition {
      age = "3"
    }
    action {
      type = "Delete"
    }
  }

  storage_class = "ARCHIVE"
}
