using System;
using System.Collections.Generic;
using System.Globalization;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using System.Runtime.CompilerServices;

namespace CosmosUploader.Processors
{
    // Define a placeholder data type - replace with your actual data model
    using DataItem = System.Collections.Generic.Dictionary<string, object>; 

    public interface ISchemaProcessor
    {
        // Return IEnumerable for streaming potential
        Task<IEnumerable<DataItem>> ProcessAsync(IEnumerable<DataItem> rawData, CancellationToken cancellationToken);
        // Add an async streaming interface method
        IAsyncEnumerable<DataItem> ProcessStreamAsync(IEnumerable<DataItem> rawData, CancellationToken cancellationToken);
    }

    public class SchemaProcessor : ISchemaProcessor
    {
        private readonly ILogger<SchemaProcessor> _logger;
        // Define required keys for basic validation
        private readonly List<string> _requiredKeys = new List<string> { "id", "sensor_id", "timestamp", "temperature" };

        public SchemaProcessor(ILogger<SchemaProcessor> logger)
        {
            _logger = logger;
        }

        // Keep the original method for compatibility if needed, but delegate to streaming
        public async Task<IEnumerable<DataItem>> ProcessAsync(IEnumerable<DataItem> rawData, CancellationToken cancellationToken)
        {
             _logger.LogInformation("--- Starting Schematization (buffered) ---");
            var results = new List<DataItem>();
            await foreach (var item in ProcessStreamAsync(rawData, cancellationToken).WithCancellation(cancellationToken))
            {
                results.Add(item);
            }
             _logger.LogInformation("--- Finished Schematization (buffered, Output: {Count} items) ---", results.Count);
            return results;
        }
        
        // Implement the streaming method using async iterator
        public async IAsyncEnumerable<DataItem> ProcessStreamAsync(IEnumerable<DataItem> rawData,
                                                                   [EnumeratorCancellation] CancellationToken cancellationToken)
        {
             _logger.LogInformation("--- Starting Schematization (streaming) ---");
            int inputCount = 0;
            int invalidCount = 0;
            int outputCount = 0;

            foreach(var item in rawData) // Keep iterating input enumerable
            {
                 // Check cancellation frequently within the loop
                 cancellationToken.ThrowIfCancellationRequested(); 
                 inputCount++;
                 
                 bool isValid = true;
                 foreach (var key in _requiredKeys)
                 {
                     if (!item.ContainsKey(key) || item[key] == null)
                     {
                         // Avoid serializing full item in logs for performance
                         _logger.LogWarning("Item missing required key '{Key}' or value is null. Skipping item ID: {ItemId}", key, item.GetValueOrDefault("id", "[unknown_id]"));
                         isValid = false;
                         break;
                     }
                 }

                 if (!isValid) {
                     invalidCount++;
                     continue; // Skip to next item
                 }

                 // Create a *copy* if modifying, or modify in place if safe for the caller
                 // Let's modify in place for this example, assuming the dictionary won't be reused unexpectedly elsewhere
                 var processedItem = item; // Modify in place

                 if (processedItem.TryGetValue("temperature", out object? tempValue) && tempValue != null) { 
                    if (!(tempValue is double)) {
                        if (double.TryParse(tempValue.ToString(), NumberStyles.Any, CultureInfo.InvariantCulture, out double tempDouble)) {
                            processedItem["temperature"] = tempDouble;
                        } else {
                             _logger.LogWarning("Could not convert temperature '{Value}' to double for item id {Id}. Setting to null.", tempValue, processedItem["id"]);
                             processedItem["temperature"] = null; 
                        }
                    }
                 } else { 
                     processedItem["temperature"] = null; 
                 }

                 processedItem["processed_stage"] = ProcessingStage.Schematized.ToString();
                 
                 outputCount++;
                 yield return processedItem; // Yield the processed item
            }
            
            // Log summary after the loop finishes
            if (invalidCount > 0) { _logger.LogWarning("Schematization skipped {InvalidCount} invalid items.", invalidCount); }
            _logger.LogInformation("--- Finished Schematization (streaming, Input: {InputCount}, Output: {OutputCount} items) ---", inputCount, outputCount);
             // No explicit return needed for IAsyncEnumerable method body itself
             await Task.CompletedTask; // Required if there are no awaits inside the async iterator method
        }
    }
} 