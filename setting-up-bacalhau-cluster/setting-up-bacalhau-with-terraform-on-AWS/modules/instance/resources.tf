resource "random_string" "suffix" {
  count   = var.node_count
  length  = 8
  special = false
  upper   = false
  # Avoid confusing characters
  override_special = "!@#$%&*()-_=+[]{}<>:?"
}

locals {
  vm_names   = [for i in range(var.node_count) : "${var.app_tag}-${var.region}-${random_string.suffix[i].result}"]
  role_names = [for i in range(var.node_count) : "vm-role-${random_string.suffix[i].result}"]
}

resource "aws_iam_role" "vm_iam_role" {
  count              = var.node_count
  name               = local.role_names[count.index]
  assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Effect": "Allow",
      "Sid": ""
    }
  ]
}
EOF
}

resource "aws_iam_instance_profile" "vm_instance_profile" {
  count = var.node_count
  name  = local.role_names[count.index]
  role  = aws_iam_role.vm_iam_role[count.index].name
}

resource "aws_instance" "instance" {
  count                  = var.node_count
  ami                    = var.instance_ami
  instance_type          = var.aws_instance_type
  subnet_id              = var.subnet_public_id
  vpc_security_group_ids = var.security_group_ids
  availability_zone      = var.zone
  user_data              = data.cloudinit_config.user_data[count.index].rendered
  iam_instance_profile   = aws_iam_instance_profile.vm_instance_profile[count.index].name

  tags = {
    App  = var.app_tag
    Name = local.vm_names[count.index]
  }
}

resource "aws_eip" "instanceeip" {
  count    = var.node_count
  instance = aws_instance.instance[count.index].id

  tags = {
    App = var.app_tag
  }
}

data "cloudinit_config" "user_data" {
  count         = var.node_count
  gzip          = true
  base64_encode = true

  part {
    filename     = "cloud-config.yaml"
    content_type = "text/cloud-config"

    content = templatefile("${path.module}/cloud-init/init-vm.yml", {
      bacalhau_startup_service_file : base64encode(file("${path.module}/scripts/bacalhau-startup.service")),
      bacalhau_startup_script_file : base64encode(file("${path.module}/scripts/startup.sh")),
      bacalhau_config_file : base64encode(file(var.bacalhau_config_file_path)),
      bacalhau_data_dir : var.bacalhau_data_dir,
      bacalhau_node_dir : var.bacalhau_node_dir,
      docker_compose_file : base64encode(file("${path.module}/config/docker-compose.yml")),
      healthz_web_server_script_file : base64encode(file("${path.module}/scripts/healthz-web-server.py")),
      healthz_service_file : base64encode(file("${path.module}/scripts/healthz-web.service")),
      node_name : local.vm_names[count.index]
      username : var.username
      ssh_key : var.public_key
      region : var.region
      zone : var.zone
      app_name : var.app_tag
    })
  }
}

