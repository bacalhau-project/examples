# Bacalhau Scale Tester

A tool for testing the scalability of Bacalhau nodes on AWS spot instances. This tool can launch, manage, and monitor large numbers of Bacalhau nodes, with built-in health checking and stress testing capabilities.

## Features

- Launch and manage AWS spot instances running Bacalhau nodes
- Monitor instance health and status
- Run automated stress tests with configurable parameters
- Beautiful CLI interface with progress bars and live updates
- Comprehensive logging and debugging options

## Prerequisites

- Python 3.10 or higher
- AWS CLI configured with appropriate credentials
- [uv](https://github.com/astral-sh/uv) for dependency management (recommended)
- [Packer](https://www.packer.io/) for building AMIs

## Project Structure

```
bacalhau-scale-tester/
├── ami/                      # AMI Creation Workflow
│   ├── packer/              # Packer configuration
│   │   ├── main.pkr.hcl
│   │   └── variables.pkr.hcl
│   ├── files/               # Files included in AMI
│   │   ├── bacalhau/
│   │   │   ├── startup.service
│   │   │   └── config.yaml
│   │   └── docker/
│   │       └── compose.yml
│   └── scripts/             # AMI build scripts
│       ├── build.sh
│       └── setup.sh
├── aws/                     # AWS Resource Management
│   ├── config/             # AWS configurations
│   │   ├── env.sh.example
│   │   └── env.sh
│   ├── keys/               # SSH keys (gitignored)
│   │   └── README.md
│   └── scripts/            # AWS setup scripts
│       ├── setup-iam.sh
│       └── upload-ssm.sh
├── fleet/                  # Spot Fleet Management
│   ├── bin/               # Command-line tools
│   │   └── spot-manager
│   ├── src/               # Python implementation
│   │   └── spot_manager.py
│   ├── scripts/           # Fleet management scripts
│   │   └── startup.sh
│   └── examples/          # Example jobs
│       └── pusher/        # Pusher job example
│           ├── job.yaml
│           ├── env.yaml
│           └── README.md
├── pyproject.toml         # Python project config
├── requirements.txt       # Python dependencies
└── README.md             # Main documentation
```

## Workflows

### 1. Creating a New AMI

To create a new AMI for your Bacalhau nodes:

```bash
# 1. Configure AMI settings
vim ami/packer/variables.pkr.hcl

# 2. Build the AMI
cd ami
./scripts/build.sh
cd ..
```

### 2. Setting Up AWS Resources

Before running spot instances, set up required AWS resources:

```bash
# 1. Configure AWS environment
cp aws/config/env.sh.example aws/config/env.sh
vim aws/config/env.sh

# 2. Create SSH key pair
cd aws/keys
aws ec2 create-key-pair --key-name BacalhauScaleTestKey --query 'KeyMaterial' --output text > BacalhauScaleTestKey.pem
chmod 600 BacalhauScaleTestKey.pem
cd ../..

# 3. Set up IAM roles and upload configs
cd aws/scripts
./setup-iam.sh
./upload-ssm.sh
cd ../..
```

### 3. Managing Spot Fleet

The spot manager provides a CLI for managing your fleet:

```bash
# The spot-manager script handles environment setup
./fleet/bin/spot-manager --help

# Launch instances
./fleet/bin/spot-manager launch --count 5

# List running instances
./fleet/bin/spot-manager list

# Run stress test
./fleet/bin/spot-manager stress-test \
    --min-nodes 100 \
    --max-nodes 500 \
    --iterations 5 \
    --health-timeout 300

# Terminate all instances
./fleet/bin/spot-manager terminate-all
```

### Stress Test Options

- `--min-nodes`: Minimum number of nodes per iteration (default: 250)
- `--max-nodes`: Maximum number of nodes per iteration (default: 750)
- `--iterations`: Number of test iterations (default: 10)
- `--health-timeout`: Timeout in seconds for health checks (default: 300)

### Debug Mode

Add `--debug` to any command to enable detailed logging:
```bash
./fleet/bin/spot-manager --debug launch --count 5
```

## Development Setup

1. Clone the repository:
```bash
git clone https://github.com/bacalhau-project/bacalhau-scale-tester.git
cd bacalhau-scale-tester
```

2. Set up the environment:
```bash
# Using uv (recommended)
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt

# Or using pip
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Example Jobs

See the `fleet/examples/` directory for example job configurations:

### Pusher Job
Located in `fleet/examples/pusher/`, this example demonstrates how to set up a job that pushes events to a monitoring system. See its README for detailed setup instructions.

## Development

The project uses:
- [Rich](https://rich.readthedocs.io/) for beautiful terminal output
- [Click](https://click.palletsprojects.com/) for CLI interface
- [Boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html) for AWS interaction
- [aiohttp](https://docs.aiohttp.org/) for async health checks
- [Packer](https://www.packer.io/) for AMI building

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the Apache License 2.0 - see the LICENSE file for details.