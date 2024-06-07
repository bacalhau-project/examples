param uniqueId string
param location string
param adminUsername string
param sshKey string

resource vnet 'Microsoft.Network/virtualNetworks@2021-02-01' = {
  name: 'bac-queue-vnet-${location}-${uniqueId}'
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: ['10.1.0.0/16']
    }
    subnets: [
      {
        name: 'subnet'
        properties: {
          addressPrefix: '10.1.0.0/24'
        }
      }
    ]
  }
  tags: {
    uniqueId: uniqueId
  }
}

resource nsg 'Microsoft.Network/networkSecurityGroups@2020-11-01' = {
  name: 'bac-queue-nsg-${location}-${uniqueId}'
  location: location
  properties: {
    securityRules: [
      {
        name: 'Allow-SSH'
        properties: {
          priority: 1000
          protocol: 'Tcp'
          access: 'Allow'
          direction: 'Inbound'
          sourcePortRange: '*'
          destinationPortRange: '22'
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
        }
      }
      {
        name: 'Allow-Port-1234'
        properties: {
          priority: 1010
          protocol: 'Tcp'
          access: 'Allow'
          direction: 'Inbound'
          sourcePortRange: '*'
          destinationPortRange: '1234'
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
        }
      }
      {
        name: 'Allow-Port-4222'
        properties: {
          priority: 1020
          protocol: 'Tcp'
          access: 'Allow'
          direction: 'Inbound'
          sourcePortRange: '*'
          destinationPortRange: '4222'
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
        }
      }
    ]
  }
  tags: {
    uniqueId: uniqueId
  }
}

resource publicIP 'Microsoft.Network/publicIPAddresses@2020-11-01' = {
  name: 'bac-queue-pip-${location}-${uniqueId}'
  location: location
  properties: {
    publicIPAllocationMethod: 'Dynamic'
  }
  tags: {
    uniqueId: uniqueId
  }
}

resource nic 'Microsoft.Network/networkInterfaces@2021-02-01' = {
  name: 'bac-queue-nic-${location}-${uniqueId}'
  location: location
  properties: {
    ipConfigurations: [
      {
        name: 'ipconfig1'
        properties: {
          subnet: {
            id: vnet.properties.subnets[0].id
          }
          privateIPAllocationMethod: 'Dynamic'
          publicIPAddress: {
            id: publicIP.id
          }
        }
      }
    ]
    networkSecurityGroup: {
      id: nsg.id
    }
  }
  tags: {
    uniqueId: uniqueId
  }
}

resource supportNode 'Microsoft.Compute/virtualMachines@2021-07-01' = {
  name: 'bac-queue-vm-${location}-${uniqueId}'
  location: location
  properties: {
    hardwareProfile: {
      vmSize: 'Standard_DS1_v2'
    }
    osProfile: {
      computerName: 'supportNode'
      adminUsername: adminUsername
      customData: base64('echo "${adminUsername} ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/${adminUsername}')
      linuxConfiguration: {
          disablePasswordAuthentication: true
          ssh: {
              publicKeys: [
                  {
                      path: '/home/${adminUsername}/.ssh/authorized_keys'
                      keyData: sshKey
                  }
              ]
          }
      }
    }
    storageProfile: {
      imageReference: {
        publisher: 'Canonical'
        offer: '0001-com-ubuntu-server-jammy'
        sku: '22_04-lts-gen2'
        version: 'latest'
      }
      osDisk: {
        createOption: 'FromImage'
      }
    }
    networkProfile: {
      networkInterfaces: [
        {
          id: nic.id
        }
      ]
    }
  }
  tags: {
    uniqueId: uniqueId
  }
}
