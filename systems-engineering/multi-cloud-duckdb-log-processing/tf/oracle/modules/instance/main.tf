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

    content = templatefile("${path.module}/../../cloud-init/init-vm.yml", {
      bacalhau_service : base64encode(file("${path.module}/../../node_files/bacalhau.service")),
      ipfs_service : base64encode(file("${path.module}/../../node_files/ipfs.service")),
      start_bacalhau : base64encode(file("${path.module}/../../node_files/start-bacalhau.sh")),
      logs_dir : "/var/log/${var.app_tag}_logs",
      log_generator_py : filebase64("${path.module}/../../node_files/log_generator.py"),
      node_name : "${var.app_tag}-${var.region}-vm",
      ssh_key : compact(split("\n", file(var.public_key)))[0],
      region : var.region,
      zone : var.region
    })
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

resource "null_resource" "configure_instance" {
  depends_on = [oci_core_instance.vm]

  connection {
    host        = oci_core_instance.vm.public_ip
    port        = 22
    user        = var.username
  }

  provisioner "file" {
    source      = var.orchestrator_config_path
    destination = "/home/${var.username}/orchestrator-config.yaml"
  }

  provisioner "remote-exec" {
    inline = [
      "sudo mkdir -p /etc/bacalhau",
      "sudo mv /home/${var.username}/orchestrator-config.yaml /etc/bacalhau/orchestrator-config.yaml",
      "sudo systemctl daemon-reload",
      "sudo systemctl restart bacalhau.service"
    ]
  }
}
