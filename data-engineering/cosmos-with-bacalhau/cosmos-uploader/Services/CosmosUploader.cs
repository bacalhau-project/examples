using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using CosmosUploader.Configuration;
using CosmosUploader.Models;
using Microsoft.Azure.Cosmos;
using Microsoft.Extensions.Logging;
using System.Net.NetworkInformation;
using System.Net;

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

        public async Task InitializeAsync(CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();

            try
            {
                _logger.LogInformation("Initializing Cosmos DB connection...");

                if (_settings.DebugMode)
                {
                    _logger.LogDebug("DEBUG MODE ENABLED");
                    _logger.LogDebug("DEBUG: Target Cosmos Endpoint: {Endpoint}", _settings.Cosmos.Endpoint);

                    try
                    {
                        Uri endpointUri = new Uri(_settings.Cosmos.Endpoint);
                        _logger.LogDebug("DEBUG: Attempting DNS lookup for host: {Host}", endpointUri.Host);
                        IPHostEntry entry = await Dns.GetHostEntryAsync(endpointUri.Host);
                        _logger.LogDebug("DEBUG: DNS resolved host {Host} to {IPCount} IP addresses. First IP: {IPAddress}",
                            endpointUri.Host, entry.AddressList.Length, entry.AddressList.FirstOrDefault()?.ToString() ?? "N/A");
                    }
                    catch (Exception netEx)
                    {
                         _logger.LogWarning(netEx, "DEBUG: Network diagnostic check (DNS/Ping) failed for {Host}.", new Uri(_settings.Cosmos.Endpoint).Host);
                    }
                }

                var clientOptions = new CosmosClientOptions
                {
                    ConnectionMode = ConnectionMode.Gateway,
                    AllowBulkExecution = true,
                    MaxRetryAttemptsOnRateLimitedRequests = 9,
                    MaxRetryWaitTimeOnRateLimitedRequests = TimeSpan.FromSeconds(30),
                    RequestTimeout = TimeSpan.FromSeconds(60),
                    ApplicationName = "CosmosUploader",
                    EnableContentResponseOnWrite = false
                };

                if (_settings.DebugMode)
                {
                    _logger.LogDebug("DEBUG: CosmosClientOptions - ConnectionMode: {Mode}, AllowBulkExecution: {Bulk}, MaxRetryAttempts: {Retries}, MaxRetryWaitTime: {WaitTime}, RequestTimeout: {ReqTimeout}, AppName: {AppName}",
                        clientOptions.ConnectionMode, clientOptions.AllowBulkExecution, clientOptions.MaxRetryAttemptsOnRateLimitedRequests, clientOptions.MaxRetryWaitTimeOnRateLimitedRequests, clientOptions.RequestTimeout, clientOptions.ApplicationName);
                }

                _logger.LogDebug("Creating CosmosClient with endpoint: {Endpoint} and ConnectionMode: {Mode}",
                    _settings.Cosmos.Endpoint, clientOptions.ConnectionMode);
                _cosmosClient = new CosmosClient(
                    _settings.Cosmos.Endpoint,
                    _settings.Cosmos.Key,
                    clientOptions);

                _logger.LogDebug("Testing database connection (with cancellation race)");

                if (_settings.DebugMode)
                {
                    _logger.LogDebug("DEBUG: Calling CreateDatabaseIfNotExistsAsync for database '{DatabaseName}'...", _settings.Cosmos.DatabaseName);
                }

                var createDbTask = _cosmosClient.CreateDatabaseIfNotExistsAsync(
                    _settings.Cosmos.DatabaseName,
                    cancellationToken: cancellationToken);

                var cancellationTask = Task.Delay(Timeout.InfiniteTimeSpan, cancellationToken);

                var completedTask = await Task.WhenAny(createDbTask, cancellationTask);

                if (completedTask == cancellationTask)
                {
                    if (_settings.DebugMode)
                    {
                        dbWatch.Stop();
                        _logger.LogDebug("DEBUG: CreateDatabaseIfNotExistsAsync cancelled after {ElapsedMs}ms.", dbWatch.ElapsedMilliseconds);
                    }
                    _logger.LogWarning("Cosmos DB initialization cancelled during CreateDatabaseIfNotExistsAsync.");
                    throw new OperationCanceledException(cancellationToken);
                }

                var databaseResponse = await createDbTask;

                if (_settings.DebugMode)
                {
                     _logger.LogDebug("DEBUG: CreateDatabaseIfNotExistsAsync completed in {ElapsedMs}ms. Status: {StatusCode}, RU: {RequestCharge}",
                         dbWatch.ElapsedMilliseconds, databaseResponse.StatusCode, databaseResponse.RequestCharge);
                }

                _logger.LogDebug("Testing container connection (with cancellation race)");
                cancellationToken.ThrowIfCancellationRequested();

                if (_settings.DebugMode)
                {
                    _logger.LogDebug("DEBUG: Calling CreateContainerIfNotExistsAsync for container '{ContainerName}'...", _settings.Cosmos.ContainerName);
                }

                var createContainerTask = databaseResponse.Database.CreateContainerIfNotExistsAsync(
                    _settings.Cosmos.ContainerName,
                    _settings.Cosmos.PartitionKey,
                    cancellationToken: cancellationToken);

                cancellationTask = Task.Delay(Timeout.InfiniteTimeSpan, cancellationToken);

                completedTask = await Task.WhenAny(createContainerTask, cancellationTask);

                if (completedTask == cancellationTask)
                {
                    if (_settings.DebugMode)
                    {
                         _logger.LogDebug("DEBUG: CreateContainerIfNotExistsAsync cancelled after {ElapsedMs}ms.", containerWatch.ElapsedMilliseconds);
                    }
                    _logger.LogWarning("Cosmos DB initialization cancelled during CreateContainerIfNotExistsAsync.");
                    throw new OperationCanceledException(cancellationToken);
                }

                var containerResponse = await createContainerTask;

                if (_settings.DebugMode)
                {
                     _logger.LogDebug("DEBUG: CreateContainerIfNotExistsAsync completed in {ElapsedMs}ms. Status: {StatusCode}, RU: {RequestCharge}",
                         containerWatch.ElapsedMilliseconds, containerResponse.StatusCode, containerResponse.RequestCharge);
                }

                _container = containerResponse.Container;

                _logger.LogInformation("Successfully initialized Cosmos DB connection");
            }
            catch (Exception ex)
            {
                 if (_settings.DebugMode)
                {
                    _logger.LogDebug(ex, "DEBUG: Exception caught during InitializeAsync.");
                }

                if (cancellationToken.IsCancellationRequested)
                {
                    _logger.LogWarning("Cosmos DB initialization cancelled during operation.");
                    throw new OperationCanceledException("Operation cancelled during initialization.", ex, cancellationToken);
                }

                if (ex is CosmosException cosmosEx)
                {
                    _logger.LogError(cosmosEx,
                        "Cosmos DB error during initialization attempt. StatusCode: {StatusCode}, SubStatusCode: {SubStatusCode}, Message: {Message}, Diagnostics: {Diagnostics}",
                        cosmosEx.StatusCode, cosmosEx.SubStatusCode, cosmosEx.Message, cosmosEx.Diagnostics?.ToString() ?? "N/A");
                }
                else
                {
                    _logger.LogError(ex,
                        "Unexpected error during Cosmos DB initialization attempt: {Message}",
                        ex.Message);
                }

                throw;
            }
        }

        public async Task UploadReadingsAsync(List<SensorReading> readings, CancellationToken cancellationToken)
        {
            if (readings == null || readings.Count == 0)
            {
                _logger.LogInformation("No readings to upload");
                return;
            }

            if (_container == null)
            {
                _logger.LogError("Cosmos DB container has not been initialized");
                throw new InvalidOperationException("Cosmos DB container has not been initialized");
            }

            _logger.LogInformation("Starting bulk upload of {Count} readings...", readings.Count);
            var stopwatch = Stopwatch.StartNew();
            double operationRequestUnits = 0;
            int totalUploaded = 0;
            int totalFailed = 0;
            int totalConflicts = 0;

            var concurrentTasks = new List<Task<(ItemResponse<SensorReading>? Response, bool Success, bool IsConflict)>>();

            foreach (var reading in readings)
            {
                if (cancellationToken.IsCancellationRequested)
                {
                    _logger.LogWarning("Upload cancelled by user during task creation");
                    break;
                }

                if (_settings.DevelopmentMode)
                {
                    reading.Id = Guid.NewGuid().ToString();
                    reading.Timestamp = DateTime.UtcNow;
                }
                else
                {
                    if (string.IsNullOrEmpty(reading.Id))
                    {
                        reading.Id = Guid.NewGuid().ToString();
                    }
                }

                if (string.IsNullOrEmpty(reading.City))
                {
                    _logger.LogWarning("Reading with ID {ReadingId} missing City partition key. Using Location '{Location}' as fallback.", reading.Id, reading.Location);
                    reading.City = reading.Location;
                    if (string.IsNullOrEmpty(reading.City)) {
                         _logger.LogError("Reading with ID {ReadingId} has neither City nor Location. Cannot determine partition key. Skipping.", reading.Id);
                         totalFailed++;
                         continue;
                    }
                }

                concurrentTasks.Add(
                    _container.CreateItemAsync(
                        reading,
                        new PartitionKey(reading.City),
                        cancellationToken: cancellationToken
                    )
                    .ContinueWith(task => {
                        if (task.IsFaulted)
                        {
                            if (task.Exception?.InnerException is CosmosException cosmosEx && cosmosEx.StatusCode == System.Net.HttpStatusCode.Conflict)
                            {
                                _logger.LogDebug("Item {ItemId} already exists (Conflict - 409). Skipping.", reading.Id);
                                return (Response: (ItemResponse<SensorReading>?)null, Success: false, IsConflict: true);
                            }
                            else
                            {
                                _logger.LogError(task.Exception, "Failed to create item {ItemId}: {ErrorMessage}", reading.Id, task.Exception?.InnerException?.Message ?? task.Exception?.Message);
                                return (Response: (ItemResponse<SensorReading>?)null, Success: false, IsConflict: false);
                            }
                        }
                        if (task.IsCanceled)
                        {
                            _logger.LogWarning("Create task cancelled for item {ItemId}", reading.Id);
                            return (Response: (ItemResponse<SensorReading>?)null, Success: false, IsConflict: false);
                        }
                        if (_settings.Logging.LogRequestUnits)
                        {
                             _logger.LogDebug("Successfully created reading {Id} for sensor {SensorId}: {RU} RUs",
                                reading.Id, reading.SensorId, task.Result.RequestCharge);
                        }
                        return (Response: task.Result, Success: true, IsConflict: false);
                    }, cancellationToken)
                );
            }

             _logger.LogInformation("Awaiting completion of {Count} concurrent create tasks...", concurrentTasks.Count);
            var results = await Task.WhenAll(concurrentTasks);

            foreach (var result in results)
            {
                if (result.Success && result.Response != null)
                {
                    totalUploaded++;
                    operationRequestUnits += result.Response.RequestCharge;
                }
                else if (result.IsConflict)
                {
                    totalConflicts++;
                }
                else
                {
                    totalFailed++;
                }
            }

            _totalRequestUnits += (long)operationRequestUnits;
            stopwatch.Stop();

            _logger.LogInformation(
                "Bulk upload completed: {Total} items attempted in {ElapsedMs}ms. Success: {Uploaded}, Failed: {Failed}, Conflicts: {Conflicts}, RUs Consumed (approx): {RUs}",
                readings.Count,
                stopwatch.ElapsedMilliseconds,
                totalUploaded,
                totalFailed,
                totalConflicts,
                operationRequestUnits);

            if (cancellationToken.IsCancellationRequested)
            {
                  _logger.LogWarning("Operation was cancelled. Results might be partial.");
             }

            if (totalFailed > 0 && totalUploaded == 0)
            {
                _logger.LogError("Bulk upload failed for all items.");
            }
        }

        public async Task<int> GetContainerItemCountAsync()
        {
            if (_container == null)
            {
                _logger.LogError("Cosmos DB container has not been initialized");
                return 0;
            }

            try
            {
                int count = 0;
                QueryDefinition query = new QueryDefinition("SELECT VALUE COUNT(1) FROM c");
                using (FeedIterator<int> feedIterator = _container.GetItemQueryIterator<int>(query))
                {
                    while (feedIterator.HasMoreResults)
                    {
                        FeedResponse<int> response = await feedIterator.ReadNextAsync();
                        count += response.FirstOrDefault();
                        _totalRequestUnits += (long)response.RequestCharge;
                    }
                }
                _logger.LogInformation("Container item count: {Count}", count);
                return count;
            }
            catch (CosmosException ex)
            {
                _logger.LogError(ex, "Error retrieving item count. StatusCode: {StatusCode}", ex.StatusCode);
                return -1;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Unexpected error retrieving item count: {Message}", ex.Message);
                return -1;
            }
        }

        public Task<long> GetTotalRequestUnitsAsync()
        {
            return Task.FromResult(_totalRequestUnits);
        }
    }
}