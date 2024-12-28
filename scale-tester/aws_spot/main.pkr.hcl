packer {
  required_plugins {
    amazon = {
      version = ">= 1.2.1"
      source  = "github.com/hashicorp/amazon"
    }
  }
}

source "amazon-ebs" "bacalhau" {
  region          = var.aws_region
  ami_name        = "${var.ami_name}-{{timestamp}}"
  ami_description = var.ami_description
  instance_type   = "t3.micro"
  
  source_ami_filter {
    filters = {
      name                = "al2023-ami-*-x86_64"
      root-device-type    = "ebs"
      virtualization-type = "hvm"
    }
    most_recent = true
    owners      = ["amazon"]
  }
  
  ssh_username    = "ec2-user"
  
  force_deregister      = true
  force_delete_snapshot = true

  tags = {
    Name = "bacalhau-scale-test"
    Builder = "Packer"
    BuildTime = "{{timestamp}}"
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }
}

build {
  sources = ["source.amazon-ebs.bacalhau"]

  # Copy environment variables file
  provisioner "file" {
    source      = "aws-spot-env.sh"
    destination = "/tmp/aws-spot-env.sh"
  }

  # Copy startup script and service file
  provisioner "file" {
    source      = "scripts/startup.sh"
    destination = "/tmp/startup.sh"
  }

  provisioner "file" {
    source      = "files/bacalhau-startup.service"
    destination = "/tmp/bacalhau-startup.service"
  }

  # Run main setup script
  provisioner "shell" {
    script = "setup.sh"
  }

  # Move files to their final locations and set permissions
  provisioner "shell" {
    inline = [
      "sudo mkdir -p /bacalhau_node",
      "sudo mkdir -p /bacalhau_data",
      "sudo mv /tmp/aws-spot-env.sh /bacalhau_node/",
      "sudo mv /tmp/startup.sh /bacalhau_node/",
      "sudo mv /tmp/bacalhau-startup.service /etc/systemd/system/",
      "sudo chmod +x /bacalhau_node/startup.sh",
      "sudo systemctl enable bacalhau-startup.service"
    ]
  }

  # Verify installation
  provisioner "shell" {
    inline = [
      "docker --version",
      "docker-compose --version",
      "sudo systemctl status docker",
      "systemctl list-unit-files | grep bacalhau"
    ]
  }

  # Generate manifest
  post-processor "manifest" {
    output = "manifest.json"
    strip_path = true
  }
}