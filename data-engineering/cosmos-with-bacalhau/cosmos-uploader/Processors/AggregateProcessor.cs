using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;

namespace CosmosUploader.Processors
{
    // Using the same placeholder data type defined in SchemaProcessor.cs
    using DataItem = System.Collections.Generic.Dictionary<string, object>; 

    public interface IAggregateProcessor
    {
        Task<IEnumerable<DataItem>> ProcessAsync(IEnumerable<DataItem> sanitizedData, CancellationToken cancellationToken);
    }

    public class AggregateProcessor : IAggregateProcessor
    {
        private readonly ILogger<AggregateProcessor> _logger;

        public AggregateProcessor(ILogger<AggregateProcessor> logger)
        {
            _logger = logger;
        }

        public Task<IEnumerable<DataItem>> ProcessAsync(IEnumerable<DataItem> sanitizedData, CancellationToken cancellationToken)
        {
            _logger.LogInformation("--- Starting Aggregation ---");

            // TODO: Implement more complex aggregation based on actual needs.
            // Example: Time windowing, different aggregate functions (sum, count, min, max), multiple grouping keys.

            var aggregatedData = new List<DataItem>();
            int inputCount = 0;

            // Group by sensor_id
            var groupedData = sanitizedData.GroupBy(item => item.GetValueOrDefault("sensor_id", "unknown_sensor").ToString());

            foreach (var group in groupedData)
            {
                cancellationToken.ThrowIfCancellationRequested();
                string sensorId = group.Key ?? "unknown_sensor";
                int groupCount = group.Count();
                inputCount += groupCount;

                 _logger.LogDebug("Aggregating {GroupCount} items for sensor ID: {SensorId}", groupCount, sensorId);

                // Calculate average temperature (handle potential nulls or non-doubles)
                double sumTemp = 0;
                int validTempCount = 0;
                DateTime? firstTimestamp = null;
                DateTime? lastTimestamp = null;

                foreach(var item in group) {
                    if (item.TryGetValue("temperature", out var tempValue) && tempValue is double tempDouble) {
                        sumTemp += tempDouble;
                        validTempCount++;
                    }
                    if (item.TryGetValue("timestamp", out var tsValue) && tsValue is DateTime tsDateTime) {
                        if (firstTimestamp == null || tsDateTime < firstTimestamp) firstTimestamp = tsDateTime;
                        if (lastTimestamp == null || tsDateTime > lastTimestamp) lastTimestamp = tsDateTime;
                    }
                }

                double? averageTemperature = validTempCount > 0 ? sumTemp / validTempCount : (double?)null;

                // Create aggregated item
                var aggregatedItem = new DataItem
                {
                    // Generate a new ID for the aggregated record
                    { "id", $"agg_{sensorId}_{lastTimestamp?.Ticks ?? DateTime.UtcNow.Ticks}" }, 
                    { "sensor_id", sensorId }, // Use the grouping key
                    { "processed_stage", ProcessingStage.Aggregated.ToString() },
                    { "aggregation_type", "average_temperature_per_batch" },
                    { "item_count", groupCount },
                    { "average_temperature", averageTemperature },
                    { "first_timestamp", firstTimestamp },
                    { "last_timestamp", lastTimestamp ?? DateTime.UtcNow }, // Use UtcNow if no valid timestamp found
                    // Add partition key field(s) - assuming partition key is sensor_id or city derived from it
                    // Example: If partition key is city, we need to extract/add it here
                    // Let's assume the partition key is passed through or derivable from sensorId for this example
                    // { "city", group.First().GetValueOrDefault("city", "unknown_city") } // Example if city was present
                };
                
                // IMPORTANT: Ensure the partition key field required by Cosmos DB is present in the aggregated item!
                // We might need to retrieve it from the first item in the group or reconstruct it.
                // For now, assuming sensor_id might be the partition key or part of it.
                string partitionKeyField = "sensor_id"; // Replace with actual partition key field if different
                if (!aggregatedItem.ContainsKey(partitionKeyField)) {
                     if (group.FirstOrDefault()?.TryGetValue(partitionKeyField, out var pkValue) == true) {
                          aggregatedItem[partitionKeyField] = pkValue;
                     } else {
                         _logger.LogWarning("Could not determine partition key '{PartitionKeyField}' for aggregated item with sensor ID {SensorId}. Upload might fail.", partitionKeyField, sensorId);
                         // Handle missing partition key appropriately - maybe skip, maybe use default? Defaulting might overload one partition.
                         aggregatedItem[partitionKeyField] = "unknown_partition_key"; // Placeholder - potentially dangerous
                     }
                }


                aggregatedData.Add(aggregatedItem);
            }

            _logger.LogInformation("--- Finished Aggregation (Input: {InputCount} items across {GroupCount} groups, Output: {OutputCount} aggregated items) ---", 
                inputCount, groupedData.Count(), aggregatedData.Count);
            return Task.FromResult<IEnumerable<DataItem>>(aggregatedData);
        }
    }
} 