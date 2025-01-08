#!/usr/bin/env bash

platforms="linux/amd64,linux/arm64"

# Parse command line arguments
force_rebuild=false
while [[ $# -gt 0 ]]; do
  case $1 in
    --force)
      force_rebuild=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Get latest DuckDB version using GitHub API and jq
duckdb_version=$(curl -s https://api.github.com/repos/duckdb/duckdb/releases/latest | jq -r .tag_name)
echo "Latest DuckDB version: ${duckdb_version}"

versioned_image=docker.io/bacalhauproject/duckdb:"${duckdb_version}"
latest_image=docker.io/bacalhauproject/duckdb:latest

if [ "$force_rebuild" = true ] || [ -z "$(DOCKER_CLI_EXPERIMENTAL=enabled docker manifest inspect "$versioned_image" 2> /dev/null)" ]; then
  if [ "$force_rebuild" = true ]; then
    echo "Force rebuild requested for duckdb version: ${duckdb_version}"
  else
    echo "Building for duckdb version: ${duckdb_version}"
  fi

  docker run --privileged --rm tonistiigi/binfmt --install all
  docker buildx create --use --name builder
  docker buildx inspect --bootstrap builder

  docker buildx build \
    --platform "$platforms" \
    --build-arg "DUCKDB_VERSION=${duckdb_version}" \
    -t "$versioned_image" \
    -t "$latest_image" \
    --push .

  echo "Done!"
else
  echo "Latest duckdb image version already exists, version: ${duckdb_version}"
fi