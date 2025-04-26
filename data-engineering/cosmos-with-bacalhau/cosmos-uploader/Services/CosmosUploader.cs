using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using CosmosUploader.Configuration;
using Microsoft.Azure.Cosmos;
using Microsoft.Extensions.Logging;
using CosmosUploader.Models;

namespace CosmosUploader.Services
{
    // Re-apply interface implementation
    public class CosmosUploader : ICosmosUploader
    {
        private readonly ILogger<CosmosUploader> _logger;
        private readonly AppSettings _settings;
        private CosmosClient? _cosmosClient;
        private Container? _container;
        private long _totalRequestUnits = 0;
        private bool _isInitialized;

        public CosmosUploader(ILogger<CosmosUploader> logger, AppSettings settings)
        {
            _logger = logger;
            _settings = settings;
        }

        public async Task InitializeAsync(CancellationToken cancellationToken)
        {
            if (_isInitialized)
            {
                return;
            }

            if (_cosmosClient != null)
            {
                _logger.LogWarning("Cosmos DB client is already initialized");
                return;
            }
            if (_settings.Cosmos == null)
            {
                throw new InvalidOperationException("Cosmos settings are not configured");
            }

            try
            {
                _logger.LogInformation("Initializing Cosmos DB client...");
                _cosmosClient = new CosmosClient(
                    _settings.Cosmos.Endpoint,
                    _settings.Cosmos.Key,
                    new CosmosClientOptions
                    {
                        ApplicationName = "CosmosUploader",
                        ConnectionMode = ConnectionMode.Direct,
                        MaxRetryAttemptsOnRateLimitedRequests = 5,
                        MaxRetryWaitTimeOnRateLimitedRequests = TimeSpan.FromSeconds(30)
                    });

                _logger.LogInformation("Getting Database: {DatabaseName}", _settings.Cosmos.DatabaseName);
                Database database = await _cosmosClient.CreateDatabaseIfNotExistsAsync(
                   _settings.Cosmos.DatabaseName,
                    cancellationToken: cancellationToken);
                _logger.LogInformation("Database obtained successfully.");

                _logger.LogInformation("Getting Container: {ContainerName}", _settings.Cosmos.ContainerName);
                string partitionKeyPath = _settings.Cosmos.PartitionKey ?? "/partitionKey";
                if (!partitionKeyPath.StartsWith("/"))
                {
                    partitionKeyPath = "/" + partitionKeyPath;
                }
                _logger.LogDebug("Using Partition Key Path: {Path}", partitionKeyPath);

                _container = await database.CreateContainerIfNotExistsAsync(
                    _settings.Cosmos.ContainerName,
                    partitionKeyPath,
                    cancellationToken: cancellationToken);
                 _logger.LogInformation("Container obtained successfully.");

                _isInitialized = true;
                _logger.LogInformation("Cosmos DB client initialized successfully");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to initialize Cosmos DB client");
                throw;
            }
        }

        public async Task UploadDataAsync(List<DataTypes.DataItem> data, string dataPath, CancellationToken cancellationToken)
        {
            if (!_isInitialized)
            {
                _logger.LogWarning("CosmosUploader not initialized. Initializing now...");
                await InitializeAsync(cancellationToken); 
            }

            if (_container == null)
            {
                throw new InvalidOperationException("Cosmos container is not initialized after attempt.");
            }

            if (data == null || !data.Any())
            {
                _logger.LogWarning("No data provided to upload.");
                return;
            }

            if (_settings?.Cosmos == null)
            {
                throw new InvalidOperationException("Cosmos settings are not configured.");
            }

            string partitionKeyName = _settings.Cosmos.PartitionKey ?? "partitionKey";
            if (partitionKeyName.StartsWith("/"))
            {
                partitionKeyName = partitionKeyName.Substring(1);
            }

            _logger.LogInformation("Starting upload of {Count} items to Cosmos DB [Database: {Db}, Container: {Container}]...",
                data.Count, _settings.Cosmos.DatabaseName, _settings.Cosmos.ContainerName);

            var tasks = new List<Task>();
            Stopwatch stopwatch = Stopwatch.StartNew();
            double totalRU = 0;
            int successfulUploads = 0;
            int failedUploads = 0;
            int conflictUploads = 0;

            // Create a linked token source to allow cancelling this specific batch on 503
            using var batchCts = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
            var batchToken = batchCts.Token;

            foreach (var item in data)
            {
                cancellationToken.ThrowIfCancellationRequested();

                // Store local_reading_id for logging/error context before potentially removing 'id' key
                string logItemId = item.TryGetValue("local_reading_id", out object? localId) && localId != null ? localId.ToString() ?? "unknown" : "unknown";

                try
                {
                    // Ensure the 'id' field is present. Generate one if it's missing.
                    if (!item.ContainsKey("id") || item["id"] == null || string.IsNullOrWhiteSpace(item["id"].ToString()))
                    {
                        string newId = Guid.NewGuid().ToString();
                        item["id"] = newId;
                        _logger.LogTrace("Generated new GUID '{NewId}' for item with local_reading_id {LogItemId}.", newId, logItemId);
                    }
                    else
                    {
                         _logger.LogTrace("Using existing 'id' '{ExistingId}' for item with local_reading_id {LogItemId}.", item["id"], logItemId);
                    }

                    if (!item.TryGetValue(partitionKeyName, out object? pkValue) || pkValue == null)
                    {
                         _logger.LogWarning("Item missing partition key field '{PartitionKeyName}' or value is null. Skipping item with local_reading_id: {LogItemId}", partitionKeyName, logItemId);
                         failedUploads++;
                         continue;
                    }
                    string partitionKeyValue = string.Empty;
                    if (pkValue != null)
                    {
                        partitionKeyValue = pkValue.ToString() ?? string.Empty;
                    }
                    if (string.IsNullOrEmpty(partitionKeyValue))
                    {
                        _logger.LogWarning("Partition key value for field '{PartitionKeyName}' is empty. Skipping item: {LogItemId}", partitionKeyName, logItemId);
                        failedUploads++;
                        continue;
                    }

                    // Use the batch-specific token for the create operation
                    tasks.Add(_container.CreateItemAsync(item, new PartitionKey(partitionKeyValue), cancellationToken: batchToken)
                        .ContinueWith(task =>
                        {
                            // Check the batch token first - if cancellation was requested (e.g., by a 503), don't process result
                            if (batchToken.IsCancellationRequested)
                            {
                                return; // Stop processing results for this task if batch was cancelled
                            }

                            if (task.IsCompletedSuccessfully)
                            {
                                Interlocked.Increment(ref successfulUploads);
                                var responseItem = task.Result.Resource;
                                string? cosmosId = "unknown"; // Default if resource is somehow null
                                if (responseItem != null && responseItem.ContainsKey("id"))
                                {
                                    cosmosId = responseItem["id"]?.ToString();
                                }
                                
                                totalRU += task.Result.RequestCharge;
                                _logger.LogTrace("Successfully uploaded item (Local ID: {LogItemId}, Cosmos ID: {CosmosId}). RU: {RU}", 
                                    logItemId, cosmosId, task.Result.RequestCharge);
                            }
                            else if (task.IsFaulted)
                            {
                                // Check for Service Unavailable (503) first
                                if (task.Exception?.InnerException is CosmosException cosmosEx503 && cosmosEx503.StatusCode == System.Net.HttpStatusCode.ServiceUnavailable)
                                {
                                    Interlocked.Increment(ref failedUploads); // Still count as failed for this batch attempt report
                                    // Log as Warning since we intend to retry
                                    _logger.LogWarning("Service Unavailable (503) detected for item (Local ID: {LogItemId}). Halting batch upload for this cycle. Will retry later.", logItemId);
                                    // Cancel the rest of the batch
                                    try { batchCts.Cancel(); } catch (ObjectDisposedException) { /* Ignore if already disposed */ }
                                }
                                // Check for TooManyRequests (429) next
                                else if (task.Exception?.InnerException is CosmosException cosmosEx429 && cosmosEx429.StatusCode == System.Net.HttpStatusCode.TooManyRequests)
                                {
                                    Interlocked.Increment(ref failedUploads); // Count as failed for this batch attempt report
                                    _logger.LogWarning("TooManyRequests (429) detected for item (Local ID: {LogItemId}). Halting batch upload for this cycle. Will retry later.", logItemId);
                                    // Cancel the rest of the batch
                                    try { batchCts.Cancel(); } catch (ObjectDisposedException) { /* Ignore if already disposed */ }
                                }
                                // Then check for Conflict (409)
                                else if (task.Exception?.InnerException is CosmosException cosmosEx409 && cosmosEx409.StatusCode == System.Net.HttpStatusCode.Conflict)
                                {
                                    Interlocked.Increment(ref conflictUploads);
                                    // Log conflict, which might occur if the explicitly provided/generated ID already exists.
                                    _logger.LogWarning(task.Exception?.InnerException, "Conflict (409) detected for item (Local ID: {LogItemId}, Document ID: {DocumentId}). Skipping.", logItemId, item.TryGetValue("id", out var docId) ? docId : "unknown");
                                }
                                // Add specific handling for BadRequest (400)
                                else if (task.Exception?.InnerException is CosmosException cosmosEx400 && cosmosEx400.StatusCode == System.Net.HttpStatusCode.BadRequest)
                                {
                                    string errorMessage = cosmosEx400.ResponseBody ?? cosmosEx400.Message;
                                    // Handle BadRequest errors normally now that we explicitly set 'id'
                                    Interlocked.Increment(ref failedUploads);
                                    _logger.LogError(cosmosEx400, "BadRequest (400) detected for item (Local ID: {LogItemId}, Document ID: {DocumentId}). Reason: {Reason}", logItemId, item.TryGetValue("id", out var docId400) ? docId400 : "unknown", errorMessage);
                                }
                                // Handle other failures
                                else
                                {
                                    Interlocked.Increment(ref failedUploads);
                                    _logger.LogError(task.Exception?.InnerException ?? task.Exception, "Failed to upload item (Local ID: {LogItemId})", logItemId);
                                }
                            }
                            else if (task.IsCanceled && task.Exception == null)
                            {
                                // Log cancellation specifically if it wasn't due to an exception (e.g., external cancellation)
                                // Don't increment failure count here, as it might be intended cancellation.
                                _logger.LogWarning("Upload task cancelled for item (Local ID: {LogItemId}) (external request or 503 propagation).", logItemId);
                            }
                            // Note: If task.IsCanceled is true AND task.Exception is not null, it's likely due to the token passed
                            // to CreateItemAsync being cancelled (e.g., by our batchCts.Cancel()), which is handled by IsFaulted.
                        }, CancellationToken.None)); // Use CancellationToken.None for the continuation itself
                }
                catch (Exception ex)
                {
                    Interlocked.Increment(ref failedUploads);
                     // Use logItemId which was captured before potentially removing 'id'
                     _logger.LogError(ex, "Error preparing item for upload (Local ID: {LogItemId}): {ItemJson}", logItemId, System.Text.Json.JsonSerializer.Serialize(item));
                }
            }

            try
            {
                 await Task.WhenAll(tasks);
            }
            catch (OperationCanceledException ex) // Catch cancellation specific to Task.WhenAll
            {
                // Check if cancellation was triggered by our batch CTS (likely a 503) or the external token
                if (ex.CancellationToken == batchToken)
                {
                    _logger.LogWarning("Batch upload halted due to Service Unavailable (503). Only partially completed.");
                }
                else if (ex.CancellationToken == cancellationToken)
                {
                    _logger.LogWarning("Batch upload cancelled by external request.");
                }
                else
                {
                    _logger.LogWarning("Upload operation cancelled during Task.WhenAll."); // Generic cancellation
                }
            }
            catch (AggregateException aggEx)
            { 
                // Check if the aggregate exception contains the cancellation we triggered
                if (aggEx.InnerExceptions.OfType<OperationCanceledException>().Any(oce => oce.CancellationToken == batchToken))
                {
                    _logger.LogWarning("Batch upload halted due to Service Unavailable (503) resulting in AggregateException. Only partially completed.");
                }
                else
                {
                    _logger.LogError(aggEx, "AggregateException occurred during Task.WhenAll that was not related to batch cancellation.");
                    // Re-throw if it's not the expected cancellation scenario, as it represents other errors.
                    // Note: This might still be caught by Program.cs, which is okay.
                    throw; 
                }
            }

            stopwatch.Stop();
            _totalRequestUnits += (long)totalRU; // Note: RU count might be slightly off if cancelled mid-operation

            // Log results, indicating if the batch was halted
            string completionStatus = batchCts.IsCancellationRequested ? "(Halted by 503, 429, or Cancellation)" : "(Completed)";
            _logger.LogInformation("Upload batch processing finished {Status} in {ElapsedMs} ms. Successful: {SuccessCount}, Conflicts (Skipped): {ConflictCount}, Other Failures: {FailCount}. Total RU consumed for batch: {RU}",
                completionStatus, stopwatch.ElapsedMilliseconds, successfulUploads, conflictUploads, failedUploads, totalRU);

            // Only throw a hard exception for non-503/429 failures if the batch wasn't intentionally cancelled
            if (failedUploads > 0 && !batchCts.IsCancellationRequested)
            {
                throw new Exception($"{failedUploads} items failed to upload due to errors (excluding conflicts, 503s, and 429s). Check logs for details.");
            }
            else if (successfulUploads == 0 && conflictUploads == 0 && !batchCts.IsCancellationRequested && !cancellationToken.IsCancellationRequested)
            {
                _logger.LogWarning("No items were successfully uploaded or skipped due to conflicts, and the operation was not cancelled.");
            }

            // Update status based on items processed before any potential cancellation
            if (successfulUploads > 0 || conflictUploads > 0)
            {
                _logger.LogInformation("Processed {Count} items (Successful + Conflicts) for data path: {DataPath}", successfulUploads + conflictUploads, dataPath);
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