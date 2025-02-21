# Presidio Container

This container provides a ready-to-use environment for data anonymization using Microsoft's Presidio framework. It includes both the Analyzer and Anonymizer components along with the English language model for NLP processing.

## Components

The container includes:
- Presidio Analyzer (version 2.2.357)
- Presidio Anonymizer (version 2.2.357)
- SpaCy English Core Model (large)
- Python 3.12 base environment

## Dockerfile Details

The Dockerfile:
- Uses Python 3.12 as the base image
- Installs necessary SSL certificates for secure connections
- Installs Presidio Analyzer and Anonymizer packages
- Downloads and installs the SpaCy English language model
- Sets up proper container metadata following OCI standards
- Configures the working directory as `/app`

## Makefile Commands

The makefile provides several useful commands:

`build`: Build the Docker image for your local architecture
- Creates local image tagged with current version and latest
- Uses docker buildx for the build process

`push`: Push the Docker image to the registry
- Builds for both AMD64 and ARM64 architectures
- Pushes to GitHub Container Registry
- Tags with both version number and latest

`test`: Run the test suite
- Verifies Presidio installation
- Tests basic anonymization functionality

`login`: Login to GitHub Container Registry
- Requires `GITHUB_PAT` and `GITHUB_USERNAME` environment variables
- Sets up authentication for pushing images

`version`: Display the current version
- Shows the version based on year.month format

`tag`: Create a new release tag
- Creates and pushes a git tag for the current version

`size`: Show image size details
- Displays detailed breakdown of image layers

`clean`: Clean up test artifacts
- Removes temporary test files and directories

## Usage Example

To build and push a new version:

1. Login to the container registry:
   ```
   make login
   ```

2. Build the image:
   ```
   make build
   ```

3. Run tests:
   ```
   make test
   ```

4. Push to registry:
   ```
   make push
   ```

## Version Scheme

The version number follows the format `YY.MM` (year.month), automatically generated during build time.

## Container Registry

Images are stored in the GitHub Container Registry under:
`ghcr.io/bacalhau-project/presidio`
