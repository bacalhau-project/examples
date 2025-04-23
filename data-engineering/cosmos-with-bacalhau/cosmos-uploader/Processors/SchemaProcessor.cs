using System;
using System.Collections.Generic;
using System.Globalization;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;

namespace CosmosUploader.Processors
{
    // Define a placeholder data type - replace with your actual data model
    using DataItem = System.Collections.Generic.Dictionary<string, object>; 

    public interface ISchemaProcessor
    {
        Task<IEnumerable<DataItem>> ProcessAsync(IEnumerable<DataItem> rawData, CancellationToken cancellationToken);
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

        public Task<IEnumerable<DataItem>> ProcessAsync(IEnumerable<DataItem> rawData, CancellationToken cancellationToken)
        {
            _logger.LogInformation("--- Starting Schematization ---");
            
            var processedData = new List<DataItem>();
            int inputCount = 0;
            int invalidCount = 0;

            foreach(var item in rawData)
            {
                 cancellationToken.ThrowIfCancellationRequested();
                 inputCount++;
                 
                 // 1. Validate required keys
                 bool isValid = true;
                 foreach (var key in _requiredKeys)
                 {
                     if (!item.ContainsKey(key) || item[key] == null)
                     {
                         _logger.LogWarning("Item missing required key '{Key}' or value is null. Skipping item. Data: {ItemData}", key, JsonSerializer.Serialize(item));
                         isValid = false;
                         break;
                     }
                 }

                 if (!isValid) {
                     invalidCount++;
                     continue; // Skip to next item
                 }

                 // 2. Example Transformation: Ensure temperature is a double
                 if (item.TryGetValue("temperature", out object? tempValue) && tempValue != null)
                 { 
                    if (!(tempValue is double)) {
                        if (double.TryParse(tempValue.ToString(), NumberStyles.Any, CultureInfo.InvariantCulture, out double tempDouble))
                        {
                            item["temperature"] = tempDouble;
                             _logger.LogTrace("Converted temperature '{OriginalValue}' to double {ConvertedValue}", tempValue, tempDouble);
                        }
                        else
                        {
                             _logger.LogWarning("Could not convert temperature '{Value}' to double for item id {Id}. Setting to null.", tempValue, item["id"]);
                             item["temperature"] = null; // Or handle error differently
                        }
                    }
                 } else {
                     // Temperature was already null or key didn't exist (handled by required key check)
                     item["temperature"] = null; 
                 }

                // 3. Add/Update stage marker
                 item["processed_stage"] = ProcessingStage.Schematized.ToString();
                 processedData.Add(item);
            }

            if (invalidCount > 0) {
                 _logger.LogWarning("Schematization skipped {InvalidCount} invalid items due to missing required keys.", invalidCount);
            }
            _logger.LogInformation("--- Finished Schematization (Input: {InputCount}, Output: {OutputCount} items) ---", inputCount, processedData.Count);
            return Task.FromResult<IEnumerable<DataItem>>(processedData);
        }
    }
} 