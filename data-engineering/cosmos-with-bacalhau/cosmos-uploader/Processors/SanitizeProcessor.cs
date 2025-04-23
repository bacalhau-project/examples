using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using System.Runtime.CompilerServices;

namespace CosmosUploader.Processors
{
    // Using the same placeholder data type defined in SchemaProcessor.cs
    using DataItem = System.Collections.Generic.Dictionary<string, object>; 

    public interface ISanitizeProcessor
    {
        Task<IEnumerable<DataItem>> ProcessAsync(IEnumerable<DataItem> schematizedData, CancellationToken cancellationToken);
        IAsyncEnumerable<DataItem> ProcessStreamAsync(IEnumerable<DataItem> schematizedData, CancellationToken cancellationToken);
    }

    public class SanitizeProcessor : ISanitizeProcessor
    {
        private readonly ILogger<SanitizeProcessor> _logger;

        public SanitizeProcessor(ILogger<SanitizeProcessor> logger)
        {
            _logger = logger;
        }

        public async Task<IEnumerable<DataItem>> ProcessAsync(IEnumerable<DataItem> schematizedData, CancellationToken cancellationToken)
        {
            _logger.LogDebug("--- Starting Sanitization (buffered wrapper) ---");
            var results = new List<DataItem>();
            await foreach (var item in ProcessStreamAsync(schematizedData, cancellationToken).WithCancellation(cancellationToken).ConfigureAwait(false))
            {
                results.Add(item);
            }
            _logger.LogDebug("--- Finished Sanitization (buffered wrapper, Output: {Count} items) ---", results.Count);
            return results;
        }

        public async IAsyncEnumerable<DataItem> ProcessStreamAsync(IEnumerable<DataItem> schematizedData, 
                                                                 [EnumeratorCancellation] CancellationToken cancellationToken)
        {
            _logger.LogInformation("--- Starting Sanitization (streaming) ---");

            int count = 0;
            int maskedCount = 0;
            string keyToMask = "sensor_id"; // Example PII field

            foreach(var item in schematizedData)
            {
                 cancellationToken.ThrowIfCancellationRequested();
                 count++;
                 var processedItem = item; // Modify in place

                 if (processedItem.TryGetValue(keyToMask, out object? sensorIdValue) && sensorIdValue != null)
                 {
                     string originalId = sensorIdValue.ToString() ?? string.Empty;
                     if (!string.IsNullOrEmpty(originalId)) 
                     {
                        string maskedId = originalId.Length > 3 ? originalId.Substring(0, 3) + "***" : "***";
                        processedItem[keyToMask] = maskedId;
                        maskedCount++;
                        _logger.LogTrace("Masked {Key} for item id {ItemId}", keyToMask, processedItem.GetValueOrDefault("id", "[unknown_id]"));
                     }
                 }

                 processedItem["processed_stage"] = ProcessingStage.Sanitized.ToString(); 
                 yield return processedItem; // Yield the processed item
            }

            _logger.LogInformation("--- Finished Sanitization (streaming, Processed: {Count} items, Masked '{Key}' for {MaskedCount} items) ---", 
                count, keyToMask, maskedCount);
             await Task.CompletedTask; // Required if there are no awaits inside the async iterator method
        }
    }
} 