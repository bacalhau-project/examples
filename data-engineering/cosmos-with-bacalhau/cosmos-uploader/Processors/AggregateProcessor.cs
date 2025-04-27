using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using System.Runtime.CompilerServices;
using CosmosUploader.Models;

namespace CosmosUploader.Processors
{
    public class AggregateProcessor : BaseProcessor, IAggregateProcessor
    {
        private readonly TimeSpan _timeWindow;

        public AggregateProcessor(ILogger<AggregateProcessor> logger, TimeSpan timeWindow)
            : base(logger, "AggregateProcessor", ProcessingStage.Aggregated)
        {
            _timeWindow = timeWindow;
        }

        public async Task<IEnumerable<DataTypes.DataItem>> ProcessAsync(
            IEnumerable<DataTypes.DataItem> data,
            CancellationToken cancellationToken)
        {
            _logger.LogInformation("--- Starting Aggregation (buffered) ---");
            var results = new List<DataTypes.DataItem>();
            await foreach (var item in ProcessStreamAsync(data, cancellationToken).WithCancellation(cancellationToken))
            {
                results.Add(item);
            }
            _logger.LogInformation("--- Finished Aggregation (buffered, Output: {Count} items) ---", results.Count);
            return results;
        }

        public async IAsyncEnumerable<DataTypes.DataItem> ProcessStreamAsync(
            IEnumerable<DataTypes.DataItem> data,
            [EnumeratorCancellation] CancellationToken cancellationToken)
        {
            _logger.LogInformation("--- Starting Aggregation (streaming) ---");
            int inputCount = 0;
            int outputCount = 0;

            // Group data by sensor ID and time window (explicit key type)
            var groupedData = data.GroupBy(item =>
            {
                // Use TryGetValue and TryParse for robust timestamp handling
                // Cast item to satisfy IReadOnlyDictionary<string, object?> for GetValueOrDefault
                var itemDict = (IReadOnlyDictionary<string, object?>)item;
                object? tsValue = itemDict.GetValueOrDefault("timestamp", null);
                DateTime timestamp = DateTime.MinValue;
                if (tsValue is DateTime dt)
                {
                    timestamp = dt;
                }
                else if (tsValue is string tsString && DateTime.TryParse(tsString, out DateTime parsedDt))
                {
                    timestamp = parsedDt;
                }
                else
                {
                    _logger.LogWarning("Could not parse timestamp from item for aggregation grouping. Using MinValue. Item SensorId: {SensorId}", itemDict.GetValueOrDefault("sensorId", "UNKNOWN"));
                    // Handle or log the case where timestamp is missing or invalid - using MinValue might group unrelated items
                }

                // Use cast itemDict here too
                string sensorId = itemDict.GetValueOrDefault("sensorId", string.Empty)?.ToString() ?? string.Empty;

                // Return explicitly typed tuple for the key
                return (SensorId: sensorId, TimeWindow: GetTimeWindow(timestamp));
            });

            foreach (var group in groupedData)
            {
                cancellationToken.ThrowIfCancellationRequested();
                inputCount += group.Count();

                var aggregatedItem = new DataTypes.DataItem();
                // Add null check for safety, though group.Key shouldn't be null (group.Key is now a tuple)
                // Access tuple elements directly
                aggregatedItem["sensorId"] = group.Key.SensorId; // SensorId is guaranteed non-null from GroupBy
                aggregatedItem["timestamp"] = group.Key.TimeWindow;

                aggregatedItem["processingStage"] = ProcessingStage.Aggregated.ToString();

                // Calculate aggregates for numeric fields
                CalculateAggregates(aggregatedItem, group);

                outputCount++;
                yield return aggregatedItem;
            }

            _logger.LogInformation("--- Finished Aggregation (streaming, Input: {InputCount}, Output: {OutputCount} items) ---",
                inputCount, outputCount);
                
            await Task.CompletedTask;
        }

        private DateTime GetTimeWindow(DateTime timestamp)
        {
            var ticks = timestamp.Ticks / _timeWindow.Ticks;
            return new DateTime(ticks * _timeWindow.Ticks);
        }

        private void CalculateAggregates(DataTypes.DataItem aggregatedItem, IGrouping<(string SensorId, DateTime TimeWindow), DataTypes.DataItem> group)
        {
            string[] numericFields = { "temperature", "vibration", "voltage", "humidity" };
            
            foreach (var field in numericFields)
            {
                var values = group.Select(item => 
                {
                    if (item.TryGetValue(field, out object? value) && value is double d)
                        return d;
                    return 0.0;
                }).ToList();

                if (values.Any())
                {
                    aggregatedItem[$"{field}_min"] = values.Min();
                    aggregatedItem[$"{field}_max"] = values.Max();
                    aggregatedItem[$"{field}_avg"] = values.Average();
                }
            }

            // Count anomalies
            aggregatedItem["anomalyCount"] = group.Count(item => 
                item.TryGetValue("isAnomaly", out object? isAnomaly) && 
                isAnomaly is bool b && b);
        }
    }
} 