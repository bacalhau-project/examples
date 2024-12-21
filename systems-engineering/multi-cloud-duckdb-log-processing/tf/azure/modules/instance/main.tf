# Azure Instance Module

resource "azurerm_public_ip" "pip" {
  name                = "${var.app_name}-pip"
  resource_group_name = var.resource_group_name
  location            = var.location
  allocation_method   = "Static"

  tags = {
    App = var.app_name
  }
}

resource "azurerm_network_interface" "nic" {
  name                = "${var.app_name}-nic"
  location            = var.location
  resource_group_name = var.resource_group_name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = var.subnet_id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.pip.id
  }

  tags = {
    App = var.app_name
  }
}

resource "azurerm_network_interface_security_group_association" "nic_nsg_assoc" {
  network_interface_id      = azurerm_network_interface.nic.id
  network_security_group_id = var.nsg_id
}

data "cloudinit_config" "user_data" {
  gzip          = false
  base64_encode = false

  part {
    filename     = "cloud-config.yaml"
    content_type = "text/cloud-config"

    content = templatefile("${path.module}/../../cloud-init/init-vm.yml", {
      bacalhau_service         = filebase64("${path.module}/../node_files/bacalhau.service")
      start_bacalhau          = filebase64("${path.module}/../node_files/start_bacalhau.sh")
      orchestrator_config     = filebase64(var.orchestrator_config_path)
      bacalhau_installation_id = var.bacalhau_installation_id
      logs_dir               = var.logs_dir
      logs_to_process_dir    = var.logs_to_process_dir
      central_logging_bucket = var.central_logging_bucket
      ssh_key               = compact(split("\n", file(var.public_key)))[0]
      username             = var.username
      region              = var.location
      zone                = var.location
    })
  }
}

resource "azurerm_linux_virtual_machine" "vm" {
  name                = "${var.app_name}-vm"
  resource_group_name = var.resource_group_name
  location            = var.location
  size                = var.vm_size
  admin_username      = var.username
  network_interface_ids = [
    azurerm_network_interface.nic.id,
  ]

  admin_ssh_key {
    username   = var.username
    public_key = file(var.public_key)
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts"
    version   = "latest"
  }

  custom_data = base64encode(data.cloudinit_config.user_data.rendered)

  tags = {
    App = var.app_name
  }
}

resource "azurerm_storage_account" "storage" {
  name                     = lower(replace("${var.app_name}${var.location}sa", "/[^a-z0-9]/", ""))
  resource_group_name      = var.resource_group_name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = "LRS"

  tags = {
    App = var.app_name
  }
}

resource "azurerm_storage_container" "container" {
  name                  = "${var.app_name}-${var.location}-container"
  storage_account_name  = azurerm_storage_account.storage.name
  container_access_type = "private"
}

resource "null_resource" "configure_instance" {
  depends_on = [azurerm_linux_virtual_machine.vm]

  connection {
    host        = azurerm_public_ip.pip.ip_address
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
