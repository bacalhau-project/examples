using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Threading;
using System.Threading.Tasks;
using CosmosUploader.Configuration;
using CosmosUploader.Models;
using Microsoft.Azure.Cosmos;
using Microsoft.Extensions.Logging;
using Newtonsoft.Json;

namespace CosmosUploader.Services
{
    public class CosmosUploader : ICosmosUploader
    {
        private readonly ILogger<CosmosUploader> _logger;
        private readonly AppSettings _settings;
        private CosmosClient? _cosmosClient;
        private Container? _container;
        private long _totalRequestUnits = 0;

        public CosmosUploader(AppSettings settings, ILogger<CosmosUploader> logger)
        {
            _settings = settings;
            _logger = logger;
        }

        public async Task InitializeAsync()
        {
            try
            {
                _logger.LogInformation("Initializing Cosmos DB connection to {Endpoint}", _settings.Cosmos.Endpoint);
                
                // Configure connection options
                var clientOptions = new CosmosClientOptions
                {
                    ConnectionMode = ConnectionMode.Gateway,
                    MaxRetryAttemptsOnRateLimitedRequests = 9,
                    MaxRetryWaitTimeOnRateLimitedRequests = TimeSpan.FromSeconds(30)
                };
                
                // Create the client
                _cosmosClient = new CosmosClient(
                    _settings.Cosmos.Endpoint,
                    _settings.Cosmos.Key,
                    clientOptions);
                
                // Ensure database exists
                _logger.LogInformation("Ensuring database {Database} exists", _settings.Cosmos.DatabaseName);
                Database database = await _cosmosClient.CreateDatabaseIfNotExistsAsync(
                    _settings.Cosmos.DatabaseName,
                    throughput: _settings.Performance.Throughput);
                
                // Ensure container exists
                _logger.LogInformation("Ensuring container {Container} exists", _settings.Cosmos.ContainerName);
                _container = await database.CreateContainerIfNotExistsAsync(
                    _settings.Cosmos.ContainerName,
                    _settings.Cosmos.PartitionKey);
                
                _logger.LogInformation("Cosmos DB initialization completed successfully");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error initializing Cosmos DB connection");
                throw;
            }
        }

        public async Task UploadReadingsAsync(List<SensorReading> readings, CancellationToken cancellationToken)
        {
            if (readings == null || readings.Count == 0)
            {
                _logger.LogWarning("No readings to upload");
                return;
            }

            _logger.LogInformation("Uploading {Count} readings to Cosmos DB", readings.Count);
            var stopwatch = Stopwatch.StartNew();
            
            try
            {
                // Process readings in batches
                int totalUploaded = 0;
                int batchSize = _settings.Performance.BatchSize;
                int batches = (readings.Count + batchSize - 1) / batchSize; // Ceiling division
                
                for (int i = 0; i < batches; i++)
                {
                    if (cancellationToken.IsCancellationRequested)
                    {
                        _logger.LogWarning("Upload cancelled by user");
                        break;
                    }
                    
                    int skip = i * batchSize;
                    int take = Math.Min(batchSize, readings.Count - skip);
                    var batch = readings.GetRange(skip, take);
                    
                    _logger.LogDebug("Processing batch {Current}/{Total} with {Size} items", 
                        i + 1, batches, batch.Count);
                    
                    // Process batch in parallel for better performance
                    var tasks = new List<Task<(double, bool)>>();
                    foreach (var reading in batch)
                    {
                        tasks.Add(UploadReadingAsync(reading, cancellationToken));
                    }
                    
                    // Wait for all upload tasks to complete
                    var results = await Task.WhenAll(tasks);
                    
                    // Calculate statistics
                    double batchRequestUnits = 0;
                    int successCount = 0;
                    
                    foreach (var (ru, success) in results)
                    {
                        batchRequestUnits += ru;
                        if (success) successCount++;
                    }
                    
                    _totalRequestUnits += (long)batchRequestUnits;
                    totalUploaded += successCount;
                    
                    _logger.LogInformation(
                        "Batch {Current}/{Total} completed: {Success}/{Total} items, {RU} RUs consumed", 
                        i + 1, batches, successCount, batch.Count, batchRequestUnits);
                }
                
                stopwatch.Stop();
                
                if (_settings.Logging.LogLatency)
                {
                    _logger.LogInformation(
                        "Upload completed in {ElapsedMs} ms. Total RUs: {RUs}, Avg RU/item: {AvgRU}, Items/sec: {ItemsPerSec}", 
                        stopwatch.ElapsedMilliseconds,
                        _totalRequestUnits,
                        _totalRequestUnits / Math.Max(1, totalUploaded),
                        totalUploaded * 1000.0 / Math.Max(1, stopwatch.ElapsedMilliseconds));
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error uploading sensor readings to Cosmos DB");
                throw;
            }
        }

        private async Task<(double RequestUnits, bool Success)> UploadReadingAsync(SensorReading reading, CancellationToken cancellationToken)
        {
            try
            {
                if (_container == null)
                {
                    throw new InvalidOperationException("Cosmos DB container has not been initialized. Call InitializeAsync first.");
                }

                // Create a unique ID for the document
                if (string.IsNullOrEmpty(reading.Id))
                {
                    reading.Id = Guid.NewGuid().ToString();
                }
                
                // Add partition key if missing
                if (string.IsNullOrEmpty(reading.City))
                {
                    reading.City = reading.Location;
                }
                
                // Perform upsert operation to ensure idempotency
                var response = await _container.UpsertItemAsync(
                    reading,
                    new PartitionKey(reading.City),
                    cancellationToken: cancellationToken);
                
                if (_settings.Logging.LogRequestUnits)
                {
                    _logger.LogDebug("Uploaded reading {Id} for sensor {SensorId}: {RU} RUs", 
                        reading.Id, reading.SensorId, response.RequestCharge);
                }
                
                return (response.RequestCharge, true);
            }
            catch (CosmosException ex) when (ex.StatusCode == System.Net.HttpStatusCode.TooManyRequests)
            {
                _logger.LogWarning("Rate limited when uploading reading for sensor {SensorId}. Retrying...", 
                    reading.SensorId);
                // Retry handled by the SDK automatically
                return (0, false);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error uploading reading for sensor {SensorId}", reading.SensorId);
                return (0, false);
            }
        }

        public async Task<int> GetContainerItemCountAsync()
        {
            try
            {
                if (_container == null)
                {
                    throw new InvalidOperationException("Cosmos DB container has not been initialized. Call InitializeAsync first.");
                }

                var queryDefinition = new QueryDefinition("SELECT VALUE COUNT(1) FROM c");
                var query = _container.GetItemQueryIterator<int>(queryDefinition);
                
                if (query.HasMoreResults)
                {
                    var response = await query.ReadNextAsync();
                    return response.Resource.FirstOrDefault();
                }
                
                return 0;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error getting container item count");
                return -1;
            }
        }

        public Task<long> GetTotalRequestUnitsAsync()
        {
            return Task.FromResult(_totalRequestUnits);
        }
    }
}