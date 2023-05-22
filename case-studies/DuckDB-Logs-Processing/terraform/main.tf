provider "google" {
  project = var.project_id
  region  = "us-central1"
}

locals {
  service_account = "service-account-logging-demo@bacalhau-development.iam.gserviceaccount.com"

  node_configs = {
    "us-central1-a-node" = {
      zone         = "us-central1-a"
      machine_type = var.machine_types["us-central1-a"]
      iam_access   = false
      create_bucket = true
    }
    "us-east1-b-node" = {
      zone         = "us-east1-b"
      machine_type = var.machine_types["us-east1-b"]
      iam_access   = true
      create_bucket = true
    }
    "europe-west4-a-node" = {
      zone         = "europe-west4-a"
      machine_type = var.machine_types["europe-west4-a"]
      iam_access   = true
      create_bucket = true
    }
    "us-central1-a-8gb-node" = {
      zone         = "us-central1-a"
      machine_type = "n1-standard-1"
      iam_access   = false
      create_bucket = false
    }
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
    email  = local.service_account
    scopes = ["cloud-platform"]
  }

  metadata_startup_script = <<-EOT
    #!/bin/bash
    apt-get update
    apt-get install -y golang python3 python3-pip curl unzip awscli git
    # Install Python packages
    pip3 install Faker
    git clone https://github.com/js-ts/logrotate
    cd logrotate
    chmod +x ./log-rotate.sh
    sudo ./log-rotate.sh
	  # Install Docker
    apt-get update
    apt-get install -y docker.io
    systemctl start docker
    systemctl enable docker



    # Install IPFS
    wget https://dist.ipfs.io/go-ipfs/v0.9.1/go-ipfs_v0.9.1_linux-amd64.tar.gz
    tar xvf go-ipfs_v0.9.1_linux-amd64.tar.gz
    cd go-ipfs
    sudo bash install.sh
    ipfs init
    systemctl start ipfs
    systemctl enable ipfs

    curl -sL https://get.bacalhau.org/install.sh | bash
  EOT
}

resource "google_storage_bucket" "node_bucket" {
  for_each = { for k, v in local.node_configs : k => v if v.create_bucket }
  
  name     = "${each.key}-archive-bucket"
  location = "US"

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