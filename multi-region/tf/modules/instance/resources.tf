
data "cloudinit_config" "user_data" {
  gzip          = false
  base64_encode = false

  part {
    filename     = "cloud-config.yaml"
    content_type = "text/cloud-config"

    content = templatefile("${path.module}/../../cloud-init/init-vm.yml", {
      bacalhau_service : base64encode(file("${path.module}/../../node_files/bacalhau.service")),
      start_bacalhau : base64encode(file("${path.module}/../../node_files/start-bacalhau.sh")),
      tailscale_key : var.tailscale_key
      node_name : "${var.app_tag}-${var.region}-vm"
      ssh_key : compact(split("\n", file(var.public_key)))[0]
    })
  }
}

resource "aws_instance" "instance" {
  ami                    = var.instance_ami
  instance_type          = var.instance_type
  subnet_id              = var.subnet_public_id
  vpc_security_group_ids = var.security_group_ids
  key_name               = var.key_pair_name
  availability_zone      = var.availability_zone
  user_data              = data.cloudinit_config.user_data.rendered

  tags = {
    App  = var.app_tag
    Name = "${var.app_tag}-vm"
  }
}

resource "aws_eip" "instanceeip" {
  vpc      = true
  instance = aws_instance.instance.id

  tags = {
    App = var.app_tag
  }
}

# resource "null_resource" "copy-to-node-if-worker" {
#   count = var.bootstrap_region == var.region ? 0 : 1

#   connection {
#     host        = aws_eip.instanceeip.public_ip
#     port        = 22
#     user        = var.shelluser
#     private_key = file(var.private_key)
#   }

#   provisioner "file" {
#     destination = "/etc/bacalhau-bootstrap"
#     content     = file(var.bacalhau_run_file)
#   }
# }

# resource "null_resource" "copy-bacalhau-bootstrap-to-local" {
#   count = var.bootstrap_region == var.region ? 1 : 0

#   depends_on = [aws_instance.instance]

#   connection {
#     host        = aws_instance.instance.public_dns
#     port        = 22
#     user        = var.shelluser
#     private_key = file(var.private_key)
#     timeout     = 600
#   }

#   provisioner "file" {
#     source      = "/run/bacalhau.run"
#     destination = var.bacalhau_run_file
#   }
# }
