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
using System.Text.Json;

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
                    _logger.LogDebug("DEBUG: Target Cosmos Endpoint: {Endpoint}", _settings.Cosmos?.Endpoint ?? "undefined");

                    try
                    {
                        if (!string.IsNullOrEmpty(_settings.Cosmos?.Endpoint))
                        {
                            Uri endpointUri = new Uri(_settings.Cosmos.Endpoint);
                            _logger.LogDebug("DEBUG: Attempting DNS lookup for host: {Host}", endpointUri.Host);
                            IPHostEntry entry = await Dns.GetHostEntryAsync(endpointUri.Host);
                            _logger.LogDebug("DEBUG: DNS resolved host {Host} to {IPCount} IP addresses. First IP: {IPAddress}",
                                endpointUri.Host, entry.AddressList.Length, entry.AddressList.FirstOrDefault()?.ToString() ?? "N/A");
                        }
                        else
                        {
                            _logger.LogWarning("DEBUG: Cosmos endpoint is not configured - cannot perform DNS lookup");
                        }
                    }
                    catch (Exception netEx)
                    {
                         _logger.LogWarning(netEx, "DEBUG: Network diagnostic check (DNS/Ping) failed for {Host}.", 
                             !string.IsNullOrEmpty(_settings.Cosmos?.Endpoint) ? new Uri(_settings.Cosmos.Endpoint).Host : "unknown host");
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
                    _settings.Cosmos?.Endpoint ?? "undefined", clientOptions.ConnectionMode);
                
                if (string.IsNullOrEmpty(_settings.Cosmos?.Endpoint) || string.IsNullOrEmpty(_settings.Cosmos?.Key))
                {
                    _logger.LogError("Missing required Cosmos DB settings: Endpoint or Key");
                    throw new InvalidOperationException("Cosmos DB settings incomplete: Endpoint and Key are required");
                }

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
            string processingStage = _settings.ProcessingStage.ToString();
            _logger.LogInformation("Starting bulk upload of {Count} {Stage} items...", totalCount, processingStage);
            
            // Display helpful message if using Raw stage
            if (processingStage == "Raw")
            {
                _logger.LogInformation("Processing in 'Raw' stage which requires 'rawDataString' field. " + 
                    "If you have issues, consider using 'Schematized' stage in your config.yaml: " +
                    "Processing.Schematize: true, Processing.Sanitize: false, Processing.Aggregate: false");
            }

            var stopwatch = Stopwatch.StartNew();
            double operationRequestUnits = 0;
            int totalUploaded = 0;
            int totalFailed = 0;
            int totalConflicts = 0;
            int totalSkipped = 0;

            // Ensure all items have required fields according to schema
            var validatedItems = new List<DataItem>();
            foreach (var item in data)
            {
                // Ensure processing stage is set
                if (!item.ContainsKey("processingStage") || item["processingStage"] == null || string.IsNullOrWhiteSpace(item["processingStage"].ToString()))
                {
                    _logger.LogWarning("Item missing 'processingStage' field. Setting to configured value: {Stage}", processingStage);
                    item["processingStage"] = processingStage;
                }

                // Get the actual processing stage of this item
                string itemStage = item["processingStage"]?.ToString() ?? string.Empty;
                
                // Check if item has city but no location, and if so, copy city to location
                if ((!item.ContainsKey("location") || item["location"] == null || string.IsNullOrWhiteSpace(item["location"].ToString())) && 
                     item.ContainsKey("city") && item["city"] != null && !string.IsNullOrWhiteSpace(item["city"].ToString()))
                {
                    _logger.LogDebug("Item ID {ItemId} has 'city' field but no 'location'. Copying city value to location for partition key.", 
                        item.GetValueOrDefault("id", "[unknown_id]"));
                    item["location"] = item["city"];
                }
                
                // Validate and fix any missing fields
                if (!ValidateItemFields(item, itemStage))
                {
                    _logger.LogError("Item failed validation and cannot be processed. Skipping item.");
                    totalSkipped++;
                    continue;
                }

                validatedItems.Add(item);
            }

            // DEBUGGING: Try single item upload mode when in debug mode to identify problematic documents
            if (_settings.DebugMode && validatedItems.Count > 0)
            {
                _logger.LogWarning("DEBUG MODE: Attempting to upload first item individually to diagnose issues");
                
                // Get the first item and try to upload it
                var firstItem = validatedItems.First();
                string itemId = firstItem.GetValueOrDefault("id", "[unknown_id]")?.ToString() ?? "[unknown_id]";
                
                _logger.LogDebug("Attempting individual upload of item ID: {ItemId}", itemId);
                
                try
                {
                    // Create a simplified version for testing
                    var simplifiedItem = new Dictionary<string, object>
                    {
                        ["id"] = itemId,
                        ["processingStage"] = firstItem["processingStage"],
                        ["location"] = firstItem["location"] // Partition key field
                    };
                    
                    // Try adding a few basic fields
                    if (firstItem.ContainsKey("timestamp"))
                        simplifiedItem["timestamp"] = firstItem["timestamp"];
                    
                    // Try to get the partition key
                    string testPartitionKeyField = "location";
                    string partitionKeyValue = simplifiedItem[testPartitionKeyField]?.ToString() ?? "unknown";
                                            
                    // Try uploading just the simplified version first
                    try
                    {
                        var response = await _container.CreateItemAsync<Dictionary<string, object>>(
                            simplifiedItem,
                            new PartitionKey(partitionKeyValue),
                            cancellationToken: cancellationToken);
                            
                        _logger.LogInformation("SUCCESS: Simplified document uploaded successfully!");
                        
                        // Now try to identify which fields might be causing problems by adding them one at a time
                        _logger.LogInformation("Field-by-field analysis started for document {ItemId}", itemId);
                        
                        // Delete the simplified document we just created
                        await _container.DeleteItemAsync<Dictionary<string, object>>(
                            itemId,
                            new PartitionKey(partitionKeyValue),
                            cancellationToken: cancellationToken);
                            
                        // Try the original document to see what happens
                        try
                        {
                            var fullResponse = await _container.CreateItemAsync<Dictionary<string, object>>(
                                firstItem,
                                new PartitionKey(partitionKeyValue),
                                cancellationToken: cancellationToken);
                                
                            _logger.LogInformation("SUCCESS: Original document uploaded successfully too! Problem may be with batching.");
                        }
                        catch (CosmosException ce)
                        {
                            _logger.LogError("FAILED: Original document upload failed with error: {Error}", ce.Message);
                            _logger.LogWarning("This suggests the document structure is problematic. Examining document:");
                            
                            // Log problematic fields
                            foreach (var kvp in firstItem)
                            {
                                object? value = kvp.Value;
                                
                                try
                                {
                                    if (value == null)
                                    {
                                        _logger.LogDebug("Field {Field}: null", kvp.Key);
                                    }
                                    else
                                    {
                                        var valueType = value.GetType().Name;
                                        string valueString;
                                        
                                        if (value is string str)
                                            valueString = str.Length > 50 ? $"{str.Substring(0, 47)}..." : str;
                                        else
                                            valueString = value.ToString() ?? "null";
                                            
                                        _logger.LogDebug("Field {Field}: [{Type}] {Value}", 
                                            kvp.Key, valueType, valueString);
                                    }
                                }
                                catch (Exception ex)
                                {
                                    _logger.LogWarning("Error examining field {Field}: {Error}", kvp.Key, ex.Message);
                                }
                            }
                        }
                    }
                    catch (Exception ex)
                    {
                        _logger.LogError("Even simplified document failed: {Error}", ex.Message);
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogError("Error during diagnostic upload: {ErrorMessage}", ex.Message);
                }
                
                _logger.LogWarning("DEBUG DIAGNOSTICS COMPLETE - continuing with normal operation");
            }

            // Update task list type to match the actual nullability of the return values
            var concurrentTasks = new List<Task<(ItemResponse<object>? Response, bool Success, bool IsConflict)>>();
            // Always use "location" as the partition key field, regardless of configuration
            string partitionKeyField = "location";
            
            // Log the partition key field being used
            _logger.LogInformation("Using '{PartitionKeyField}' as the partition key field (container configured with {ConfiguredKey})", 
                partitionKeyField, _settings.Cosmos?.PartitionKey ?? "/id");

            foreach (var item in validatedItems)
            {
                if (cancellationToken.IsCancellationRequested)
                {
                    _logger.LogWarning("Upload cancelled by user during task creation");
                    break;
                }

                // Check location exists and has a value (location should never be null)
                if (!item.TryGetValue(partitionKeyField, out var partitionKeyValue) || 
                    partitionKeyValue == null || 
                    string.IsNullOrWhiteSpace(partitionKeyValue?.ToString()))
                {
                     _logger.LogError("Item with ID {ItemId} is missing the partition key field '{PartitionKeyField}' or its value is null/empty. Skipping upload.", 
                        item.GetValueOrDefault("id", "[unknown_id]"), 
                        partitionKeyField);
                     totalFailed++;
                     continue;
                }

                // Get the string value safely
                string partitionKeyString = partitionKeyValue?.ToString() ?? string.Empty;
                
                if (string.IsNullOrWhiteSpace(partitionKeyString))
                {
                    _logger.LogError("Item with ID {ItemId} has a null or empty partition key after conversion to string", 
                        item.GetValueOrDefault("id", "[unknown_id]"));
                    totalFailed++;
                    continue;
                }
                
                // Debug log the item content to see what might be causing the BadRequest
                if (_settings.DebugMode)
                {
                    try 
                    {
                        // Check document size - Cosmos DB has a 2MB limit
                        string jsonContent = System.Text.Json.JsonSerializer.Serialize(item);
                        int documentSizeKB = System.Text.Encoding.UTF8.GetByteCount(jsonContent) / 1024;
                        
                        if (documentSizeKB > 1900) // Getting close to 2MB limit
                        {
                            _logger.LogWarning("Document ID {ItemId} is {SizeKB}KB, approaching Cosmos DB 2MB limit", 
                                item.GetValueOrDefault("id", "[unknown_id]"), documentSizeKB);
                        }
                        
                        // Only log full content for small documents
                        if (documentSizeKB < 10)
                        {
                            _logger.LogDebug("Attempting to upload document with ID {ItemId}. Content: {Content}", 
                                item.GetValueOrDefault("id", "[unknown_id]"), 
                                System.Text.Json.JsonSerializer.Serialize(item, new System.Text.Json.JsonSerializerOptions { WriteIndented = true }));
                        }
                        else
                        {
                            // For large documents, just log the keys and their types
                            var fieldInfo = string.Join(", ", item.Select(kvp => $"{kvp.Key}:[{kvp.Value?.GetType().Name ?? "null"}]"));
                            _logger.LogDebug("Document ID {ItemId} - Size: {SizeKB}KB - Fields: {Fields}", 
                                item.GetValueOrDefault("id", "[unknown_id]"), documentSizeKB, fieldInfo);
                        }
                    }
                    catch (Exception jsonEx)
                    {
                        _logger.LogWarning("Unable to serialize document to JSON for debug output. This may indicate the issue: {ErrorMessage}", 
                            jsonEx.Message);
                    }
                }
                
                concurrentTasks.Add(
                    // Use generic object type for CreateItemAsync
                    _container.CreateItemAsync<object>(
                        item, 
                        new PartitionKey(partitionKeyString), // Use the validated string 
                        cancellationToken: cancellationToken)
                    .ContinueWith<(ItemResponse<object>? Response, bool Success, bool IsConflict)>(task =>
                    {
                        cancellationToken.ThrowIfCancellationRequested(); // Check before processing result
                        if (task.IsCompletedSuccessfully)
                        {
                            return (task.Result, true, false);
                        }
                        if (task.IsFaulted)
                        {
                            if (task.Exception?.InnerException is CosmosException cosmosEx)
                            {
                                if (cosmosEx.StatusCode == HttpStatusCode.Conflict)
                                {
                                    // Treat conflict as a separate category, not necessarily a hard failure
                                    return (null, false, true);
                                }
                                else if (cosmosEx.StatusCode == HttpStatusCode.BadRequest)
                                {
                                    // Add enhanced error logging for BadRequest errors
                                    _logger.LogError("BadRequest error for item ID {ItemId}. SubStatusCode: {SubStatusCode}, ActivityId: {ActivityId}. " +
                                        "Diagnostics: {Diagnostics}", 
                                        item.GetValueOrDefault("id", "[unknown_id]"),
                                        cosmosEx.SubStatusCode,
                                        cosmosEx.ActivityId,
                                        cosmosEx.Diagnostics?.ToString() ?? "No diagnostic info");
                                        
                                    // Try to dump data properties that might be problematic
                                    try
                                    {
                                        var problematicKeys = new List<string>();
                                        foreach (var kvp in item)
                                        {
                                            if (kvp.Value == null)
                                                problematicKeys.Add($"{kvp.Key}: null");
                                            else if (kvp.Value is string str && string.IsNullOrEmpty(str))
                                                problematicKeys.Add($"{kvp.Key}: empty string");
                                            else if (Double.IsNaN(kvp.Value as double? ?? 0))
                                                problematicKeys.Add($"{kvp.Key}: NaN");
                                            else if (Double.IsInfinity(kvp.Value as double? ?? 0))
                                                problematicKeys.Add($"{kvp.Key}: Infinity");
                                        }
                                        
                                        if (problematicKeys.Count > 0)
                                            _logger.LogWarning("Found potentially problematic properties: {Properties}", 
                                                string.Join(", ", problematicKeys));
                                    }
                                    catch (Exception ex)
                                    {
                                        _logger.LogWarning("Error analyzing document properties: {ErrorMessage}", ex.Message);
                                    }
                                }
                                
                                // Log other exceptions
                                _logger.LogError(task.Exception, "Bulk upload task failed for item ID {ItemId}: {ErrorMessage} (Status: {Status}, SubStatus: {SubStatus})", 
                                    item.GetValueOrDefault("id", "[unknown_id]"), 
                                    task.Exception?.InnerException?.Message ?? task.Exception?.Message ?? "Unknown error",
                                    cosmosEx.StatusCode,
                                    cosmosEx.SubStatusCode);
                            }
                            else
                            {
                                // For non-Cosmos exceptions
                                _logger.LogError(task.Exception, "Bulk upload task failed for item ID {ItemId}: {ErrorMessage}", 
                                    item.GetValueOrDefault("id", "[unknown_id]"), 
                                    task.Exception?.InnerException?.Message ?? task.Exception?.Message ?? "Unknown error");
                            }
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
                    if (_settings.Logging?.LogLatency == true)
                    {
                        _logger.LogTrace("Uploaded item {Id} - RU: {RequestCharge}, Latency: {Latency}", 
                            response.Resource?.GetType().GetProperty("id")?.GetValue(response.Resource) ?? "unknown", // Try to get ID from response if possible
                            response.RequestCharge, 
                            response.Diagnostics?.GetClientElapsedTime() ?? TimeSpan.Zero); 
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
            if (totalSkipped > 0)
            {
                _logger.LogWarning("Bulk upload skipped {Skipped} items due to validation failures.", totalSkipped);
            }

            _logger.LogInformation(
                "Bulk upload of {ProcessingStage} data finished in {ElapsedSeconds:F2} seconds. Uploaded: {Uploaded}, Conflicts: {Conflicts}, Failed: {Failures}, Skipped: {Skipped}, Total RUs: {RequestUnits:F2}",
                processingStage,
                stopwatch.Elapsed.TotalSeconds,
                totalUploaded,
                totalConflicts,
                totalFailed,
                totalSkipped,
                operationRequestUnits);
            
            // Decide if failure count warrants throwing an exception to halt processing
            if (totalFailed > 0 && totalFailed == validatedItems.Count) // Only throw if all attempted uploads failed
            {
                 throw new Exception($"Bulk upload failed for all {totalFailed} attempted items. See logs for details.");
            }
        }

        // Helper method to validate item fields based on processing stage
        private bool ValidateItemFields(DataItem item, string stage)
        {
            // Check if the stage is valid (using string comparison)
            if (stage != "Raw" && stage != "Schematized" && 
                stage != "Sanitized" && stage != "Aggregated")
            {
                _logger.LogWarning("Invalid processing stage '{Stage}' for item ID {ItemId}", 
                    stage, item.GetValueOrDefault("id", "[unknown_id]"));
                return false;
            }

            // Get required fields for this stage based on the stage string
            HashSet<string> requiredFields;
            if (stage == "Raw")
            {
                requiredFields = new HashSet<string> { "id", "sensorId", "timestamp", "location", "processingStage", "rawDataString" };
            }
            else if (stage == "Schematized" || stage == "Sanitized")
            {
                requiredFields = new HashSet<string> { 
                    "id", "sensorId", "timestamp", "location", "processingStage",
                    "temperature", "vibration", "voltage", "humidity", "status",
                    "anomalyFlag", "anomalyType", "firmwareVersion", "model", "manufacturer",
                    "lat", "long"
                };
            }
            else if (stage == "Aggregated")
            {
                requiredFields = new HashSet<string> { 
                    "id", "sensorId", "timestamp", "location", "processingStage",
                    "temperature", "vibration", "voltage", "humidity", "status",
                    "anomalyFlag", "anomalyType", "firmwareVersion", "model", "manufacturer",
                    "aggregationWindowStart", "aggregationWindowEnd"
                };
            }
            else
            {
                // Should not get here due to earlier check
                requiredFields = new HashSet<string> { "id", "processingStage" };
            }
            
            // Check if all required fields are present
            bool isValid = true;
            List<string> missingFields = new List<string>();
            
            foreach (var field in requiredFields)
            {
                if (!item.ContainsKey(field) || item[field] == null || 
                    (item[field] is string strVal && string.IsNullOrWhiteSpace(strVal)))
                {
                    missingFields.Add(field);
                    isValid = false;
                }
            }
            
            if (!isValid)
            {
                string itemId = item.GetValueOrDefault("id", "[unknown_id]")?.ToString() ?? "[unknown_id]";
                _logger.LogWarning("Item ID {ItemId} missing required fields for processing stage '{Stage}': {MissingFields}", 
                    itemId, stage, string.Join(", ", missingFields));
                
                // Automatically add missing fields with default values where possible
                foreach (var field in missingFields)
                {
                    switch (field)
                    {
                        case "id":
                            item["id"] = Guid.NewGuid().ToString();
                            _logger.LogDebug("Generated new ID {Id} for item", item["id"]);
                            break;
                        case "processingStage":
                            item["processingStage"] = stage; // Use the provided stage
                            break;
                        case "timestamp":
                            item["timestamp"] = DateTime.UtcNow;
                            break;
                        case "location":
                            // Location is used as partition key and cannot be null
                            item["location"] = "unknown_location";
                            _logger.LogWarning("Added required partition key field 'location' with default value for item ID {ItemId}", 
                                item.GetValueOrDefault("id", "[unknown_id]"));
                            break;
                        case "rawDataString":
                            // For Raw stage, provide an empty JSON object as default rawDataString
                            item["rawDataString"] = "{}";
                            _logger.LogDebug("Added default rawDataString value for item ID {ItemId}", 
                                item.GetValueOrDefault("id", "[unknown_id]"));
                            break;
                        case "anomalyFlag":
                            item["anomalyFlag"] = false; // Default to no anomaly
                            break;
                        default:
                            // For other fields, add a placeholder/empty value
                            if (field.EndsWith("WindowStart") || field.EndsWith("WindowEnd"))
                                item[field] = DateTime.UtcNow; // Default date for window fields
                            else if (field == "temperature" || field == "vibration" || field == "voltage" || field == "humidity")
                                item[field] = 0.0; // Default numeric value for sensor readings
                            else
                                item[field] = ""; // Empty string for other fields
                            break;
                    }
                    _logger.LogDebug("Added default value for missing field {Field} to item ID {ItemId}", field, item["id"]);
                }
            }
            
            // After fixing missing fields, check special field requirements
            if (stage == "Aggregated")
            {
                // Ensure timestamp matches aggregationWindowEnd for Aggregated data
                if (item.ContainsKey("timestamp") && item.ContainsKey("aggregationWindowEnd") &&
                    item["timestamp"] != item["aggregationWindowEnd"])
                {
                    _logger.LogWarning("For Aggregated data, 'timestamp' should match 'aggregationWindowEnd'. Fixing.");
                    item["timestamp"] = item["aggregationWindowEnd"];
                }
            }
            
            return true; // Return true since we attempt to fix all issues
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