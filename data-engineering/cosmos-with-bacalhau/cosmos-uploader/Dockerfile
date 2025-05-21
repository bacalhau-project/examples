# syntax=docker/dockerfile:1.4
FROM mcr.microsoft.com/dotnet/sdk:9.0 AS build

# Set working directory 
WORKDIR /cosmos-uploader

# Copy sln, csproj and restore dependencies using the solution file
COPY cosmos-uploader.sln .
COPY *.csproj .
RUN dotnet restore cosmos-uploader.sln

# Copy all source files and build using the project file
COPY . .
RUN dotnet publish CosmosUploader.csproj -c Release -o /app

# Build runtime image
FROM mcr.microsoft.com/dotnet/runtime:9.0 AS final
WORKDIR /app
COPY --from=build /app .

# Explicitly copy the entrypoint script into the final image
COPY entrypoint.sh /app/entrypoint.sh
# Ensure it has execute permissions within the image
RUN chmod +x /app/entrypoint.sh

# Install iproute2 for the 'ip' command
# Using apt-get for the Debian-based runtime image
RUN apt-get update && apt-get install -y --no-install-recommends iproute2 && \
    rm -rf /var/lib/apt/lists/*

# Set entrypoint to use our wrapper script
ENTRYPOINT ["/app/entrypoint.sh"]
