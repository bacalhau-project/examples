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
  account_id   = "motherduck-bacalhau-sa"
  display_name = "MotherDuck Bacalhau Service Account"
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

      bacalhau_service : filebase64("${path.root}/node_files/bacalhau.service"),
      ipfs_service : base64encode(file("${path.module}/node_files/ipfs.service")),
      start_bacalhau : filebase64("${path.root}/node_files/start_bacalhau.sh"),
      logs_dir : "/var/log/${var.app_name}_logs",
      log_generator_py : filebase64("${path.root}/node_files/log_generator.py"),
      global_bucket_name : "${var.project_id}-global-archive-bucket",

      # Need to do the below to remove spaces and newlines from public key
      ssh_key : compact(split("\n", file(var.public_key)))[0],

      tailscale_key : var.tailscale_key,
      motherduck_key : var.motherduck_key,
      node_name : "${var.app_tag}-${each.key}-vm",
      username : var.username,
      region : each.value.region,
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
      image = "projects/ubuntu-os-cloud/global/images/family/ubuntu-2304-amd64"
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
}

resource "null_resource" "copy-bacalhau-bootstrap-to-local" {
  // Only run this on the bootstrap node
  for_each = { for k, v in google_compute_instance.gcp_instance : k => v if v.zone == var.bootstrap_zone }

  depends_on = [google_compute_instance.gcp_instance]

  connection {
    host        = each.value.network_interface[0].access_config[0].nat_ip
    port        = 22
    user        = var.username
    private_key = file(var.private_key)
  }

  provisioner "remote-exec" {
    inline = [
      "echo 'SSHD is now alive.'",
      "sudo timeout 300 bash -c 'until [[ -s /data/bacalhau.run ]]; do sleep 1; done' && echo 'Bacalhau is now alive.'",
    ]
  }

  provisioner "local-exec" {
    command = "ssh -o StrictHostKeyChecking=no ${var.username}@${each.value.network_interface[0].access_config[0].nat_ip} 'sudo cat /data/bacalhau.run' > ${var.bacalhau_run_file}"
  }
}

resource "null_resource" "copy-to-node-if-worker" {
  // Only run this on worker nodes, not the bootstrap node
  for_each = { for k, v in google_compute_instance.gcp_instance : k => v if v.zone != var.bootstrap_zone }

  depends_on = [null_resource.copy-bacalhau-bootstrap-to-local]

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

