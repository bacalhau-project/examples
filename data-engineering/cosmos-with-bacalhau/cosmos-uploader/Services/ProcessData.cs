using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using CosmosUploader.Configuration;
using CosmosUploader.Models;
using CosmosUploader.Processors; // Required for processor interfaces
using Microsoft.Extensions.DependencyInjection; // Required for IServiceProvider
using Microsoft.Extensions.Logging;
using System.Globalization;

namespace CosmosUploader.Services
{
    public class ProcessData
    {
        private readonly ILogger<ProcessData> _logger;
        private readonly AppSettings _settings;
        private readonly IServiceProvider _serviceProvider; // Inject IServiceProvider

        // Remove direct processor dependencies
        // private readonly ISchemaProcessor? _schemaProcessor;
        // private readonly ISanitizeProcessor? _sanitizeProcessor;
        // private readonly IAggregateProcessor? _aggregateProcessor;

        public ProcessData(
            ILogger<ProcessData> logger,
            AppSettings settings,
            IServiceProvider serviceProvider // Add IServiceProvider to constructor
            // Remove processor interfaces from constructor parameters
            )
        {
            _logger = logger;
            _settings = settings;
            _serviceProvider = serviceProvider; // Store IServiceProvider
            // Remove assignments for direct processors
        }

        public async Task<List<DataTypes.DataItem>> ProcessAsync(List<SensorReading> rawReadings, CancellationToken cancellationToken)
        {
            if (rawReadings == null || !rawReadings.Any())
            {
                _logger.LogInformation("No raw readings provided for processing.");
                return new List<DataTypes.DataItem>();
            }

            int initialCount = rawReadings.Count;
            // Update log message to show the processor list
            _logger.LogInformation("Starting data processing pipeline for {Count} raw readings. Pipeline: [{Pipeline}]",
                initialCount, string.Join(" -> ", _settings.Processors));

            // 1. Convert raw SensorReading objects to DataItem dictionaries
            List<DataTypes.DataItem> currentPipelineData = ConvertReadingsToDataItems(rawReadings);
            _logger.LogDebug("Converted {Count} raw readings to DataItems.", currentPipelineData.Count);

            // 3. Apply processing pipeline steps sequentially based on the configured list
            try
            {
                // --- Pipeline Execution Loop ---
                foreach (var processorName in _settings.Processors)
                {
                    cancellationToken.ThrowIfCancellationRequested();

                    _logger.LogDebug("Attempting to apply pipeline processor: {ProcessorName}...", processorName);
                    // ResolveProcessor now returns object? or null
                    object? processorInstance = ResolveProcessor(processorName);

                    if (processorInstance != null)
                    {
                        var dataBefore = currentPipelineData;
                        _logger.LogDebug("Processing with {ProcessorType}...", processorInstance.GetType().Name);

                        // Cast to the appropriate interface and call ProcessAsync
                        if (processorInstance is ISchemaProcessor schemaProcessor)
                        {
                            var result = await schemaProcessor.ProcessAsync(dataBefore, cancellationToken);
                            currentPipelineData = result?.ToList() ?? new List<DataTypes.DataItem>();
                        }
                        else if (processorInstance is ISanitizeProcessor sanitizeProcessor)
                        {
                            var result = await sanitizeProcessor.ProcessAsync(dataBefore, cancellationToken);
                            currentPipelineData = result?.ToList() ?? new List<DataTypes.DataItem>();
                        }
                        // Aggregate case removed from pipeline loop
                        else
                        {
                            _logger.LogError("Resolved processor '{ProcessorName}' is not a recognized processor type (ISchemaProcessor or ISanitizeProcessor).", processorName);
                            // Skip this processor
                            continue;
                        }

                        _logger.LogDebug("Pipeline processor '{ProcessorName}' completed. Item count: {Count}", processorName, currentPipelineData.Count);

                        if (!currentPipelineData.Any())
                        {
                            _logger.LogWarning("Pipeline yielded zero items after processor '{ProcessorName}'. Subsequent processors and aggregation will be skipped.", processorName);
                            break; // Stop processing if the pipeline yields no data
                        }
                    }
                }

                // --- Aggregation Step (if configured and data exists) ---
                if (_settings.AggregationWindow.HasValue && currentPipelineData.Any())
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    _logger.LogDebug("Applying final Aggregation step with window {Window}...", _settings.AggregationWindow.Value);

                    // Resolve the AggregateProcessor specifically
                    var aggregateProcessor = _serviceProvider.GetService<IAggregateProcessor>();
                    if (aggregateProcessor != null)
                    {
                        var dataBefore = currentPipelineData;
                        // Assuming AggregateProcessor now uses AppSettings for the window
                        var result = await aggregateProcessor.ProcessAsync(dataBefore, cancellationToken);
                        currentPipelineData = result?.ToList() ?? new List<DataTypes.DataItem>();
                        _logger.LogDebug("Aggregation step completed. Item count: {Count}", currentPipelineData.Count);
                    }
                    else
                    {
                        // Should not happen if registration in Program.cs is correct
                        _logger.LogError("Configuration error: Aggregation was configured but IAggregateProcessor service could not be resolved.");
                        // Optionally throw an exception here
                    }
                }
                else if (_settings.AggregationWindow.HasValue)
                {
                    _logger.LogWarning("Skipping aggregation step as there are no items remaining after the processing pipeline.");
                }

                // 4. Apply Development Mode overrides if enabled (e.g., new IDs, timestamps)
                if (_settings.DevelopmentMode)
                {
                    _logger.LogWarning("DEVELOPMENT MODE: Applying overrides (new IDs, timestamps) to processed data.");
                    ApplyDevelopmentModeOverrides(currentPipelineData);
                }

                int finalCount = currentPipelineData.Count;
                _logger.LogInformation("Processing pipeline completed. Initial items: {InitialCount}, Final items: {FinalCount}", initialCount, finalCount);

                return currentPipelineData;
            }
            catch (OperationCanceledException)
            {
                _logger.LogWarning("Data processing was cancelled.");
                throw;
            }
            catch (Exception ex)
            {
                // Update error log to indicate which processor potentially failed (though the exact one isn't known here)
                _logger.LogError(ex, "Error during data processing pipeline. Pipeline: [{Pipeline}]", string.Join(" -> ", _settings.Processors));
                // Depending on requirements, you might return partial results or an empty list
                throw; // Re-throw to indicate failure
            }
        }

        // Helper method returns object? now
        private object? ResolveProcessor(string processorName)
        {
            // Use IServiceProvider to get the registered service for the interface
            if (StringComparer.OrdinalIgnoreCase.Equals(processorName, "Schematize"))
            {
                return _serviceProvider.GetService<ISchemaProcessor>();
            }
            else if (StringComparer.OrdinalIgnoreCase.Equals(processorName, "Sanitize"))
            {
                return _serviceProvider.GetService<ISanitizeProcessor>();
            }
            // Removed Aggregate case
            else
            {
                _logger.LogWarning("Attempted to resolve unknown pipeline processor name: {ProcessorName}", processorName);
                return null;
            }
        }

        // Basic conversion from SensorReading to DataItem. More complex logic belongs in processors.
        private List<DataTypes.DataItem> ConvertReadingsToDataItems(List<SensorReading> readings)
        {
            var dataItems = new List<DataTypes.DataItem>();
            foreach (var reading in readings)
            {
                var item = new DataTypes.DataItem
                {
                    // Always include base fields
                    ["sqlite_id"] = reading.OriginalSqliteId,
                    ["sensorId"] = reading.SensorId,
                    // Format timestamp using ISO 8601 round-trip format ("o")
                    ["timestamp"] = reading.Timestamp.ToString("o", CultureInfo.InvariantCulture),
                    ["city"] = reading.City,
                    ["location"] = reading.Location,
                    // ["processingStage"] will be set/updated by processors
                };

                // Add optional fields if they exist in the raw reading
                if (reading.Temperature.HasValue) item["temperature"] = reading.Temperature.Value;
                if (reading.Vibration.HasValue) item["vibration"] = reading.Vibration.Value;
                if (reading.Voltage.HasValue) item["voltage"] = reading.Voltage.Value;
                if (reading.Humidity.HasValue) item["humidity"] = reading.Humidity.Value; // Include if present
                if (reading.Pressure.HasValue) item["pressure"] = reading.Pressure.Value;
                if (!string.IsNullOrEmpty(reading.Status)) item["status"] = reading.Status;
                item["anomalyFlag"] = reading.AnomalyFlag; // Include raw flag
                if (!string.IsNullOrEmpty(reading.AnomalyType)) item["anomalyType"] = reading.AnomalyType; // Include raw type
                if (!string.IsNullOrEmpty(reading.FirmwareVersion)) item["firmwareVersion"] = reading.FirmwareVersion;
                if (!string.IsNullOrEmpty(reading.Model)) item["model"] = reading.Model;
                if (!string.IsNullOrEmpty(reading.Manufacturer)) item["manufacturer"] = reading.Manufacturer;
                if (reading.Latitude.HasValue) item["latitude"] = reading.Latitude.Value;
                if (reading.Longitude.HasValue) item["longitude"] = reading.Longitude.Value;

                // RawDataString was specific to the "Raw" processing stage format, skip here.
                // Processors will add stage-specific fields like aggregation windows.

                dataItems.Add(item);
            }
            return dataItems;
        }

        private void ApplyDevelopmentModeOverrides(List<DataTypes.DataItem> dataItems)
        {
            var now = DateTime.UtcNow;
            // Use ISO 8601 round-trip format string
            string nowFormatted = now.ToString("o", CultureInfo.InvariantCulture);

            foreach (var item in dataItems)
            {
                var localId = item.ContainsKey("sqlite_id") ? item["sqlite_id"]?.ToString() : "N/A";
                // var oldId = item.ContainsKey("id") ? item["id"]?.ToString() : "N/A"; // No longer overriding 'id'
                // var newId = Guid.NewGuid().ToString(); // No longer overriding 'id'
                // item["id"] = newId; // Overwrite ID <-- Remove this

                var oldTs = item.ContainsKey("timestamp") ? item["timestamp"]?.ToString() : "N/A";
                // Overwrite timestamp with formatted string
                item["timestamp"] = nowFormatted;

                _logger.LogTrace("DEV MODE: Overwrote Timestamp {OldTs} with {NewTs}. Original SQLite ID: {SqliteId}", oldTs, nowFormatted, localId); // Log the formatted string
            }
        }
    }
} 