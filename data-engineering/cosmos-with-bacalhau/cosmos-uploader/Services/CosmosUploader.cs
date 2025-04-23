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
    // Define placeholder data type consistent with processors
    using DataItem = System.Collections.Generic.Dictionary<string, object>;

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

            // Declare Stopwatches here so they are accessible throughout the try block
            Stopwatch? dbWatch = null;
            Stopwatch? containerWatch = null;

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
                    ConnectionMode = ConnectionMode.Direct,
                    AllowBulkExecution = true,
                    MaxRetryAttemptsOnRateLimitedRequests = 9,
                    MaxRetryWaitTimeOnRateLimitedRequests = TimeSpan.FromSeconds(30),
                    RequestTimeout = TimeSpan.FromSeconds(60),
                    ApplicationName = "CosmosUploader",
                    EnableContentResponseOnWrite = false
                };

                _logger.LogInformation("Using Cosmos DB ConnectionMode: {Mode}. Ensure outbound TCP ports 10250-10255 are open if using Direct mode.", clientOptions.ConnectionMode);

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
                    dbWatch = Stopwatch.StartNew();
                    _logger.LogDebug("DEBUG: Calling CreateDatabaseIfNotExistsAsync for database '{DatabaseName}'...", _settings.Cosmos.DatabaseName);
                }

                var createDbTask = _cosmosClient.CreateDatabaseIfNotExistsAsync(
                    _settings.Cosmos.DatabaseName,
                    cancellationToken: cancellationToken);

                var cancellationTask = Task.Delay(Timeout.InfiniteTimeSpan, cancellationToken);

                var completedTask = await Task.WhenAny(createDbTask, cancellationTask);

                if (completedTask == cancellationTask)
                {
                    dbWatch?.Stop();
                    if (_settings.DebugMode)
                    {
                        _logger.LogDebug("DEBUG: CreateDatabaseIfNotExistsAsync cancelled after {ElapsedMs}ms.", dbWatch?.ElapsedMilliseconds ?? -1);
                    }
                    _logger.LogWarning("Cosmos DB initialization cancelled during CreateDatabaseIfNotExistsAsync.");
                    throw new OperationCanceledException(cancellationToken);
                }

                var databaseResponse = await createDbTask;

                dbWatch?.Stop();
                if (_settings.DebugMode)
                {
                     _logger.LogDebug("DEBUG: CreateDatabaseIfNotExistsAsync completed in {ElapsedMs}ms. Status: {StatusCode}, RU: {RequestCharge}",
                         dbWatch?.ElapsedMilliseconds ?? -1, databaseResponse.StatusCode, databaseResponse.RequestCharge);
                }

                _logger.LogDebug("Testing container connection (with cancellation race)");
                cancellationToken.ThrowIfCancellationRequested();

                if (_settings.DebugMode)
                {
                    containerWatch = Stopwatch.StartNew();
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
                    containerWatch?.Stop();
                    if (_settings.DebugMode)
                    {
                         _logger.LogDebug("DEBUG: CreateContainerIfNotExistsAsync cancelled after {ElapsedMs}ms.", containerWatch?.ElapsedMilliseconds ?? -1);
                    }
                    _logger.LogWarning("Cosmos DB initialization cancelled during CreateContainerIfNotExistsAsync.");
                    throw new OperationCanceledException(cancellationToken);
                }

                var containerResponse = await createContainerTask;

                containerWatch?.Stop();
                if (_settings.DebugMode)
                {
                     _logger.LogDebug("DEBUG: CreateContainerIfNotExistsAsync completed in {ElapsedMs}ms. Status: {StatusCode}, RU: {RequestCharge}",
                         containerWatch?.ElapsedMilliseconds ?? -1, containerResponse.StatusCode, containerResponse.RequestCharge);
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

        // Modify signature and implementation to handle generic DataItems
        public async Task UploadDataAsync(IEnumerable<DataItem> data, CancellationToken cancellationToken)
        {
            if (data == null || !data.Any())
            {
                _logger.LogInformation("No data items to upload");
                return;
            }

            if (_container == null)
            {
                _logger.LogError("Cosmos DB container has not been initialized");
                throw new InvalidOperationException("Cosmos DB container has not been initialized");
            }

            int totalCount = data.Count();
            string processingStage = _settings.ProcessingStage;
            _logger.LogInformation("Starting bulk upload of {Count} {Stage} items...", totalCount, processingStage);
            var stopwatch = Stopwatch.StartNew();
            double operationRequestUnits = 0;
            int totalUploaded = 0;
            int totalFailed = 0;
            int totalConflicts = 0;

            // Verify all items have the required processingStage field
            foreach (var item in data)
            {
                if (!item.ContainsKey("processingStage"))
                {
                    _logger.LogWarning("Item missing 'processingStage' field. Setting to configured value: {Stage}", processingStage);
                    item["processingStage"] = processingStage;
                }
            }

            // Update task list type to handle generic object/DataItem
            var concurrentTasks = new List<Task<(ItemResponse<object>? Response, bool Success, bool IsConflict)>>();
            string partitionKeyPath = _settings.Cosmos.PartitionKey.TrimStart('/'); // Get the key name (e.g., "city")

            foreach (var item in data)
            {
                if (cancellationToken.IsCancellationRequested)
                {
                    _logger.LogWarning("Upload cancelled by user during task creation");
                    break;
                }

                // Ensure Id exists (processors should maintain it, or add it if needed)
                if (!item.ContainsKey("id") || item["id"] == null || string.IsNullOrWhiteSpace(item["id"].ToString()))
                {
                    string newId = Guid.NewGuid().ToString();
                    _logger.LogWarning("Item missing or has empty 'id', assigning new Guid: {NewId}", newId);
                    item["id"] = newId;
                }

                // Ensure partition key exists and has a value
                if (!item.TryGetValue(partitionKeyPath, out var partitionKeyValue) || partitionKeyValue == null || string.IsNullOrWhiteSpace(partitionKeyValue.ToString()))
                {
                     _logger.LogError("Item with ID {ItemId} is missing the partition key field '{PartitionKeyField}' or its value is null/empty. Skipping upload.", 
                        item.GetValueOrDefault("id", "[unknown_id]"), 
                        partitionKeyPath);
                     totalFailed++;
                     continue;
                }

                // Verify the item has the correct fields for its processing stage
                string itemStage = item.GetValueOrDefault("processingStage", processingStage)?.ToString() ?? processingStage;
                
                // Perform field validation based on processing stage
                if (!ValidateItemFields(item, itemStage))
                {
                    _logger.LogWarning("Item with ID {ItemId} is missing required fields for processing stage '{Stage}'. Uploading anyway with available fields.", 
                        item.GetValueOrDefault("id", "[unknown_id]"),
                        itemStage);
                }

                concurrentTasks.Add(
                    // Use generic object type for CreateItemAsync
                    _container.CreateItemAsync<object>(
                        item, 
                        new PartitionKey(partitionKeyValue.ToString()), // Extract partition key value
                        cancellationToken: cancellationToken)
                    .ContinueWith(task =>
                    {
                        cancellationToken.ThrowIfCancellationRequested(); // Check before processing result
                        if (task.IsCompletedSuccessfully)
                        {
                            return (task.Result, true, false);
                        }
                        if (task.IsFaulted)
                        {
                            if (task.Exception?.InnerException is CosmosException cosmosEx && cosmosEx.StatusCode == HttpStatusCode.Conflict)
                            {
                                // Treat conflict as a separate category, not necessarily a hard failure
                                return (null, false, true);
                            }
                            // Log other exceptions
                            _logger.LogError(task.Exception, "Bulk upload task failed for item ID {ItemId}: {ErrorMessage}", 
                                item.GetValueOrDefault("id", "[unknown_id]"), 
                                task.Exception?.InnerException?.Message ?? task.Exception?.Message ?? "Unknown error");
                            return (null, false, false);
                        }
                        // Handle cancellation if task status indicates it (though ThrowIfCancellationRequested should catch most)
                        if (task.IsCanceled) {
                            _logger.LogWarning("Bulk upload task was cancelled for item ID {ItemId}", item.GetValueOrDefault("id", "[unknown_id]"));
                            // Can decide how to count this, maybe as failed?
                            return (null, false, false);
                        }
                        // Default case (shouldn't happen often)
                        return (null, false, false);
                    }, cancellationToken)
                );

                // Optional: Throttle task creation if needed, e.g.:
                // if (concurrentTasks.Count >= 100) { // Limit concurrency
                //     var completedTask = await Task.WhenAny(concurrentTasks);
                //     concurrentTasks.Remove(completedTask);
                //     // Process completedTask result here or wait for the main loop
                // }
            }

             if (cancellationToken.IsCancellationRequested)
            {
                 _logger.LogWarning("Upload was cancelled after creating {TaskCount} upload tasks. Awaiting completion of initiated tasks...", concurrentTasks.Count);
            }
            else {
                 _logger.LogDebug("Created {TaskCount} upload tasks. Awaiting completion...", concurrentTasks.Count);
            }

            // Wait for all initiated tasks to complete
            await Task.WhenAll(concurrentTasks);

            // Process results
            foreach (var task in concurrentTasks)
            {
                var (response, success, isConflict) = task.Result; // Access the result directly as Task.WhenAll ensures completion

                if (success && response != null)
                {
                    totalUploaded++;
                    operationRequestUnits += response.RequestCharge;
                    if (_settings.Logging.LogLatency)
                    {
                        _logger.LogTrace("Uploaded item {Id} - RU: {RequestCharge}, Latency: {Latency}", 
                            response.Resource?.GetType().GetProperty("id")?.GetValue(response.Resource) ?? "unknown", // Try to get ID from response if possible
                            response.RequestCharge, 
                            response.Diagnostics.GetClientElapsedTime()); 
                    }
                }
                else if (isConflict)
                {
                    totalConflicts++;
                     _logger.LogWarning("Conflict detected for an item during bulk upload (item likely already exists).");
                }
                else
                {
                    // Already logged in the ContinueWith block
                    totalFailed++;
                }
            }

            stopwatch.Stop();
            _totalRequestUnits += (long)operationRequestUnits;

            if (totalFailed > 0)
            {
                 _logger.LogError("Bulk upload completed with {Failures} failures out of {Total} items.", totalFailed, totalCount);
            }
            if (totalConflicts > 0)
            {
                _logger.LogWarning("Bulk upload completed with {Conflicts} conflicts detected out of {Total} items.", totalConflicts, totalCount);
            }

            _logger.LogInformation(
                "Bulk upload of {ProcessingStage} data finished in {ElapsedSeconds:F2} seconds. Uploaded: {Uploaded}, Conflicts: {Conflicts}, Failed: {Failures}, Total RUs: {RequestUnits:F2}",
                processingStage,
                stopwatch.Elapsed.TotalSeconds,
                totalUploaded,
                totalConflicts,
                totalFailed,
                operationRequestUnits);
            
            // Decide if failure count warrants throwing an exception to halt processing
            if (totalFailed > 0 && totalFailed == totalCount) // Example: Fail if all items failed
            {
                 throw new Exception($"Bulk upload failed for all {totalFailed} items. See logs for details.");
            }
        }

        // Helper method to validate item fields based on processing stage
        private bool ValidateItemFields(DataItem item, string stage)
        {
            if (!ProcessingStage.IsValid(stage))
            {
                _logger.LogWarning("Invalid processing stage '{Stage}' for item ID {ItemId}", 
                    stage, item.GetValueOrDefault("id", "[unknown_id]"));
                return false;
            }

            // Get required fields for this stage
            var requiredFields = ProcessingStage.FieldRequirements.GetForStage(stage);
            
            // Check if all required fields are present
            bool isValid = true;
            foreach (var field in requiredFields)
            {
                if (!item.ContainsKey(field))
                {
                    _logger.LogDebug("Item ID {ItemId} missing required field '{Field}' for processing stage '{Stage}'", 
                        item.GetValueOrDefault("id", "[unknown_id]"), field, stage);
                    isValid = false;
                }
            }
            
            return isValid;
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