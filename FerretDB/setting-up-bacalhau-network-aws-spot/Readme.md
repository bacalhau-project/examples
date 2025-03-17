## setting-up-bacalhau-network-aws-spot

### Changes made for FerretDB demo
 - allow to deploy arm64 or x86_64 nodes
 - util/get_ubuntu_amis.py now fetches AMI IDs for arm64 and x86_64 architectures
 - use of uv instead of plain old python pip module (faster and allows to run scripts as an 'executable')
 - dynamically sized rich console
 - different set of cloud-init scripts (for Bacalhau compute nodes and FerretDB node)
 - changed logging - log file is created instead loggin to console
 - custom tags for nodes (to distinguish i.e. between node types - visible when listing nodes)
 - creation of subnet limited by async semaphore (more thread-safe)
 - security group has 27017 port open



### Running script
> **Copy config_ferret.yaml to config.yaml and enter Bacalhau token and orchestrator URL.**

#### Install uv (https://docs.astral.sh/uv/getting-started/installation/)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### Make scripts executable
```bash
chmod +x util/get_ubuntu_amis.py
chmod +x deploy_spot.py
```

#### deploy infrastructure (assuming AWS credentials are defined in your system)
```bash
./deploy_spot.py --action create
```

#### list nodes
```
./deploy_spot.py --action list
```

#### destroy infrastructure
```bash
./deploy_spot.py --action destroy
```