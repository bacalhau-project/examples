resource "random_string" "prefix" {
  count   = var.node_count
  length  = 8
  special = false
  upper   = false
  # Avoid confusing characters
  override_special = "!@#$%&*()-_=+[]{}<>:?"
}

locals {
  # Create a list of random prefixes, one for each instance
  instance_prefixes = [for i in range(var.node_count) : random_string.prefix[i].result]

  # Use the same prefix for both VM and role names for each instance
  vm_names   = [for i in range(var.node_count) : "${local.instance_prefixes[i]}-${i}-vm"]
  role_names = [for i in range(var.node_count) : "${local.instance_prefixes[i]}-${i}-role"]
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
      docker_install_script_file : base64encode(file("${path.module}/scripts/install_docker.sh")),
      node_name : local.vm_names[count.index],
      username : var.username,
      public_ssh_key : base64encode(file(var.public_key_path)),
      region : var.region,
      zone : var.zone,
      app_name : var.app_tag
    })
  }
}

