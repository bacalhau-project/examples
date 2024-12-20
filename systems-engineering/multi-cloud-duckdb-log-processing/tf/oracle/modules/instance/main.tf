# Oracle Instance Module

resource "oci_core_instance" "vm" {
  availability_domain = data.oci_identity_availability_domain.ad.name
  compartment_id      = var.compartment_id
  display_name        = "${var.app_tag}-vm"
  shape               = var.instance_shape

  create_vnic_details {
    subnet_id        = var.subnet_id
    nsg_ids          = var.nsg_ids
    assign_public_ip = true
  }

  source_details {
    source_type = "image"
    source_id   = data.oci_core_images.ubuntu_image.images[0].id
  }

  metadata = {
    ssh_authorized_keys = file(var.public_key)
    user_data          = base64encode(data.cloudinit_config.user_data.rendered)
  }

  freeform_tags = {
    "App" = var.app_tag
  }
}

data "oci_identity_availability_domain" "ad" {
  compartment_id = var.compartment_id
  ad_number      = 1
}

data "oci_core_images" "ubuntu_image" {
  compartment_id           = var.compartment_id
  operating_system         = "Canonical Ubuntu"
  operating_system_version = "22.04"
  shape                    = var.instance_shape
  sort_by                  = "TIMECREATED"
  sort_order              = "DESC"
}

data "cloudinit_config" "user_data" {
  gzip          = false
  base64_encode = false

  part {
    filename     = "cloud-config.yaml"
    content_type = "text/cloud-config"

    content = templatefile("${path.root}/../cloud-init/init-vm.yml", {
      bacalhau_service : base64encode(file("${path.root}/../node_files/bacalhau.service")),
      ipfs_service : base64encode(file("${path.root}/../node_files/ipfs.service")),
      start_bacalhau : base64encode(file("${path.root}/../node_files/start-bacalhau.sh")),
      logs_dir : "/var/log/${var.app_tag}_logs",
      log_generator_py : filebase64("${path.root}/../node_files/log_generator.py"),
      tailscale_key : var.tailscale_key,
      node_name : "${var.app_tag}-${var.region}-vm",
      ssh_key : compact(split("\n", file(var.public_key)))[0],
      region : var.region,
      zone : var.region
    })
  }
}

resource "oci_objectstorage_bucket" "bucket" {
  compartment_id = var.compartment_id
  name           = "${var.app_tag}-${var.region}-bucket"
  namespace      = data.oci_objectstorage_namespace.ns.namespace
  access_type    = "NoPublicAccess"

  freeform_tags = {
    "App" = var.app_tag
  }
}

data "oci_objectstorage_namespace" "ns" {
  compartment_id = var.compartment_id
}

resource "null_resource" "copy-bacalhau-bootstrap-to-local" {
  count = var.bootstrap_region == var.region ? 1 : 0

  depends_on = [oci_core_instance.vm]

  connection {
    host        = oci_core_instance.vm.public_ip
    user        = var.ssh_user
    private_key = file(var.private_key)
  }

  provisioner "remote-exec" {
    inline = [
      "echo 'SSHD is now alive.'",
      "timeout 300 bash -c 'until [[ -s /data/bacalhau.run ]]; do sleep 1; done'",
      "echo 'Bacalhau is now alive.'",
    ]
  }

  provisioner "local-exec" {
    command = "ssh -o StrictHostKeyChecking=no ${var.ssh_user}@${oci_core_instance.vm.public_ip} 'sudo cat /data/bacalhau.run' > ${var.bacalhau_run_file}"
  }
}

resource "null_resource" "copy-to-node-if-worker" {
  count = var.bootstrap_region == var.region ? 0 : 1

  connection {
    host        = oci_core_instance.vm.public_ip
    user        = var.ssh_user
    private_key = file(var.private_key)
  }

  provisioner "file" {
    destination = "/home/${var.ssh_user}/bacalhau-bootstrap"
    content     = file(var.bacalhau_run_file)
  }

  provisioner "remote-exec" {
    inline = [
      "sudo mv /home/${var.ssh_user}/bacalhau-bootstrap /etc/bacalhau-bootstrap",
      "sudo systemctl daemon-reload",
      "sudo systemctl restart bacalhau.service",
    ]
  }
}
