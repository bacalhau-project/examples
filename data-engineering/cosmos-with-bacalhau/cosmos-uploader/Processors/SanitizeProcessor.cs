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
    public class SanitizeProcessor : BaseProcessor, ISanitizeProcessor
    {
        public SanitizeProcessor(ILogger<SanitizeProcessor> logger)
            : base(logger, "SanitizeProcessor", ProcessingStage.Sanitized)
        {
        }

        public async Task<IEnumerable<DataTypes.DataItem>> ProcessAsync(
            IEnumerable<DataTypes.DataItem> data,
            CancellationToken cancellationToken)
        {
            _logger.LogInformation("--- Starting Sanitization (buffered) ---");
            var results = new List<DataTypes.DataItem>();
            await foreach (var item in ProcessStreamAsync(WrapInAsyncEnumerable(data), cancellationToken).WithCancellation(cancellationToken))
            {
                results.Add(item);
            }
            _logger.LogInformation("--- Finished Sanitization (buffered, Output: {Count} items) ---", results.Count);
            return results;
        }

        public async IAsyncEnumerable<DataTypes.DataItem> ProcessStreamAsync(
            IAsyncEnumerable<DataTypes.DataItem> data,
            [EnumeratorCancellation] CancellationToken cancellationToken)
        {
            _logger.LogInformation("--- Starting Sanitization (streaming) ---");
            int inputCount = 0;
            int outputCount = 0;

            await foreach (var item in data.WithCancellation(cancellationToken))
            {
                cancellationToken.ThrowIfCancellationRequested();
                inputCount++;

                var processedItem = new DataTypes.DataItem(item);

                // Sanitize numeric fields
                SanitizeNumericFields(processedItem);

                // Sanitize string fields
                SanitizeStringFields(processedItem);

                // Set processing stage
                processedItem["processingStage"] = ProcessingStage.Sanitized.ToString();

                outputCount++;
                yield return processedItem;
            }

            _logger.LogInformation("--- Finished Sanitization (streaming, Input: {InputCount}, Output: {OutputCount} items) ---",
                inputCount, outputCount);
        }

        private void SanitizeNumericFields(DataTypes.DataItem item)
        {
            string[] numericFields = { "temperature", "vibration", "voltage", "humidity" };

            foreach (var field in numericFields)
            {
                if (item.TryGetValue(field, out object? value))
                {
                    // Handle null values
                    if (value == null)
                    {
                        item[field] = 0.0;
                        _logger.LogDebug("Set null value for field {Field} to 0.0 in item {Id}",
                            field, item.TryGetValue("id", out var id) ? id?.ToString() ?? "unknown" : "unknown");
                        continue;
                    }
                    
                    // Handle non-double values
                    if (value is not double doubleValue)
                    {
                        // Try to convert to double
                        if (double.TryParse(value.ToString(), out double parsedValue))
                        {
                            item[field] = parsedValue;
                            _logger.LogTrace("Converted {Field} from {Type} to double in item {Id}",
                                field, value.GetType().Name, item.TryGetValue("id", out var id2) ? id2?.ToString() ?? "unknown" : "unknown");
                        }
                        else
                        {
                            item[field] = 0.0;
                            _logger.LogWarning("Sanitized invalid numeric value for field {Field} in item {Id}",
                                field, item.TryGetValue("id", out var id3) ? id3?.ToString() ?? "unknown" : "unknown");
                        }
                        continue;
                    }
                    
                    // Handle NaN and Infinity
                    if (double.IsNaN(doubleValue) || double.IsInfinity(doubleValue))
                    {
                        item[field] = 0.0;
                        _logger.LogWarning("Sanitized {SpecialValue} value for field {Field} in item {Id}",
                            double.IsNaN(doubleValue) ? "NaN" : "Infinity", field, 
                            item.TryGetValue("id", out var id4) ? id4?.ToString() ?? "unknown" : "unknown");
                    }
                }
                else
                {
                    // Field doesn't exist, add it with default value
                    item[field] = 0.0;
                    _logger.LogTrace("Added missing field {Field} with default value 0.0 to item {Id}",
                        field, item.TryGetValue("id", out var id5) ? id5?.ToString() ?? "unknown" : "unknown");
                }
            }
        }

        private void SanitizeStringFields(DataTypes.DataItem item)
        {
            string[] stringFields = { "sensorId", "location", "status", "anomalyType" };

            foreach (var field in stringFields)
            {
                if (item.TryGetValue(field, out object? value))
                {
                    if (value == null)
                    {
                        item[field] = string.Empty;
                        _logger.LogDebug("Set null value for string field {Field} to empty string in item {Id}",
                            field, item.TryGetValue("id", out var id) ? id?.ToString() ?? "unknown" : "unknown");
                    }
                    else
                    {
                        string stringValue = value.ToString()?.Trim() ?? string.Empty;
                        
                        // If the value changed, log it
                        if (!stringValue.Equals(value.ToString()))
                        {
                            _logger.LogTrace("Trimmed string field {Field} in item {Id}", 
                                field, item.TryGetValue("id", out var id2) ? id2?.ToString() ?? "unknown" : "unknown");
                        }
                        
                        item[field] = stringValue;
                    }
                }
                else
                {
                    item[field] = string.Empty;
                    _logger.LogTrace("Added missing string field {Field} with empty value to item {Id}",
                        field, item.TryGetValue("id", out var id3) ? id3?.ToString() ?? "unknown" : "unknown");
                }
            }
        }
    }
}