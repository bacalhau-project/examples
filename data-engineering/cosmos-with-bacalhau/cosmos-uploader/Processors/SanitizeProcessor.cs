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
                    if (value == null || value is not double || double.IsNaN((double)value) || double.IsInfinity((double)value))
                    {
                        item[field] = 0.0;
                        _logger.LogWarning("Sanitized invalid numeric value for field {Field} in item {Id}",
                            field, item["id"]);
                    }
                }
                else
                {
                    item[field] = 0.0;
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
                    }
                    else
                    {
                        item[field] = value.ToString()?.Trim() ?? string.Empty;
                    }
                }
                else
                {
                    item[field] = string.Empty;
                }
            }
        }
    }
}