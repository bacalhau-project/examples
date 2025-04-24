using System;
using System.Collections.Generic;
using System.Globalization;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using System.Runtime.CompilerServices;
using CosmosUploader.Models;

namespace CosmosUploader.Processors
{
    // Using the same placeholder data type defined in SchemaProcessor.cs
    using DataItem = System.Collections.Generic.Dictionary<string, object>; 

    public interface ISanitizeProcessor
    {
        Task<IEnumerable<DataItem>> ProcessAsync(IEnumerable<DataItem> schematizedData, CancellationToken cancellationToken);
        IAsyncEnumerable<DataItem> ProcessStreamAsync(IAsyncEnumerable<DataItem> schematizedData, CancellationToken cancellationToken);
    }

    public class SanitizeProcessor : ISanitizeProcessor
    {
        private readonly ILogger<SanitizeProcessor> _logger;
        private readonly ProcessingStage _processingStage;

        public SanitizeProcessor(ILogger<SanitizeProcessor> logger)
        {
            _logger = logger;
            _processingStage = ProcessingStage.Sanitized;
        }

        public async Task<IEnumerable<DataItem>> ProcessAsync(IEnumerable<DataItem> schematizedData, CancellationToken cancellationToken)
        {
            _logger.LogDebug("--- Starting Sanitization (buffered wrapper) ---");
            var results = new List<DataItem>();
            await foreach (var item in ProcessStreamAsync(WrapEnumerableAsAsyncEnumerable(schematizedData), cancellationToken).WithCancellation(cancellationToken).ConfigureAwait(false))
            {
                results.Add(item);
            }
            _logger.LogDebug("--- Finished Sanitization (buffered wrapper, Output: {Count} items) ---", results.Count);
            return results;
        }

        public async IAsyncEnumerable<DataItem> ProcessStreamAsync(IAsyncEnumerable<DataItem> schematizedData, 
                                                                 [EnumeratorCancellation] CancellationToken cancellationToken)
        {
            _logger.LogInformation("--- Starting Sanitization (streaming) ---");

            int count = 0;
            int maskedCount = 0;
            int locationSanitizedCount = 0;

            // Fields that should be sanitized (PII)
            string[] piiFields = new[] { "sensorId" };

            await foreach(var item in schematizedData.WithCancellation(cancellationToken))
            {
                 cancellationToken.ThrowIfCancellationRequested();
                 count++;
                 
                 // Create a copy to avoid modifying the original
                 var processedItem = new DataItem(item);
                 
                 // Sanitize PII fields
                 foreach (var field in piiFields)
                 {
                     if (processedItem.TryGetValue(field, out object? value) && value != null)
                     {
                         string originalValue = value.ToString() ?? string.Empty;
                         if (!string.IsNullOrEmpty(originalValue)) 
                         {
                            string maskedValue = originalValue.Length > 3 ? originalValue.Substring(0, 3) + "***" : "***";
                            processedItem[field] = maskedValue;
                            maskedCount++;
                            _logger.LogTrace("Masked {Key} for item id {ItemId}", field, processedItem.GetValueOrDefault("id", "[unknown_id]"));
                         }
                     }
                 }
                 
                 // Sanitize location data
                 SanitizeLocationData(processedItem, ref locationSanitizedCount);

                 // Set the processing stage
                 processedItem["processingStage"] = _processingStage.ToString();
                 
                 yield return processedItem; // Yield the processed item
            }

            _logger.LogInformation("--- Finished Sanitization (streaming, Processed: {Count} items, Masked PII for {MaskedCount} items, Sanitized locations: {LocationCount}) ---", 
                count, maskedCount, locationSanitizedCount);
        }
        
        // Helper to wrap IEnumerable in IAsyncEnumerable
        private async IAsyncEnumerable<T> WrapEnumerableAsAsyncEnumerable<T>(IEnumerable<T> source)
        {
            foreach (var item in source)
            {
                yield return item;
            }
            await Task.CompletedTask; // Keep the compiler happy
        }
        
        // Helper method to sanitize location data (reduce precision)
        private void SanitizeLocationData(DataItem item, ref int sanitizedCount)
        {
            bool wasSanitized = false;
            
            // Parse and sanitize latitude if available
            if (item.TryGetValue("lat", out object? latValue) && latValue != null)
            {
                if (double.TryParse(latValue.ToString(), out double lat))
                {
                    // Reduce precision to 2 decimal places (roughly 1km accuracy)
                    string sanitizedLat = Math.Round(lat, 2).ToString("F2", CultureInfo.InvariantCulture);
                    item["lat"] = sanitizedLat;
                    wasSanitized = true;
                }
            }
            
            // Parse and sanitize longitude if available
            if (item.TryGetValue("long", out object? lngValue) && lngValue != null)
            {
                if (double.TryParse(lngValue.ToString(), out double lng))
                {
                    // Reduce precision to 2 decimal places
                    string sanitizedLong = Math.Round(lng, 2).ToString("F2", CultureInfo.InvariantCulture);
                    item["long"] = sanitizedLong;
                    wasSanitized = true;
                }
            }
            
            // Update location string to reflect sanitized coordinates
            if (wasSanitized && item.ContainsKey("lat") && item.ContainsKey("long"))
            {
                item["location"] = $"{item["lat"]},{item["long"]}";
                sanitizedCount++;
                _logger.LogTrace("Sanitized location coordinates for item ID {ItemId}", item.GetValueOrDefault("id", "[unknown_id]"));
            }
        }
    }
} 