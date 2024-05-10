provider "google" {
	project = var.project_id
}

# Archive the scripts folder
data "archive_file" "scripts" {
	type        = "zip"
	source_dir  = "../scripts/"
	output_path = "../scripts.zip"
}

resource "google_storage_bucket" "public_bucket" {
  name     = var.bucket_name
  location = "US"
  force_destroy = true
}

# Set public read access on the bucket
resource "google_storage_bucket_iam_binding" "public_read" {
  bucket = google_storage_bucket.public_bucket.name
  role   = "roles/storage.objectViewer"
  members = [
    "allUsers"
  ]
}

resource "google_compute_firewall" "http" {
	name    = "allow-public-access"
	network = "default"

	allow {
		protocol = "tcp"
		ports    = ["80", "443", "1234", "4001", "4222", "5001", "8080", "43167", "42717"]
	}

	source_ranges = ["0.0.0.0/0"]
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
      poller_service : filebase64("${path.root}/node_files/poller.service"),
      stress_service : filebase64("${path.root}/node_files/stress.service"),
      ipfs_service : base64encode(file("${path.module}/node_files/ipfs.service")),
      start_bacalhau : filebase64("${path.root}/node_files/start_bacalhau.sh"),

      scripts_bucket_source: "${google_storage_bucket_object.zip_file.bucket}",
      scripts_object_key : "${google_storage_bucket_object.zip_file.name}",
      # Need to do the below to remove spaces and newlines from public key
      ssh_key : compact(split("\n", file(var.public_key)))[0],

      node_name : "${var.app_tag}-${each.key}-vm",
      username : var.username,
      region : each.value.region,
      zone : each.key,
      project_id : var.project_id,
    })
  }
}

resource "google_storage_bucket_object" "zip_file" {
	name   = "scripts.zip"
	bucket = var.bucket_name
	source = "../scripts.zip"
  depends_on = [google_storage_bucket.public_bucket]
}

resource "google_compute_instance" "gcp_instance" {
	for_each = var.locations

	# Execute a local command to print out the key
	provisioner "local-exec" {
		command = "echo 'Non-bootstrapped instance key: ${each.key}'"
	}

	name         = "${var.app_name}-${each.key}"
	machine_type = "${var.machine_type}"
	zone         = "${each.key}"

	boot_disk {
		initialize_params {
			image = "ubuntu-os-cloud/ubuntu-2004-lts"
			size = 20
		}
	}

	network_interface {
		network = "default"
		access_config {}
	}

	metadata = {
		user-data = "${data.cloudinit_config.user_data[each.key].rendered}",
		ssh-keys  = "${var.username}:${file(var.public_key)}",
	}

}


resource "null_resource" "configure_requester_node" {
  // Only run this on the bootstrap node
  for_each = { for k, v in google_compute_instance.gcp_instance : k => v if v.zone == var.bootstrap_zone }

  depends_on = [google_compute_instance.gcp_instance]

  connection {
    host        = each.value.network_interface[0].access_config[0].nat_ip
    port        = 22
    user        = var.username
    agent = true
  }

  provisioner "remote-exec" {
    inline = [
      "echo 'SSHD is now alive.'",
      "echo 'Hello, world.'",
	  "sudo timeout 600 bash -c 'until [[ -s /data/bacalhau.run ]]; do sleep 1; done' && echo 'Bacalhau is now alive.'",
    ]
  }

  provisioner "local-exec" {
    command = "ssh -o StrictHostKeyChecking=no ${var.username}@${each.value.network_interface[0].access_config[0].nat_ip} 'sudo cat /etc/bacalhau-bootstrap' > ${var.bacalhau_run_file}"
  }
}

resource "null_resource" "configure_compute_node" {
  // Only run this on worker nodes, not the bootstrap node
  for_each = { for k, v in google_compute_instance.gcp_instance : k => v if v.zone != var.bootstrap_zone }

  depends_on = [null_resource.configure_requester_node]

  connection {
    host        = each.value.network_interface[0].access_config[0].nat_ip
    port        = 22
    user        = var.username
    agent = true
  }

  provisioner "file" {
    destination = "/home/${var.username}/bacalhau-bootstrap"
    content     = file(var.bacalhau_run_file)
  }

  provisioner "local-exec" {
    command = "Echo 'I Ran'"
  }

  provisioner "remote-exec" {
    inline = [
      "sudo mv /home/${var.username}/bacalhau-bootstrap /etc/bacalhau-bootstrap",
      "sudo systemctl daemon-reload",
      "sudo systemctl restart bacalhau.service",
	  "echo 'Restarted Bacalhau Compute node'",
    ]
  }
}
