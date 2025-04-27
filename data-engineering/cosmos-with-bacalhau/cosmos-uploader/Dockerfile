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

# Create a wrapper script that will handle dotnet execution with args
RUN echo '#!/bin/bash' > /app/entrypoint.sh && \
    echo 'echo "Starting CosmosUploader with arguments: $@"' >> /app/entrypoint.sh && \
    echo 'exec dotnet CosmosUploader.dll "$@"' >> /app/entrypoint.sh && \
    chmod +x /app/entrypoint.sh

# Set entrypoint to use our wrapper script
ENTRYPOINT ["/app/entrypoint.sh"]
