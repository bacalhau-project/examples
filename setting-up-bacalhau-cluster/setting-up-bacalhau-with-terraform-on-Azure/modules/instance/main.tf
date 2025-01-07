# Azure Instance Module

resource "random_string" "prefix" {
  count   = var.node_count
  length  = 8
  special = false
  upper   = false
}

resource "azurerm_public_ip" "pip" {
  count               = var.node_count
  name                = "${random_string.prefix[count.index].result}-pip"
  resource_group_name = var.resource_group_name
  location            = var.location
  allocation_method   = "Static"

  tags = {
    App = var.app_tag
  }
}

resource "azurerm_network_interface" "nic" {
  count               = var.node_count
  name                = "${random_string.prefix[count.index].result}-nic"
  location            = var.location
  resource_group_name = var.resource_group_name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = var.subnet_id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.pip[count.index].id
  }

  tags = {
    App = var.app_tag
  }
}

resource "azurerm_network_interface_security_group_association" "nic_nsg_assoc" {
  count                     = var.node_count
  network_interface_id      = azurerm_network_interface.nic[count.index].id
  network_security_group_id = var.nsg_id
}

data "cloudinit_config" "user_data" {
  count         = var.node_count
  gzip          = false
  base64_encode = false

  part {
    filename     = "cloud-config.yaml"
    content_type = "text/cloud-config"

    content = templatefile("${path.module}/cloud-init/init-vm.yml", {
      username : var.username,
      region : var.location,
      zone : var.location,
      bacalhau_startup_service_file : filebase64("${path.module}/scripts/bacalhau-startup.service"),
      bacalhau_startup_script_file : filebase64("${path.module}/scripts/startup.sh"),
      bacalhau_config_file : var.bacalhau_config_file,
      docker_compose_file : filebase64("${path.module}/config/docker-compose.yml"),
      docker_install_script_file : filebase64("${path.module}/scripts/install_docker.sh"),
      bacalhau_data_dir : "/bacalhau_data",
      bacalhau_node_dir : "/bacalhau_node",
      public_ssh_key : compact(split("\n", file(var.public_ssh_key_path)))[0],
      healthz_web_server_script_file : filebase64("${path.module}/scripts/healthz-web-server.py"),
      healthz_service_file : filebase64("${path.module}/scripts/healthz-web.service"),

    })
  }
}

resource "azurerm_linux_virtual_machine" "vm" {
  count               = var.node_count
  name                = "${random_string.prefix[count.index].result}-vm"
  resource_group_name = var.resource_group_name
  location            = var.location
  size                = var.vm_size
  admin_username      = var.username
  network_interface_ids = [
    azurerm_network_interface.nic[count.index].id,
  ]

  admin_ssh_key {
    username   = var.username
    public_key = file(var.public_ssh_key_path)
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

  custom_data = base64encode(data.cloudinit_config.user_data[count.index].rendered)

  tags = {
    App = var.app_tag
  }
}


data "http" "healthcheck" {
  count = var.node_count

  url = "http://${azurerm_linux_virtual_machine.vm[count.index].public_ip_address}/healthz"

  retry {
    attempts     = 35
    min_delay_ms = 10000 # 10 seconds
    max_delay_ms = 10000 # 10 seconds
  }

  depends_on = [azurerm_linux_virtual_machine.vm]
}
