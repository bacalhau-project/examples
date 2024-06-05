param uniqueId string
param location1 string = 'westus'
param location2 string = 'centralus'
param location3 string = 'eastus2'

resource vnet 'Microsoft.Network/virtualNetworks@2021-02-01' = {
  name: 'vnet-${uniqueId}'
  location: location1
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
}

resource nic1 'Microsoft.Network/networkInterfaces@2021-02-01' = {
  name: 'supportNode1Nic-${uniqueId}'
  location: location1
  properties: {
    ipConfigurations: [
      {
        name: 'ipconfig1'
        properties: {
          subnet: {
            id: vnet.properties.subnets[0].id
          }
          privateIPAllocationMethod: 'Dynamic'
        }
      }
    ]
  }
}

resource supportNode1 'Microsoft.Compute/virtualMachines@2021-07-01' = {
  name: 'supportNode1-${uniqueId}'
  location: location1
  properties: {
    hardwareProfile: {
      vmSize: 'Standard_DS1_v2'
    }
    osProfile: {
      computerName: 'supportNode1'
      adminUsername: 'azureuser'
      adminPassword: 'Password1234!'
    }
    storageProfile: {
      imageReference: {
        publisher: 'Canonical'
        offer: 'UbuntuServer'
        sku: '18.04-LTS'
        version: 'latest'
      }
      osDisk: {
        createOption: 'FromImage'
      }
    }
    networkProfile: {
      networkInterfaces: [
        {
          id: nic1.id
        }
      ]
    }
  }
  tags: {
    uniqueId: uniqueId
  }
}

resource nic2 'Microsoft.Network/networkInterfaces@2021-02-01' = {
  name: 'supportNode2Nic-${uniqueId}'
  location: location2
  properties: {
    ipConfigurations: [
      {
        name: 'ipconfig1'
        properties: {
          subnet: {
            id: vnet.properties.subnets[0].id
          }
          privateIPAllocationMethod: 'Dynamic'
        }
      }
    ]
  }
}

resource supportNode2 'Microsoft.Compute/virtualMachines@2021-07-01' = {
  name: 'supportNode2-${uniqueId}'
  location: location2
  properties: {
    hardwareProfile: {
      vmSize: 'Standard_DS1_v2'
    }
    osProfile: {
      computerName: 'supportNode2'
      adminUsername: 'azureuser'
      adminPassword: 'Password1234!'
    }
    storageProfile: {
      imageReference: {
        publisher: 'Canonical'
        offer: 'UbuntuServer'
        sku: '18.04-LTS'
        version: 'latest'
      }
      osDisk: {
        createOption: 'FromImage'
      }
    }
    networkProfile: {
      networkInterfaces: [
        {
          id: nic2.id
        }
      ]
    }
  }
  tags: {
    uniqueId: uniqueId
  }
}

resource nic3 'Microsoft.Network/networkInterfaces@2021-02-01' = {
  name: 'supportNode3Nic-${uniqueId}'
  location: location3
  properties: {
    ipConfigurations: [
      {
        name: 'ipconfig1'
        properties: {
          subnet: {
            id: vnet.properties.subnets[0].id
          }
          privateIPAllocationMethod: 'Dynamic'
        }
      }
    ]
  }
}

resource supportNode3 'Microsoft.Compute/virtualMachines@2021-07-01' = {
  name: 'supportNode3-${uniqueId}'
  location: location3
  properties: {
    hardwareProfile: {
      vmSize: 'Standard_DS1_v2'
    }
    osProfile: {
      computerName: 'supportNode3'
      adminUsername: 'azureuser'
      adminPassword: 'Password1234!'
    }
    storageProfile: {
      imageReference: {
        publisher: 'Canonical'
        offer: 'UbuntuServer'
        sku: '18.04-LTS'
        version: 'latest'
      }
      osDisk: {
        createOption: 'FromImage'
      }
    }
    networkProfile: {
      networkInterfaces: [
        {
          id: nic3.id
        }
      ]
    }
  }
  tags: {
    uniqueId: uniqueId
  }
}
