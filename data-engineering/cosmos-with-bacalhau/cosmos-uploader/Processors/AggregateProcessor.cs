using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using CosmosUploader.Models;

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
        private readonly ProcessingStage _processingStage;
        private readonly TimeSpan _aggregationWindow;

        public AggregateProcessor(ILogger<AggregateProcessor> logger)
        {
            _logger = logger;
            _processingStage = ProcessingStage.Aggregated;
            _aggregationWindow = TimeSpan.FromMinutes(1); // Default to 1-minute windows
        }

        public Task<IEnumerable<DataItem>> ProcessAsync(IEnumerable<DataItem> sanitizedData, CancellationToken cancellationToken)
        {
            _logger.LogInformation("--- Starting Aggregation ---");

            var aggregatedData = new List<DataItem>();
            int inputCount = 0;
            int windowCount = 0;

            // First group by sensor ID
            var groupedBySensor = sanitizedData.GroupBy(item => item.GetValueOrDefault("sensorId", "unknown_sensor").ToString());

            foreach (var sensorGroup in groupedBySensor)
            {
                cancellationToken.ThrowIfCancellationRequested();
                string sensorId = sensorGroup.Key ?? "unknown_sensor";
                int sensorItemCount = sensorGroup.Count();
                inputCount += sensorItemCount;

                _logger.LogDebug("Processing {ItemCount} items for sensor ID: {SensorId}", sensorItemCount, sensorId);

                // For each sensor, group by time window
                var timeWindowGroups = GroupByTimeWindow(sensorGroup);
                _logger.LogDebug("Created {WindowCount} time windows for sensor {SensorId}", timeWindowGroups.Count, sensorId);

                // Process each time window
                foreach (var windowGroup in timeWindowGroups)
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    windowCount++;

                    // Get window boundaries
                    DateTime windowStart = windowGroup.Key;
                    DateTime windowEnd = windowStart.Add(_aggregationWindow);

                    // Calculate aggregated values for this window
                    var aggregatedItem = AggregateWindow(windowGroup.Value, sensorId, windowStart, windowEnd);

                    // Set processing stage and required fields for aggregated data
                    aggregatedItem["processingStage"] = _processingStage.ToString();
                    
                    // Ensure timestamp matches aggregationWindowEnd for consistency
                    aggregatedItem["timestamp"] = windowEnd;
                    
                    aggregatedData.Add(aggregatedItem);
                }
            }

            _logger.LogInformation("--- Finished Aggregation (Input: {InputCount} items, Created: {WindowCount} time windows, Output: {OutputCount} aggregated items) ---", 
                inputCount, windowCount, aggregatedData.Count);
                
            return Task.FromResult<IEnumerable<DataItem>>(aggregatedData);
        }

        // Group items by time window
        private Dictionary<DateTime, List<DataItem>> GroupByTimeWindow(IEnumerable<DataItem> items)
        {
            var timeWindows = new Dictionary<DateTime, List<DataItem>>();

            foreach (var item in items)
            {
                // Get timestamp from the item
                if (item.TryGetValue("timestamp", out object? tsObj) && tsObj is DateTime timestamp)
                {
                    // Calculate the start of the window this timestamp belongs to
                    DateTime windowStart = RoundDownToWindow(timestamp, _aggregationWindow);
                    
                    // Add item to its time window
                    if (!timeWindows.ContainsKey(windowStart))
                    {
                        timeWindows[windowStart] = new List<DataItem>();
                    }
                    timeWindows[windowStart].Add(item);
                }
                else
                {
                    _logger.LogWarning("Item is missing timestamp or it's not a DateTime. Item ID: {ItemId}", 
                        item.GetValueOrDefault("id", "[unknown]"));
                    // Skip this item since we can't determine its time window
                }
            }
            
            return timeWindows;
        }
        
        // Helper to round a timestamp down to the nearest window boundary
        private DateTime RoundDownToWindow(DateTime dt, TimeSpan window)
        {
            long ticks = dt.Ticks;
            long windowTicks = window.Ticks;
            return new DateTime(ticks - (ticks % windowTicks), dt.Kind);
        }
        
        // Create an aggregated item from items in a time window
        private DataItem AggregateWindow(List<DataItem> windowItems, string sensorId, DateTime windowStart, DateTime windowEnd)
        {
            // Create base item with required fields
            var aggregatedItem = new DataItem
            {
                // Generate a new ID for the aggregated record
                ["id"] = $"agg_{sensorId}_{windowEnd.Ticks}",
                ["sensorId"] = sensorId,
                ["aggregationWindowStart"] = windowStart,
                ["aggregationWindowEnd"] = windowEnd
            };
            
            // Ensure we copy through the location for partition key
            object? location = null;
            foreach (var item in windowItems)
            {
                if (item.TryGetValue("location", out object? locValue) && locValue != null)
                {
                    location = locValue;
                    break; // Found a non-null location
                }
            }
            aggregatedItem["location"] = location ?? "unknown";
            
            // Copy location from the most recent item (assuming last item is most recent)
            var mostRecentItem = windowItems.OrderByDescending(i => 
                i.TryGetValue("timestamp", out object? ts) && ts is DateTime ? (DateTime)ts : DateTime.MinValue)
                .FirstOrDefault();
                
            if (mostRecentItem != null)
            {
                // Copy location fields
                foreach (var field in new[] { "location", "lat", "long" })
                {
                    if (mostRecentItem.TryGetValue(field, out object? value) && value != null)
                    {
                        aggregatedItem[field] = value;
                    }
                    else if (field == "lat" || field == "long")
                    {
                        // Provide default values for lat/long if missing
                        aggregatedItem[field] = "0.0";
                    }
                }
                
                // Copy metadata fields
                foreach (var field in new[] { "firmwareVersion", "model", "manufacturer" })
                {
                    if (mostRecentItem.TryGetValue(field, out object? value) && value != null)
                    {
                        aggregatedItem[field] = value;
                    }
                    else
                    {
                        // Always use empty string (never null) for string fields
                        aggregatedItem[field] = string.Empty;
                    }
                }
            }
            
            // Aggregate numeric sensor readings
            AggregateNumericFields(windowItems, aggregatedItem);
            
            // Derive status from most common status in the window
            AggregateStatus(windowItems, aggregatedItem);
            
            // Aggregate anomalies (if any anomaly, the aggregate has anomaly)
            AggregateAnomalies(windowItems, aggregatedItem);
            
            return aggregatedItem;
        }
        
        private void AggregateNumericFields(List<DataItem> items, DataItem aggregatedItem)
        {
            string[] numericFields = new[] { "temperature", "vibration", "voltage", "humidity" };
            
            foreach (var field in numericFields)
            {
                // Create a list to store all valid values for this field
                var fieldValues = new List<double>();
                
                // First, collect all valid numeric values
                foreach (var item in items)
                {
                    if (item.TryGetValue(field, out object? value) && 
                        value != null && 
                        value is double doubleValue)
                    {
                        fieldValues.Add(doubleValue);
                    }
                }
                
                // Process collected values
                if (fieldValues.Count > 0)
                {
                    // Calculate the sum for the average
                    double sum = fieldValues.Sum();
                    double avg = sum / fieldValues.Count;
                    
                    // Calculate min and max once from the collected values
                    double min = fieldValues.Min();
                    double max = fieldValues.Max();
                    
                    // Store the aggregated values
                    aggregatedItem[field] = avg;
                    aggregatedItem[$"{field}_min"] = min;
                    aggregatedItem[$"{field}_max"] = max;
                    aggregatedItem[$"{field}_count"] = fieldValues.Count;
                }
            }
        }
        
        private void AggregateStatus(List<DataItem> items, DataItem aggregatedItem)
        {
            // Count occurrences of each status value
            var statusCounts = new Dictionary<string, int>();
            
            foreach (var item in items)
            {
                if (item.TryGetValue("status", out object? value) && value != null)
                {
                    string status = value.ToString() ?? "unknown";
                    if (!statusCounts.ContainsKey(status))
                    {
                        statusCounts[status] = 0;
                    }
                    statusCounts[status]++;
                }
            }
            
            // Get most common status
            if (statusCounts.Count > 0)
            {
                string mostCommonStatus = statusCounts.OrderByDescending(kv => kv.Value).First().Key;
                aggregatedItem["status"] = mostCommonStatus;
                
                // Add count of different statuses
                aggregatedItem["status_count"] = statusCounts.Count;
            }
            else
            {
                aggregatedItem["status"] = "unknown";
            }
        }
        
        private void AggregateAnomalies(List<DataItem> items, DataItem aggregatedItem)
        {
            bool hasAnomaly = false;
            var anomalyTypes = new HashSet<string>();
            
            foreach (var item in items)
            {
                // Check if item has anomaly flag set to true
                if (item.TryGetValue("anomalyFlag", out object? flagValue) && 
                    flagValue is bool flagBool && flagBool)
                {
                    hasAnomaly = true;
                    
                    // Collect any anomaly types
                    if (item.TryGetValue("anomalyType", out object? typeValue) && typeValue != null)
                    {
                        string anomalyType = typeValue.ToString() ?? string.Empty;
                        if (!string.IsNullOrEmpty(anomalyType))
                        {
                            anomalyTypes.Add(anomalyType);
                        }
                    }
                }
            }
            
            aggregatedItem["anomalyFlag"] = hasAnomaly;
            
            if (hasAnomaly && anomalyTypes.Count > 0)
            {
                aggregatedItem["anomalyType"] = string.Join(";", anomalyTypes);
                aggregatedItem["anomalyCount"] = anomalyTypes.Count;
            }
        }
    }
} 