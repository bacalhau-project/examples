using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using System.Net.Http;
using CosmosUploader.Configuration;
using Microsoft.Azure.Cosmos;
using Microsoft.Extensions.Logging;
using CosmosUploader.Models;
using Microsoft.Azure.Cosmos.Linq; // Required for CountAsync

namespace CosmosUploader.Services
{
    // Re-apply interface implementation
    public class CosmosUploader : ICosmosUploader
    {
        private readonly ILogger<CosmosUploader> _logger;
        private readonly AppSettings _settings;
        private readonly IHttpClientFactory _httpClientFactory;
        private CosmosClient? _cosmosClient;
        private Container? _container;
        private long _totalRequestUnits = 0;
        private bool _isInitialized;

        public CosmosUploader(ILogger<CosmosUploader> logger, AppSettings settings, IHttpClientFactory httpClientFactory)
        {
            _logger = logger;
            _settings = settings;
            _httpClientFactory = httpClientFactory;
        }

        private async Task<bool> CheckHttpConnectivityAsync(CancellationToken cancellationToken)
        {
            if (_settings.Cosmos?.Endpoint == null)
            {
                _logger.LogWarning("[Connectivity Check] Cosmos endpoint URL is null in settings. Skipping check.");
                return false;
            }

            Uri? endpointUri;
            try
            {
                endpointUri = new Uri(_settings.Cosmos.Endpoint);
            }
            catch (UriFormatException ex)
            {
                _logger.LogWarning(ex, "[Connectivity Check] Invalid Cosmos endpoint URL format: {Endpoint}. Skipping check.", _settings.Cosmos.Endpoint);
                return false;
            }

            _logger.LogInformation("[Connectivity Check] Testing basic HTTPS connection to endpoint: {Endpoint}", endpointUri);

            try
            {
                using var httpClient = _httpClientFactory.CreateClient("CosmosConnectivityCheck");
                httpClient.Timeout = TimeSpan.FromSeconds(60);

                using var request = new HttpRequestMessage(HttpMethod.Head, endpointUri);
                using var response = await httpClient.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken);

                _logger.LogInformation("[Connectivity Check] Received HTTP status code {StatusCode} from {Endpoint}. Endpoint appears reachable.", response.StatusCode, endpointUri);
                return true;
            }
            catch (HttpRequestException ex)
            {
                _logger.LogError(ex, "[Connectivity Check] Failed to connect to {Endpoint} due to HttpRequestException: {Message}", endpointUri, ex.Message);
                return false;
            }
            catch (TaskCanceledException ex) when (ex.InnerException is TimeoutException)
            {
                _logger.LogError(ex, "[Connectivity Check] Connection attempt to {Endpoint} timed out.", endpointUri);
                return false;
            }
            catch (TaskCanceledException) when (cancellationToken.IsCancellationRequested)
            {
                _logger.LogWarning("[Connectivity Check] Connectivity check cancelled.");
                cancellationToken.ThrowIfCancellationRequested();
                return false;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "[Connectivity Check] An unexpected error occurred while checking connectivity to {Endpoint}: {Message}", endpointUri, ex.Message);
                return false;
            }
        }

        public async Task InitializeAsync(CancellationToken cancellationToken)
        {
            // If already fully initialized (client AND container are ready), just return.
            if (_isInitialized)
            {
                return;
            }

            if (_settings.Cosmos == null)
            {
                // Log error and prevent further execution if config is missing
                _logger.LogError("Cosmos settings are not configured. Cannot initialize.");
                return; // Nothing more to do if settings are missing.
            }

            _logger.LogInformation("Performing pre-initialization HTTP connectivity check...");
            bool canConnectHttp = await CheckHttpConnectivityAsync(cancellationToken);
            if (!canConnectHttp)
            {
                _logger.LogWarning("Pre-initialization HTTP connectivity check failed. Proceeding with CosmosClient initialization attempt anyway...");
            }
            else
            {
                _logger.LogInformation("Pre-initialization HTTP connectivity check successful.");
            }

            const int maxRetries = 3;
            const int initialDelayMs = 1000; // 1 second initial delay

            // Ensure any potentially lingering client from a previous failed init attempt is disposed.
            // This guards against the state where _cosmosClient is non-null but _isInitialized is false.
            _cosmosClient?.Dispose();
            _cosmosClient = null;
            _container = null;

            for (int attempt = 1; attempt <= maxRetries; attempt++)
            {
                 cancellationToken.ThrowIfCancellationRequested(); // Check before each attempt

                try
                {
                    _logger.LogInformation("Attempt {Attempt}/{MaxRetries}: Initializing Cosmos DB client...", attempt, maxRetries);
                    _cosmosClient = new CosmosClient(
                        _settings.Cosmos.Endpoint,
                        _settings.Cosmos.Key,
                        new CosmosClientOptions
                        {
                            ApplicationName = "CosmosUploader",
                            ConnectionMode = ConnectionMode.Gateway,
                            MaxRetryAttemptsOnRateLimitedRequests = 5,
                            MaxRetryWaitTimeOnRateLimitedRequests = TimeSpan.FromSeconds(30),
                            // Increase the overall request timeout significantly due to observed latency
                            RequestTimeout = TimeSpan.FromSeconds(60) // Default is often lower (e.g., 60s total including retries? Let's try explicit 60s per attempt)
                        });

                    _logger.LogInformation("Attempt {Attempt}/{MaxRetries}: Getting Database: {DatabaseName}", attempt, maxRetries, _settings.Cosmos.DatabaseName);
                    Database database = await _cosmosClient.CreateDatabaseIfNotExistsAsync(
                       _settings.Cosmos.DatabaseName,
                        cancellationToken: cancellationToken);
                    _logger.LogInformation("Attempt {Attempt}/{MaxRetries}: Database obtained successfully.", attempt, maxRetries);

                    _logger.LogInformation("Attempt {Attempt}/{MaxRetries}: Getting Container: {ContainerName}", attempt, maxRetries, _settings.Cosmos.ContainerName);
                    string partitionKeyPath = _settings.Cosmos.PartitionKey ?? "/partitionKey";
                    if (!partitionKeyPath.StartsWith("/"))
                    {
                        partitionKeyPath = "/" + partitionKeyPath;
                    }
                    _logger.LogDebug("Attempt {Attempt}/{MaxRetries}: Using Partition Key Path: {Path}", attempt, maxRetries, partitionKeyPath);

                    _container = await database.CreateContainerIfNotExistsAsync(
                        _settings.Cosmos.ContainerName,
                        partitionKeyPath,
                        cancellationToken: cancellationToken);
                    _logger.LogInformation("Attempt {Attempt}/{MaxRetries}: Container obtained successfully.", attempt, maxRetries);

                    // CRITICAL: Set initialized flag ONLY after BOTH client and container are confirmed.
                    _isInitialized = true;
                    _logger.LogInformation("Cosmos DB client initialized successfully on attempt {Attempt}/{MaxRetries}.", attempt, maxRetries);
                    break; // Success, exit the retry loop
                }
                catch (CosmosException cex)
                {
                    _logger.LogError(cex, "Attempt {Attempt}/{MaxRetries}: CosmosException during initialization. Status Code: {StatusCode}, Substatus: {SubStatusCode}, ActivityId: {ActivityId}. Diagnostics: {Diagnostics}",
                        attempt, maxRetries, cex.StatusCode, cex.SubStatusCode, cex.ActivityId, cex.Diagnostics);

                    if (attempt < maxRetries)
                    {
                        int delayMs = initialDelayMs * (int)Math.Pow(2, attempt - 1);
                        _logger.LogWarning("Attempt {Attempt}/{MaxRetries} failed. Retrying in {DelaySeconds} seconds...", attempt, maxRetries, delayMs / 1000.0);
                        await Task.Delay(delayMs, cancellationToken);
                    }
                    else
                    {
                        _logger.LogError("Attempt {Attempt}/{MaxRetries}: Final attempt failed. Giving up on initialization for this cycle.", attempt, maxRetries);
                    }
                }
                catch (Exception ex)
                {
                    // Catch unexpected exceptions during initialization
                    _logger.LogError(ex, "Attempt {Attempt}/{MaxRetries}: Unexpected error during initialization.", attempt, maxRetries);
                    // Don't retry on unexpected errors, break the loop.
                    break;
                }
            }

            // Final check and cleanup if initialization failed after all retries
            if (!_isInitialized)
            {
                _logger.LogError("Cosmos DB client initialization failed after {MaxRetries} attempts. Will skip upload cycle.", maxRetries);
                // Ensure cleanup happens if the loop finishes without success
                _cosmosClient?.Dispose();
                _cosmosClient = null;
                _container = null;
            }
        }

        public async Task UploadDataAsync(List<DataTypes.DataItem> data, string dataPath, CancellationToken cancellationToken)
        {
            // Call InitializeAsync IF NOT already initialized.
            // InitializeAsync will handle its own internal checks and retries.
            if (!_isInitialized)
            {
                 _logger.LogInformation("CosmosUploader is not initialized. Attempting initialization...");
                 await InitializeAsync(cancellationToken);
                 
                 // After attempting initialization, check AGAIN if it succeeded.
                 if (!_isInitialized)
                 {
                    _logger.LogWarning("Initialization failed after attempts. Skipping upload for data file: {DataPath}", dataPath);
                    return;
                 }
                 _logger.LogInformation("Initialization successful, proceeding with upload.");
            }

            // At this point, if _isInitialized is true, _container SHOULD be non-null.
            // Add a safeguard check just in case, but log it as a potential internal error.
            if (_container == null)
            {
                 _logger.LogError("Internal State Error: CosmosUploader is marked initialized, but container is null. Skipping upload for data file: {DataPath}", dataPath);
                 return;
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

            _logger.LogInformation("Starting upload of {Count} items to Cosmos DB [Database: {Db}, Container: {Container}]... from {DataPath}",
                data.Count, _settings.Cosmos.DatabaseName, _settings.Cosmos.ContainerName, dataPath);

            var distinctPartitionKeys = data
                .Select(item => item.TryGetValue(partitionKeyName, out var pk) && pk != null ? pk.ToString() : null)
                .Where(pk => !string.IsNullOrEmpty(pk))
                .Distinct()
                .ToList();

            if (_settings.DebugMode && distinctPartitionKeys.Any())
            {
                long preUploadCount = 0;
                try
                {
                    _logger.LogDebug("[DEBUG] Querying pre-upload count for partitions: [{Partitions}]", string.Join(", ", distinctPartitionKeys));
                    preUploadCount = await GetCountForPartitionKeysAsync(distinctPartitionKeys, partitionKeyName, cancellationToken);
                    _logger.LogDebug("[DEBUG] Pre-upload count for relevant partitions: {Count}", preUploadCount);
                }
                catch (Exception ex)
                {
                    _logger.LogWarning(ex, "[DEBUG] Failed to query pre-upload count.");
                    // Continue with upload even if pre-count fails
                }
            }

            var tasks = new List<Task>();
            Stopwatch stopwatch = Stopwatch.StartNew();
            double totalRU = 0;
            int successfulUploads = 0;
            int failedUploads = 0;
            int conflictUploads = 0;

            using var batchCts = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
            var batchToken = batchCts.Token;

            foreach (var item in data)
            {
                cancellationToken.ThrowIfCancellationRequested();

                // Store sqlite_id for logging/error context before potentially removing 'id' key
                string logItemId = item.TryGetValue("sqlite_id", out object? sqliteIdObj) && sqliteIdObj != null ? sqliteIdObj.ToString() ?? "unknown" : "unknown";

                try
                {
                    // Ensure the 'id' field is present. Generate one if it's missing.
                    if (!item.ContainsKey("id") || item["id"] == null || string.IsNullOrWhiteSpace(item["id"].ToString()))
                    {
                        string newId = Guid.NewGuid().ToString();
                        item["id"] = newId;
                        _logger.LogTrace("Generated new GUID '{NewId}' for item with sqlite_id {LogItemId}.", newId, logItemId);
                    }
                    else
                    {
                         _logger.LogTrace("Using existing 'id' '{ExistingId}' for item with sqlite_id {LogItemId}.", item["id"], logItemId);
                    }

                    if (!item.TryGetValue(partitionKeyName, out object? pkValue) || pkValue == null)
                    {
                         _logger.LogWarning("Item missing partition key field '{PartitionKeyName}' or value is null. Skipping item with sqlite_id: {LogItemId}", partitionKeyName, logItemId);
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
                        _logger.LogWarning("Partition key value for field '{PartitionKeyName}' is empty. Skipping item with sqlite_id: {LogItemId}", partitionKeyName, logItemId);
                        failedUploads++;
                        continue;
                    }

                    // --- DIAGNOSTIC LOGGING --- 
                    // Log the item content right before the upload attempt
                    try 
                    {
                        var pkForLog = item.TryGetValue(partitionKeyName, out var pkValLog) ? pkValLog?.ToString() : "<missing_pk>";
                        var idForLog = item.TryGetValue("id", out var idValLog) ? idValLog?.ToString() : "<missing_id>";
                        var pressureForLog = item.TryGetValue("pressure", out var pressureValLog) ? pressureValLog?.ToString() : "<missing_pressure>";
                        var humidityForLog = item.TryGetValue("humidity", out var humidityValLog) ? humidityValLog?.ToString() : "<missing_humidity>";
                        
                        _logger.LogDebug("Preparing to upload item. SQLiteID: {SqliteId}, DocID: {DocId}, PK ({PKName}): {PKValue}, Pressure: {Pressure}, Humidity: {Humidity}", 
                            logItemId, idForLog, partitionKeyName, pkForLog, pressureForLog, humidityForLog);
                    }
                    catch(Exception logEx)
                    {
                        _logger.LogWarning(logEx, "Error during diagnostic logging for item SQLiteID {SqliteId}", logItemId);
                    }
                    // --- END DIAGNOSTIC LOGGING ---

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
                                _logger.LogTrace("Successfully uploaded item (SQLite ID: {LogItemId}, Cosmos ID: {CosmosId}). RU: {RU}", 
                                    logItemId, cosmosId, task.Result.RequestCharge);
                            }
                            else if (task.IsFaulted)
                            {
                                // Check for Service Unavailable (503) first
                                if (task.Exception?.InnerException is CosmosException cosmosEx503 && cosmosEx503.StatusCode == System.Net.HttpStatusCode.ServiceUnavailable)
                                {
                                    Interlocked.Increment(ref failedUploads); // Still count as failed for this batch attempt report
                                    // Log as Warning since we intend to retry
                                    _logger.LogWarning("Service Unavailable (503) detected for item (SQLite ID: {LogItemId}). Halting batch upload for this cycle. Will retry later.", logItemId);
                                    // Cancel the rest of the batch
                                    try { batchCts.Cancel(); } catch (ObjectDisposedException) { /* Ignore if already disposed */ }
                                }
                                // Check for TooManyRequests (429) next
                                else if (task.Exception?.InnerException is CosmosException cosmosEx429 && cosmosEx429.StatusCode == System.Net.HttpStatusCode.TooManyRequests)
                                {
                                    Interlocked.Increment(ref failedUploads); // Count as failed for this batch attempt report
                                    _logger.LogWarning("TooManyRequests (429) detected for item (SQLite ID: {LogItemId}). Halting batch upload for this cycle. Will retry later.", logItemId);
                                    // Cancel the rest of the batch
                                    try { batchCts.Cancel(); } catch (ObjectDisposedException) { /* Ignore if already disposed */ }
                                }
                                // Then check for Conflict (409)
                                else if (task.Exception?.InnerException is CosmosException cosmosEx409 && cosmosEx409.StatusCode == System.Net.HttpStatusCode.Conflict)
                                {
                                    Interlocked.Increment(ref conflictUploads);
                                    // Log conflict, which might occur if the explicitly provided/generated ID already exists.
                                    _logger.LogWarning(task.Exception?.InnerException, "Conflict (409) detected for item (SQLite ID: {LogItemId}, Document ID: {DocumentId}). Skipping.", logItemId, item.TryGetValue("id", out var docId) ? docId : "unknown");
                                }
                                // Add specific handling for BadRequest (400)
                                else if (task.Exception?.InnerException is CosmosException cosmosEx400 && cosmosEx400.StatusCode == System.Net.HttpStatusCode.BadRequest)
                                {
                                    string errorMessage = cosmosEx400.ResponseBody ?? cosmosEx400.Message;
                                    // Handle BadRequest errors normally now that we explicitly set 'id'
                                    Interlocked.Increment(ref failedUploads);
                                    _logger.LogError(cosmosEx400, "BadRequest (400) detected for item (SQLite ID: {LogItemId}, Document ID: {DocumentId}). Reason: {Reason}", logItemId, item.TryGetValue("id", out var docId400) ? docId400 : "unknown", errorMessage);
                                }
                                // Handle other failures
                                else
                                {
                                    Interlocked.Increment(ref failedUploads);
                                    _logger.LogError(task.Exception?.InnerException ?? task.Exception, "Failed to upload item (SQLite ID: {LogItemId})", logItemId);
                                }
                            }
                            else if (task.IsCanceled && task.Exception == null)
                            {
                                // Log cancellation specifically if it wasn't due to an exception (e.g., external cancellation)
                                // Don't increment failure count here, as it might be intended cancellation.
                                _logger.LogWarning("Upload task cancelled for item (SQLite ID: {LogItemId}) (external request or 503 propagation).", logItemId);
                            }
                            // Note: If task.IsCanceled is true AND task.Exception is not null, it's likely due to the token passed
                            // to CreateItemAsync being cancelled (e.g., by our batchCts.Cancel()), which is handled by IsFaulted.
                        }, CancellationToken.None)); // Use CancellationToken.None for the continuation itself
                }
                catch (Exception ex)
                {
                    failedUploads++;
                    _logger.LogError(ex, "Error processing or adding task for item (SQLite ID: {LogItemId})", logItemId);
                }
            }

            try
            {
                await Task.WhenAll(tasks);
            }
            catch (OperationCanceledException) when (batchToken.IsCancellationRequested)
            {
                _logger.LogWarning("Batch upload partially cancelled due to rate limiting (503) or excessive requests (429). Remaining tasks in this batch were halted.");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Unexpected error occurred while waiting for batch upload tasks to complete.");
            }
            stopwatch.Stop();

            if (_settings.DebugMode && distinctPartitionKeys.Any())
            {
                long postUploadCount = 0;
                try
                {
                    await Task.Delay(TimeSpan.FromSeconds(2), cancellationToken);
                    _logger.LogDebug("[DEBUG] Querying post-upload count for partitions: [{Partitions}]", string.Join(", ", distinctPartitionKeys));
                    postUploadCount = await GetCountForPartitionKeysAsync(distinctPartitionKeys, partitionKeyName, cancellationToken);
                    _logger.LogDebug("[DEBUG] Post-upload count for relevant partitions: {Count}", postUploadCount);
                }
                catch (OperationCanceledException) { /* Ignore if main operation was cancelled */ }
                catch (Exception ex)
                {
                    _logger.LogWarning(ex, "[DEBUG] Failed to query post-upload count.");
                }
            }

            _totalRequestUnits += (long)totalRU;

            _logger.LogInformation(
                "Upload batch completed in {ElapsedMilliseconds} ms. Successful: {SuccessCount}, Failed: {FailCount}, Conflicts (Skipped): {ConflictCount}, Total RU: {TotalRU:F2}",
                stopwatch.ElapsedMilliseconds,
                successfulUploads,
                failedUploads,
                conflictUploads,
                totalRU);

            if (batchCts.IsCancellationRequested && (failedUploads > 0 || conflictUploads == 0))
            {
                _logger.LogWarning("Upload batch was halted prematurely due to rate limiting (503/429). Subsequent processing cycles will attempt to retry.");
            }
        }

        private async Task<long> GetCountForPartitionKeysAsync(List<string?> partitionKeys, string partitionKeyName, CancellationToken cancellationToken)
        {
            if (_container == null) return 0;

            long totalCount = 0;
            var queryTasks = new List<Task<long>>();

            foreach (var pkValue in partitionKeys)
            {
                // Skip null values (should not occur due to Where filter, but we're being defensive)
                if (pkValue == null) continue;
                
                string partitionKey = pkValue; // Create a local non-nullable copy for the lambda
                queryTasks.Add(Task.Run(async () =>
                {
                    try
                    {
                        QueryRequestOptions queryOptions = new QueryRequestOptions() { PartitionKey = new PartitionKey(partitionKey) };
                        var count = await _container.GetItemLinqQueryable<DataTypes.DataItem>(requestOptions: queryOptions)
                                                     .Where(i => i[partitionKeyName].ToString() == partitionKey)
                                                     .CountAsync(cancellationToken);
                        return (long)count;
                    }
                    catch (CosmosException ex)
                    {
                        _logger.LogWarning(ex, "[DEBUG] Error querying count for partition key '{PK}'. Status: {Status}", partitionKey, ex.StatusCode);
                        return 0L;
                    }
                    catch (Exception ex)
                    {
                        _logger.LogError(ex, "[DEBUG] Non-Cosmos error querying count for partition key '{PK}'", partitionKey);
                        return 0L;
                    }
                }, cancellationToken));
            }

            var counts = await Task.WhenAll(queryTasks);
            totalCount = counts.Sum();

            return totalCount;
        }

        public async Task<int> GetContainerItemCountAsync()
        {
            if (_container == null)
            {
                _logger.LogWarning("Cannot get item count, container not initialized.");
                return -1;
            }

            try
            {
                int count = await _container.GetItemLinqQueryable<object>().CountAsync();
                _logger.LogInformation("Current approximate item count in container: {Count}", count);
                return count;
            }
            catch (CosmosException ex)
            {
                _logger.LogError(ex, "Failed to get item count from container. Status Code: {StatusCode}", ex.StatusCode);
                return -1;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Unexpected error occurred while getting item count.");
                return -1;
            }
        }

        public Task<long> GetTotalRequestUnitsAsync()
        {
            return Task.FromResult(_totalRequestUnits);
        }
    }
}