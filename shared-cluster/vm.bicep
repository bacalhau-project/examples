param uniqueId string
param location string
param adminUsername string
param sshKey string
param vmSize string
param vmName string
param vnetName string
param nsgName string
param pipName string
param nicName string

resource vnet 'Microsoft.Network/virtualNetworks@2021-02-01' = {
  name: '${vnetName}-${location}-${uniqueId}'
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: ['10.0.0.0/16']
    }
    subnets: [
      {
        name: 'subnet'
        properties: {
          addressPrefix: '10.0.0.0/24'
        }
      }
    ]
  }
  tags: {
    uniqueId: uniqueId
  }
}

resource nsg 'Microsoft.Network/networkSecurityGroups@2020-11-01' = {
  name: '${nsgName}-${location}-${uniqueId}'
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
        name: 'Allow-1234'
        properties: {
          priority: 1001
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
        name: 'Allow-1235'
        properties: {
          priority: 1002
          protocol: 'Tcp'
          access: 'Allow'
          direction: 'Inbound'
          sourcePortRange: '*'
          destinationPortRange: '1235'
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
  name: '${pipName}-${location}-${uniqueId}'
  location: location
  properties: {
    publicIPAllocationMethod: 'Dynamic'
  }
  tags: {
    uniqueId: uniqueId
  }
}

resource nic 'Microsoft.Network/networkInterfaces@2021-02-01' = {
  name: '${nicName}-${location}-${uniqueId}'
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

resource vm 'Microsoft.Compute/virtualMachines@2021-07-01' = {
  name: '${vmName}-${location}-${uniqueId}'
  location: location
  properties: {
    hardwareProfile: {
      vmSize: vmSize
    }
    osProfile: {
      computerName: vmName
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