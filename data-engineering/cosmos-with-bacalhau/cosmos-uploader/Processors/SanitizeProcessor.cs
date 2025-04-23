using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;

namespace CosmosUploader.Processors
{
    // Using the same placeholder data type defined in SchemaProcessor.cs
    using DataItem = System.Collections.Generic.Dictionary<string, object>; 

    public interface ISanitizeProcessor
    {
        Task<IEnumerable<DataItem>> ProcessAsync(IEnumerable<DataItem> schematizedData, CancellationToken cancellationToken);
    }

    public class SanitizeProcessor : ISanitizeProcessor
    {
        private readonly ILogger<SanitizeProcessor> _logger;

        public SanitizeProcessor(ILogger<SanitizeProcessor> logger)
        {
            _logger = logger;
        }

        public Task<IEnumerable<DataItem>> ProcessAsync(IEnumerable<DataItem> schematizedData, CancellationToken cancellationToken)
        {
            _logger.LogInformation("--- Starting Sanitization ---");

            // TODO: Implement more robust PII masking/stripping logic based on actual needs.
            // Example: Use regex for emails, SSNs, etc. Check configuration for fields to sanitize.

            var processedData = new List<DataItem>();
            int count = 0;
            int maskedCount = 0;
            string keyToMask = "sensor_id"; // Example PII field

            foreach(var item in schematizedData)
            {
                 cancellationToken.ThrowIfCancellationRequested();
                 count++;

                 // Example Masking: Mask the sensor_id
                 if (item.TryGetValue(keyToMask, out object? sensorIdValue) && sensorIdValue != null)
                 {
                     string originalId = sensorIdValue.ToString() ?? string.Empty;
                     if (!string.IsNullOrEmpty(originalId)) 
                     {
                        string maskedId = originalId.Length > 3 ? originalId.Substring(0, 3) + "***" : "***";
                        item[keyToMask] = maskedId;
                        _logger.LogTrace("Masked {Key} for item id {ItemId}: '{OriginalValue}' -> '{MaskedValue}'", 
                            keyToMask, item.GetValueOrDefault("id", "[unknown_id]"), originalId, maskedId);
                        maskedCount++;
                     }
                     else {
                          _logger.LogTrace("Sensor ID was null or empty for item id {ItemId}. Skipping masking.", item.GetValueOrDefault("id", "[unknown_id]"));
                     }
                 }
                 else {
                     _logger.LogTrace("Item id {ItemId} does not contain key '{Key}' for masking.", item.GetValueOrDefault("id", "[unknown_id]"), keyToMask);
                 }

                 // Update stage marker
                 item["processed_stage"] = ProcessingStage.Sanitized.ToString(); 
                 processedData.Add(item);
            }

            _logger.LogInformation("--- Finished Sanitization (Processed: {Count} items, Masked '{Key}' for {MaskedCount} items) ---", 
                count, keyToMask, maskedCount);
            return Task.FromResult<IEnumerable<DataItem>>(processedData);
        }
    }
} 