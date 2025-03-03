# Word Count Container

A lightweight container that counts words in files or directories. This container is designed to work seamlessly with [Bacalhau](https://www.bacalhau.org/) for distributed text processing tasks.

## Features

- Count words in files or directories
- Sort results by word frequency (descending order)
- Limit the number of results displayed
- Output in plain text or JSON format
- Write results to stdout or to a file

## Usage

### Basic Usage

```bash
docker run word-count [OPTIONS] PATH
```

### Options

- `--limit N`: Limit output to top N words (default: no limit)
- `--format FORMAT`: Output format, either "text", "json", or "csv" (default: text)
- `--output-file FILE`: Write output to FILE instead of stdout

### Examples

Count all words in Moby Dick:

```bash
docker run -v $(pwd):/data word-count /data/moby-dick.txt
```

Count top 10 words in a directory containing classic novels:

```bash
docker run -v $(pwd):/data word-count --limit 10 /data/classics/
```

Output Moby Dick word counts in JSON format:

```bash
docker run -v $(pwd):/data word-count --format json /data/moby-dick.txt
```

Write Moby Dick word count results to a file:

```bash
docker run -v $(pwd):/data word-count --output-file /data/moby-dick-counts.txt /data/moby-dick.txt
```

## Using with Bacalhau

This container is designed to work with Bacalhau for distributed text processing. Here are some examples:

### Process Moby Dick from Project Gutenberg

```bash
bacalhau docker run \
  --input https://www.gutenberg.org/files/2701/2701-0.txt:/data/moby-dick.txt \
  ghcr.io/bacalhau-project/word-count:latest /data/moby-dick.txt
```

### Process Moby Dick and save results to a specific output

```bash
bacalhau docker run \
  --input https://www.gutenberg.org/files/2701/2701-0.txt:/data/moby-dick.txt \
  --output outputs:/outputs \
  ghcr.io/bacalhau-project/word-count:latest -- --output-file /outputs/moby-dick-counts.txt /data/moby-dick.txt
```

### Get JSON output of Moby Dick word counts for further processing

```bash
bacalhau docker run \
  --input https://www.gutenberg.org/files/2701/2701-0.txt:/data/moby-dick.txt \
  ghcr.io/bacalhau-project/word-count:latest --format json /data/moby-dick.txt
```

### Limit results to top 20 words in Moby Dick

```bash
bacalhau docker run \
  --input https://www.gutenberg.org/files/2701/2701-0.txt:/data/moby-dick.txt \
  ghcr.io/bacalhau-project/word-count:latest --limit 20 /data/moby-dick.txt
```

### Process multiple books for comparison

```bash
bacalhau docker run \
  --input https://www.gutenberg.org/files/2701/2701-0.txt:/data/moby-dick.txt \
  --input https://www.gutenberg.org/files/1342/1342-0.txt:/data/pride-and-prejudice.txt \
  --output outputs:/outputs \
  ghcr.io/bacalhau-project/word-count:latest --format json --output-file /outputs/combined-analysis.json /data
```

## Development

### Using the Makefile

The container comes with a Makefile to simplify common operations:

```bash
# Build the container locally
make build

# Run tests to verify functionality
make test

# Login to GitHub Container Registry (requires GITHUB_PAT and GITHUB_USERNAME env vars)
make login

# Push to GitHub Container Registry
make push

# Build, test, login, and push in one command
make all

# Clean up test data
make clean

# Display help information
make help

# Show current version
make version
```

### Configuration

The Makefile uses the following variables that can be overridden:

```bash
# Set custom registry
make push REGISTRY=myregistry.com

# Set custom owner
make push OWNER=myorg

# Set custom image name
make push IMG_NAME=my-word-counter

# Set custom version
make push VERSION=1.0.0
```

### Manual Building

If you prefer not to use the Makefile, you can build manually:

```bash
docker build -t word-count .
```

### Testing

The container includes comprehensive tests to verify functionality:

```bash
make test
```
