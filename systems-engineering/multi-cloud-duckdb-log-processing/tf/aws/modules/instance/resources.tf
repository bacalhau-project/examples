data "cloudinit_config" "user_data" {
  gzip          = false
  base64_encode = false

  part {
    filename     = "cloud-config.yaml"
    content_type = "text/cloud-config"

    content = templatefile("${path.module}/../../cloud-init/init-vm.yml", {
      bacalhau_service : base64encode(file("${path.module}/../../../node_files/bacalhau.service")),
      ipfs_service : base64encode(file("${path.module}/../../../node_files/ipfs.service")),
      start_bacalhau : base64encode(file("${path.module}/../../../node_files/start-bacalhau.sh")),
      logs_dir : "/var/log/${var.app_tag}_logs",
      log_generator_py : filebase64("${path.module}/../../../node_files/log_generator.py"),
      node_name : "${var.app_tag}-${var.region}-vm"
      ssh_key : compact(split("\n", file(var.public_key)))[0]
      region : var.region
      zone : var.zone
      app_name : var.app_tag
    })
  }

resource "aws_iam_role" "vm_iam_role" {
  name               = "${var.app_tag}-${var.region}_vm_iam_role"
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
  name = "${var.app_tag}-${var.region}-vm_instance_profile"
  role = aws_iam_role.vm_iam_role.name
}

resource "aws_iam_role_policy" "vm_iam_role_policy" {
  name   = "${var.app_tag}-${var.region}-vm_iam_role_policy"
  role   = aws_iam_role.vm_iam_role.id
  policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": ["arn:aws:s3:::bucket-name"]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject"
      ],
      "Resource": ["arn:aws:s3:::bucket-name/*"]
    }
  ]
}
EOF
}

resource "aws_s3_bucket" "images_bucket" {
  bucket = "${var.app_tag}-${var.region}-images-bucket"
  # Force delete even if not empty
  force_destroy = true
  tags = {
    Name = var.app_tag
  }
}


resource "aws_iam_policy" "bucket_policy" {
  name        = "${var.app_tag}-${var.region}-images-bucket-policy"
  path        = "/"
  description = "Allow "
  policy = jsonencode({
    "Version" : "2012-10-17",
    "Statement" : [
      {
        "Sid" : "VisualEditor0",
        "Effect" : "Allow",
        "Action" : [
          "s3:PutObject",
          "s3:GetObject",
          "s3:ListBucket",
          "s3:DeleteObject"
        ],
        "Resource" : [
          "arn:aws:s3:::*/*",
          "arn:aws:s3:::${var.app_tag}-${var.region}-images-bucket"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "images_bucket_policy" {
  role       = aws_iam_role.vm_iam_role.name
  policy_arn = aws_iam_policy.bucket_policy.arn
}

resource "aws_instance" "instance" {
  ami                    = var.aws_ami
  instance_type          = var.aws_instance_type
  subnet_id              = var.subnet_public_id
  vpc_security_group_ids = var.security_group_ids
  availability_zone      = var.zone
  user_data              = data.cloudinit_config.user_data.rendered
  iam_instance_profile   = aws_iam_instance_profile.vm_instance_profile.name

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

resource "null_resource" "configure_instance" {
  depends_on = [aws_instance.instance]

  connection {
    host = aws_eip.instanceeip.public_ip
    port = 22
    user = var.username
  }

  provisioner "file" {
    source      = var.orchestrator_config_path
    destination = "/home/${var.username}/orchestrator-config.yaml"
  }

  provisioner "remote-exec" {
    inline = [
      "sudo mv /home/${var.username}/orchestrator-config.yaml /etc/bacalhau/orchestrator-config.yaml",
      "sudo systemctl daemon-reload",
      "sudo systemctl restart bacalhau.service"
    ]
  }
}
