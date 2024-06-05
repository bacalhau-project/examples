resource supportNode1 'Microsoft.Compute/virtualMachines@2021-07-01' = {
  name: 'supportNode1'
  location: resourceGroup().location
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
          id: resourceId('Microsoft.Network/networkInterfaces', 'supportNode1Nic')
        }
      ]
    }
  }
}

resource supportNode2 'Microsoft.Compute/virtualMachines@2021-07-01' = {
  name: 'supportNode2'
  location: resourceGroup().location
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
          id: resourceId('Microsoft.Network/networkInterfaces', 'supportNode2Nic')
        }
      ]
    }
  }
}

resource supportNode3 'Microsoft.Compute/virtualMachines@2021-07-01' = {
  name: 'supportNode3'
  location: resourceGroup().location
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
          id: resourceId('Microsoft.Network/networkInterfaces', 'supportNode3Nic')
        }
      ]
    }
  }
}
