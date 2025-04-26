using System;
using System.Collections.Generic;
using System.Globalization;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using System.Runtime.CompilerServices;
using System.Text.Json;
using CosmosUploader.Models;

namespace CosmosUploader.Processors
{
    public class SchemaProcessor : BaseProcessor, ISchemaProcessor
    {
        private readonly ProcessingStage _processingStage;
        
        // Define required keys for basic validation
        private readonly HashSet<string> _commonRawFields = new HashSet<string>()
        {
            "id", "sensorId", "timestamp", "location", "processingStage"
        };

        public SchemaProcessor(ILogger<SchemaProcessor> logger)
            : base(logger, "SchemaProcessor", ProcessingStage.Schematized)
        {
            _processingStage = ProcessingStage.Schematized;
        }

        public async Task<IEnumerable<DataTypes.DataItem>> ProcessAsync(
            IEnumerable<DataTypes.DataItem> data,
            CancellationToken cancellationToken)
        {
            _logger.LogInformation("--- Starting Schematization (buffered) ---");
            var results = new List<DataTypes.DataItem>();
            await foreach (var item in ProcessStreamAsync(data, cancellationToken).WithCancellation(cancellationToken))
            {
                results.Add(item);
            }
            _logger.LogInformation("--- Finished Schematization (buffered, Output: {Count} items) ---", results.Count);
            return results;
        }
        
        public async IAsyncEnumerable<DataTypes.DataItem> ProcessStreamAsync(IEnumerable<DataTypes.DataItem> rawData,
                                                                   [EnumeratorCancellation] CancellationToken cancellationToken)
        {
             _logger.LogInformation("--- Starting Schematization (streaming) ---");
            int inputCount = 0;
            int invalidCount = 0;
            int fixedCount = 0;
            int outputCount = 0;

            foreach(var item in rawData) // Keep iterating input enumerable
            {
                 // Check cancellation frequently within the loop
                 cancellationToken.ThrowIfCancellationRequested(); 
                 inputCount++;
                 
                 // Clone the item to avoid modifying the original
                 var processedItem = new DataTypes.DataItem(item);
                 
                 // Check and enforce required fields
                 foreach (var key in _commonRawFields)
                 {
                     if (!processedItem.ContainsKey(key) || processedItem[key] == null)
                     {
                         // Try to fix by adding default values
                         switch (key)
                         {
                             case "id":
                                 processedItem["id"] = Guid.NewGuid().ToString();
                                 break;
                             case "timestamp":
                                 processedItem["timestamp"] = DateTime.UtcNow;
                                 break;
                             case "location":
                                 processedItem[key] = "unknown";
                                 break;
                             default:
                                 processedItem[key] = string.Empty;
                                 break;
                         }
                         
                         fixedCount++;
                         _logger.LogWarning("Item missing required key '{Key}'. Added default value. Item ID: {ItemId}", 
                             key, processedItem["id"]);
                     }
                 }
                 
                 // Ensure all numeric fields are proper types (doubles, etc.)
                 EnsureProperNumericTypes(processedItem);
                 
                 // For Raw to Schematized transition, handle raw data string
                 if (processedItem.ContainsKey("rawDataString") && processedItem["rawDataString"] is string rawJson)
                 {
                     try
                     {
                         // Parse any additional data from the raw string if needed
                         var rawDict = JsonSerializer.Deserialize<Dictionary<string, object>>(rawJson);
                         if (rawDict != null)
                         {
                             // Extract any missing fields from raw data if they exist there
                             foreach (var kvp in rawDict)
                             {
                                 if (!processedItem.ContainsKey(kvp.Key) || processedItem[kvp.Key] == null)
                                 {
                                     processedItem[kvp.Key] = kvp.Value;
                                 }
                             }
                         }
                     }
                     catch (Exception ex)
                     {
                         _logger.LogWarning(ex, "Failed to parse rawDataString for item {Id}", processedItem["id"]);
                     }
                 }
                 
                 // Set the processing stage to Schematized
                 processedItem["processingStage"] = _processingStage.ToString();
                 
                 outputCount++;
                 yield return processedItem; // Yield the processed item
            }
            
            // Log summary after the loop finishes
            if (invalidCount > 0) { _logger.LogWarning("Schematization found {InvalidCount} invalid items.", invalidCount); }
            if (fixedCount > 0) { _logger.LogInformation("Schematization fixed {FixedCount} items with missing fields.", fixedCount); }
            
            _logger.LogInformation("--- Finished Schematization (streaming, Input: {InputCount}, Output: {OutputCount} items) ---", 
                inputCount, outputCount);
                
            // No explicit return needed for IAsyncEnumerable method body itself
            await Task.CompletedTask; // Required if there are no awaits inside the async iterator method
        }
        
        private void EnsureProperNumericTypes(DataTypes.DataItem item)
        {
            // Process numeric fields to ensure they're the right type
            string[] numericFields = new[] { "temperature", "vibration", "voltage", "humidity" };
            
            foreach (var field in numericFields)
            {
                if (item.TryGetValue(field, out object? value) && value != null)
                {
                    if (!(value is double))
                    {
                        if (double.TryParse(value.ToString(), NumberStyles.Any, CultureInfo.InvariantCulture, out double numericValue))
                        {
                            item[field] = numericValue;
                        }
                        else
                        {
                            _logger.LogWarning("Could not convert {Field} value '{Value}' to double for item id {Id}. Setting to null.", 
                                field, value, item["id"]);
                            item[field] = 0.0; // Default to 0.0 instead of null
                        }
                    }
                }
            }
            
            // Ensure boolean fields are proper booleans
            if (item.TryGetValue("anomalyFlag", out object? flagValue) && flagValue != null)
            {
                if (!(flagValue is bool))
                {
                    if (bool.TryParse(flagValue.ToString(), out bool boolValue))
                    {
                        item["anomalyFlag"] = boolValue;
                    }
                    else
                    {
                        // Try numeric conversion (0=false, non-zero=true)
                        if (int.TryParse(flagValue.ToString(), out int intValue))
                        {
                            item["anomalyFlag"] = intValue != 0;
                        }
                        else
                        {
                            _logger.LogWarning("Could not convert anomalyFlag value '{Value}' to boolean for item id {Id}. Setting to false.", 
                                flagValue, item["id"]);
                            item["anomalyFlag"] = false;
                        }
                    }
                }
            }
            else
            {
                // Default value if not present
                item["anomalyFlag"] = false;
            }
        }
    }
} 