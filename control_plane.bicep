resource controlPlane 'Microsoft.Compute/virtualMachines@2021-07-01' = {
  name: 'controlPlaneVM'
  location: resourceGroup().location
  properties: {
    hardwareProfile: {
      vmSize: 'Standard_DS1_v2'
    }
    osProfile: {
      computerName: 'controlPlaneVM'
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
          id: resourceId('Microsoft.Network/networkInterfaces', 'controlPlaneVMNic')
        }
      ]
    }
  }
}
