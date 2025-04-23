using System;
using System.Collections.Generic;
using System.Data;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using CosmosUploader.Configuration;
using CosmosUploader.Models;
using Microsoft.Data.Sqlite;
using Microsoft.Extensions.Logging;
using Parquet;
using Parquet.Data;
using Parquet.Serialization;
using CosmosUploader.Processors;
using System.Text.Json;

namespace CosmosUploader.Services
{
    // Define placeholder data type consistent with processors
    using DataItem = System.Collections.Generic.Dictionary<string, object>;

    public class SqliteReader
    {
        private readonly ILogger<SqliteReader> _logger;
        private readonly ICosmosUploader _cosmosUploader;
        private readonly AppSettings _settings;
        public string? _dataPath { get; set; }
        public string? _archivePath { get; set; }

        public SqliteReader(ILogger<SqliteReader> logger, ICosmosUploader cosmosUploader, AppSettings settings)
        {
            _logger = logger;
            _cosmosUploader = cosmosUploader;
            _settings = settings;
        }

        public void SetDataPath(string path)
        {
            if (string.IsNullOrEmpty(path))
            {
                throw new ArgumentNullException(nameof(path), "Data path cannot be null or empty");
            }

            // Convert relative path to absolute path based on current working directory
            _dataPath = Path.GetFullPath(path);
            _logger.LogDebug("SQLite data path set to: {Path}", _dataPath);
            
            // Ensure the directory containing the file exists
            string? directoryPath = Path.GetDirectoryName(_dataPath);
            if (string.IsNullOrEmpty(directoryPath))
            {
                throw new InvalidOperationException($"Could not determine directory path for: {_dataPath}");
            }

            if (!Directory.Exists(directoryPath))
            {
                _logger.LogWarning("Directory for SQLite file does not exist: {Path}", directoryPath);
                Directory.CreateDirectory(directoryPath);
            }
        }

        public void SetArchivePath(string path)
        {
            if (string.IsNullOrEmpty(path))
            {
                throw new ArgumentNullException(nameof(path), "Archive path cannot be null or empty");
            }

            _archivePath = path;
            _logger.LogDebug("Archive path set to: {Path}", _archivePath);
            Directory.CreateDirectory(_archivePath);
        }

        public async Task ProcessDatabaseAsync(CancellationToken cancellationToken,
                                             ISchemaProcessor? schemaProcessor = null,
                                             ISanitizeProcessor? sanitizeProcessor = null,
                                             IAggregateProcessor? aggregateProcessor = null)
        {
            if (string.IsNullOrEmpty(_dataPath))
            {
                _logger.LogError("Data path has not been set. Cannot process database.");
                throw new InvalidOperationException("Data path must be set before processing.");
            }

            bool anyBatchProcessedSuccessfully = false;
            List<SensorReading> batchReadings = new List<SensorReading>(); // Hold original readings for potential batch archiving

            try
            {
                await EnsureSyncIndexAsync(_dataPath, cancellationToken);

                if (_settings.DevelopmentMode)
                {
                    await ResetSyncStatusAsync(_dataPath, cancellationToken);
                }

                // Check if the configured processing stage is valid
                string processingStage = _settings.ProcessingStage;
                if (!ProcessingStage.IsValid(processingStage))
                {
                    _logger.LogWarning("Invalid processing stage configured: {Stage}. Falling back to Raw.", processingStage);
                    processingStage = ProcessingStage.Raw;
                }
                
                _logger.LogInformation("Processing database in {Stage} stage", processingStage);

                // Apply processors only if they match the configured stage
                // For example, don't use sanitizeProcessor if processingStage is Raw
                bool useSchemaProcessor = schemaProcessor != null && 
                    (processingStage == ProcessingStage.Schematized || 
                     processingStage == ProcessingStage.Sanitized || 
                     processingStage == ProcessingStage.Aggregated);
                     
                bool useSanitizeProcessor = sanitizeProcessor != null && 
                    (processingStage == ProcessingStage.Sanitized || 
                     processingStage == ProcessingStage.Aggregated);
                     
                bool useAggregateProcessor = aggregateProcessor != null && 
                    processingStage == ProcessingStage.Aggregated;
                
                _logger.LogDebug("Processor usage based on {Stage} stage: Schema={UseSchema}, Sanitize={UseSanitize}, Aggregate={UseAggregate}",
                    processingStage, useSchemaProcessor, useSanitizeProcessor, useAggregateProcessor);

                int batchSize = 1000; // Configurable batch size for reading
                int offset = 0;
                int totalReadCount = 0;
                int batchNumber = 0;

                _logger.LogInformation("Starting processing database {DbPath} in batches of {BatchSize}...", _dataPath, batchSize);

                while (!cancellationToken.IsCancellationRequested)
                {
                    batchNumber++;
                    _logger.LogInformation("Processing Batch #{BatchNumber} (Offset: {Offset})...", batchNumber, offset);

                    // Read a batch of sensor data
                    batchReadings = await ReadSensorDataBatchAsync(_dataPath, offset, batchSize, cancellationToken);
                    if (batchReadings == null || batchReadings.Count == 0)
                    {
                        _logger.LogInformation("No more sensor readings found in database (Batch #{BatchNumber}).", batchNumber);
                        break; // Exit the loop if no more data
                    }
                    totalReadCount += batchReadings.Count;
                    _logger.LogInformation("Read {Count} raw sensor readings for Batch #{BatchNumber}.", batchReadings.Count, batchNumber);

                    // --- Processing Pipeline for the Batch (using streaming where possible) --- 
                    // Start with the raw converted data
                    IEnumerable<DataItem> currentPipelineData = ConvertReadingsToDataItems(batchReadings);
                    IAsyncEnumerable<DataItem>? asyncPipelineData = null; // To hold intermediate async results

                    try 
                    {
                        // Chain processors, passing IAsyncEnumerable between streamable ones
                        if (useSchemaProcessor && schemaProcessor != null)
                        {
                            _logger.LogDebug("Applying Schema Processor (streaming) to Batch #{BatchNumber}...", batchNumber);
                            // Use the streaming method
                            asyncPipelineData = schemaProcessor.ProcessStreamAsync(currentPipelineData, cancellationToken);
                        }
                        else {
                             // If no schema processor, wrap the IEnumerable in an async enumerable for consistency
                             asyncPipelineData = WrapInAsyncEnumerable(currentPipelineData);
                        }

                        if (useSanitizeProcessor && sanitizeProcessor != null) 
                        {
                             _logger.LogDebug("Applying Sanitize Processor (streaming) to Batch #{BatchNumber}...", batchNumber);
                             // Input is the output of the previous stage (or wrapped raw data)
                            asyncPipelineData = sanitizeProcessor.ProcessStreamAsync(asyncPipelineData, cancellationToken);
                        }
                        // else: asyncPipelineData remains from previous stage or wrapped raw data

                        // Aggregation is not easily streamable per-item, so it consumes the async stream
                        // and returns a Task<IEnumerable>
                        IEnumerable<DataItem> finalDataToUpload;
                        if (useAggregateProcessor && aggregateProcessor != null) 
                        {
                             _logger.LogDebug("Applying Aggregate Processor to Batch #{BatchNumber}...", batchNumber);
                             // AggregateProcessor needs to consume the async stream
                             var dataBeforeAggregation = new List<DataItem>();
                             await foreach(var item in asyncPipelineData.WithCancellation(cancellationToken).ConfigureAwait(false)) {
                                 dataBeforeAggregation.Add(item);
                             }
                             _logger.LogDebug("Collected {Count} items before aggregation for Batch #{BatchNumber}.", dataBeforeAggregation.Count, batchNumber);
                             if (!dataBeforeAggregation.Any()) {
                                 finalDataToUpload = Enumerable.Empty<DataItem>();
                             } else {
                                 // Call the aggregate processor (which internally might still buffer groups)
                                 finalDataToUpload = await aggregateProcessor.ProcessAsync(dataBeforeAggregation, cancellationToken);
                             }
                        }
                        else {
                             // No aggregation, materialize the async stream result for upload
                              _logger.LogDebug("No aggregation step. Materializing stream for Batch #{BatchNumber}...", batchNumber);
                             var materializedData = new List<DataItem>();
                             await foreach(var item in asyncPipelineData.WithCancellation(cancellationToken).ConfigureAwait(false)) {
                                 materializedData.Add(item);
                             }
                             finalDataToUpload = materializedData;
                             _logger.LogDebug("Materialized {Count} items for Batch #{BatchNumber}.", finalDataToUpload.Count(), batchNumber);
                        }
                        
                        int finalItemCount = finalDataToUpload.Count();
                         _logger.LogInformation("Processing pipeline completed for Batch #{BatchNumber}. Final item count for upload: {Count}", batchNumber, finalItemCount);
                        if (finalItemCount == 0) { _logger.LogInformation("No data to upload for Batch #{BatchNumber} after processing pipeline.", batchNumber); }

                         // --- Upload processed data for the Batch --- 
                        if (finalDataToUpload.Any()) 
                        { 
                            _logger.LogInformation("Attempting to upload {Count} processed items from Batch #{BatchNumber}...", finalItemCount, batchNumber);
                            try
                            {
                                await _cosmosUploader.UploadDataAsync(finalDataToUpload, cancellationToken);
                            }
                            catch (Exception ex) // Catch specific exceptions if needed (e.g., CosmosException)
                            {
                                _logger.LogError(ex, "Error uploading processed data for Batch #{BatchNumber}. Aborting further processing.", batchNumber);
                                throw; // Rethrow upload errors to stop the process
                            }
                        }
                        // else: Logged above that there's nothing to upload

                    }
                    catch (Exception ex)
                    {
                        _logger.LogError(ex, "Error during data processing pipeline for Batch #{BatchNumber}. Skipping upload for this batch.", batchNumber);
                        throw new Exception($"Processing pipeline failed for Batch #{batchNumber}. Aborting.", ex);
                    }

                    // --- Mark original readings as synced for this batch --- 
                    // Only mark as synced if pipeline and upload (if any) succeeded for the batch
                    try
                    {
                        await MarkBatchAsSyncedAsync(_dataPath, batchReadings, cancellationToken);
                    }
                    catch (Exception ex)
                    {
                         _logger.LogError(ex, "Failed to mark Batch #{BatchNumber} as synced in SQLite. Processing stopped to prevent duplicates.", batchNumber);
                         throw; // Stop processing if we can't mark as synced
                    }

                    // --- Archive original batch readings to Parquet --- 
                    // Archive the *original* readings after successful processing and sync marking
                    if (!string.IsNullOrEmpty(_archivePath))
                    {
                        try
                        {
                            await ArchiveReadingsBatchAsync(batchReadings, cancellationToken);
                        }
                        catch (Exception ex)
                        {
                            _logger.LogError(ex, "Error archiving original readings for Batch #{BatchNumber}. Continuing processing, but archive may be incomplete.", batchNumber);
                            // Decide whether to continue or stop. Let's continue for now.
                        }
                    }
                    else
                    {
                        _logger.LogDebug("Archive path not set, skipping Parquet archiving for Batch #{BatchNumber}.", batchNumber);
                    }

                    anyBatchProcessedSuccessfully = true; // Mark that at least one batch was processed
                    // No need to increment offset manually, the next LIMIT/OFFSET query handles it.
                } // End of while loop for batches

                _logger.LogInformation("Finished processing all batches. Total readings processed: {TotalCount}", totalReadCount);

                // --- Final Archiving / Cleanup --- 
                if (anyBatchProcessedSuccessfully) 
                { 
                    // If we successfully processed at least one batch, we can consider the DB processed.
                    // Optional: Move/Rename the entire processed SQLite file instead of deleting?
                    try 
                    { 
                         // Simple approach: Delete the file if all batches were handled successfully.
                         // More robust: Check if *any* unsynced records remain before deleting.
                         bool remainingUnsynced = await CheckForUnsyncedRecordsAsync(_dataPath, cancellationToken);
                         if (!remainingUnsynced) {
                             _logger.LogInformation("No remaining unsynced records found. Deleting processed database: {DbPath}", _dataPath);
                             // This delete operation might fail if the file is locked, handle gracefully
                             try { File.Delete(_dataPath); } catch (IOException ioEx) { _logger.LogError(ioEx, "Failed to delete processed database file (it might still be locked): {DbPath}", _dataPath); }
                         } else {
                              _logger.LogWarning("Unsynced records still remain in {DbPath} after processing. Database file will not be deleted.", _dataPath);
                         }
                    }
                    catch (Exception ex)
                    {
                         _logger.LogError(ex, "Error during final cleanup/check for database {DbPath}.", _dataPath);
                         // Don't rethrow here usually, allow the process to finish
                    }
                }
                else 
                {
                     _logger.LogInformation("No batches were successfully processed. Skipping final archive/cleanup for {DbPath}", _dataPath);
                }

            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Unhandled error during batch processing for database file: {DbPath}", _dataPath);
                throw; // Rethrow to signal overall processing failure
            }
        }

        // Renamed from ReadSensorDataAsync and modified for batching
        private async Task<List<SensorReading>> ReadSensorDataBatchAsync(string dbPath, int offset, int limit, CancellationToken cancellationToken)
        {
            var readings = new List<SensorReading>();
            var connectionString = $"Data Source={dbPath}";
            
            using (var connection = new SqliteConnection(connectionString))
            {
                await connection.OpenAsync(cancellationToken);
                
                    // Check if the table exists (optional, but good practice)
                    using (var checkCmd = connection.CreateCommand()) {
                        checkCmd.CommandText = "SELECT name FROM sqlite_master WHERE type='table' AND name='sensor_readings'";
                        if (await checkCmd.ExecuteScalarAsync(cancellationToken) == null) {
                            _logger.LogWarning("sensor_readings table not found in database {DbPath}", dbPath);
                            return readings; // Return empty list
                        }
                    }
                
                // Read data using LIMIT and OFFSET
                using (var command = connection.CreateCommand())
                {
                    // Use parameterized query for LIMIT/OFFSET
                    command.CommandText = @"
                        SELECT id, sensor_id, timestamp, temperature, 
                                vibration, voltage, status_code, anomaly_flag,
                                anomaly_type, firmware_version, model, 
                                manufacturer, location
                        FROM sensor_readings
                        WHERE synced = 0
                        ORDER BY timestamp -- Order is important for consistent batching
                        LIMIT @Limit OFFSET @Offset"; // OFFSET is processed first
                    
                    command.Parameters.AddWithValue("@Limit", limit);
                    command.Parameters.AddWithValue("@Offset", offset);
                    
                    _logger.LogDebug("Executing query: {Query} with Limit={Limit}, Offset={Offset}", command.CommandText, limit, offset);

                    using (var reader = await command.ExecuteReaderAsync(cancellationToken))
                    {
                        while (await reader.ReadAsync(cancellationToken))
                        {
                            // Extract sensor information from the path structure more reliably
                            string? dbSensorId = reader.IsDBNull(1) ? null : reader.GetString(1);
                            string? dbLocation = reader.IsDBNull(12) ? null : reader.GetString(12);
                            
                            // Parse the directory path to extract meaningful info
                            // Expected structure: /app/data/CityName/SensorCode/...
                            string directoryPath = Path.GetDirectoryName(dbPath) ?? "";
                            string sensorCodeFromPath = Path.GetFileName(directoryPath);
                            string cityNameFromPath = "";
                            
                            // Get parent directory (city name)
                            string? parentDir = Path.GetDirectoryName(directoryPath);
                            if (!string.IsNullOrEmpty(parentDir))
                            {
                                cityNameFromPath = Path.GetFileName(parentDir);
                            }
                            
                            // Create a better sensor ID based on city and a unique suffix
                            string uniqueSensorId;
                            if (!string.IsNullOrEmpty(dbSensorId) && !dbSensorId.Equals("SENSOR001", StringComparison.OrdinalIgnoreCase))
                            {
                                // Use database sensor ID if it's meaningful
                                uniqueSensorId = dbSensorId;
                            }
                            else
                            {
                                // Generate a more meaningful ID using path components and file info
                                string cityCode = !string.IsNullOrEmpty(cityNameFromPath) ? cityNameFromPath.Substring(0, Math.Min(3, cityNameFromPath.Length)).ToUpper() : "UNK";
                                
                                // Use sensorCodeFromPath if available, otherwise create a unique ID portion
                                string sensorCodePart;
                                if (!string.IsNullOrEmpty(sensorCodeFromPath) && sensorCodeFromPath != "data" && !sensorCodeFromPath.EndsWith(".db"))
                                {
                                    sensorCodePart = sensorCodeFromPath;
                                }
                                else
                                {
                                    // Use database file info for uniqueness
                                    sensorCodePart = $"S{DateTime.Now.ToString("HHmmssfff")}"; // Added milliseconds for uniqueness
                                }
                                
                                uniqueSensorId = $"{cityCode}_{sensorCodePart}";
                            }
                            
                            // Use the database location if available, otherwise use the path information
                            string location = !string.IsNullOrEmpty(dbLocation) ? dbLocation : cityNameFromPath;
                            
                            // Use the constructed sensor ID
                            string sensorId = uniqueSensorId;
                            
                            _logger.LogDebug(
                                "Reading data for sensor: dbSensorId={DbSensorId}, pathSensorId={PathSensorId}, " +
                                "dbLocation={DbLocation}, pathLocation={PathLocation}, final sensorId={FinalSensorId}, final location={FinalLocation}", 
                                dbSensorId, $"{cityNameFromPath}_{sensorCodeFromPath}", dbLocation, cityNameFromPath, sensorId, location);
                            
                            // Extract latitude and longitude if available in the location string
                            string? lat = null;
                            string? lng = null;
                            
                            // Check if location might contain coordinates (simple check for comma)
                            if (!string.IsNullOrEmpty(dbLocation) && dbLocation.Contains(","))
                            {
                                var parts = dbLocation.Split(',', StringSplitOptions.RemoveEmptyEntries);
                                if (parts.Length >= 2)
                                {
                                    if (double.TryParse(parts[0].Trim(), out double latValue))
                                    {
                                        lat = latValue.ToString(CultureInfo.InvariantCulture);
                                    }
                                    
                                    if (double.TryParse(parts[1].Trim(), out double lngValue))
                                    {
                                        lng = lngValue.ToString(CultureInfo.InvariantCulture);
                                    }
                                }
                            }
                            
                            // If we couldn't extract coordinates, try to look them up from the configured city settings
                            if ((lat == null || lng == null) && _settings.Cities != null)
                            {
                                var citySettings = _settings.Cities.FirstOrDefault(c => 
                                    string.Equals(c.Name, location, StringComparison.OrdinalIgnoreCase) || 
                                    string.Equals(c.Name, cityNameFromPath, StringComparison.OrdinalIgnoreCase));
                                    
                                if (citySettings != null)
                                {
                                    lat = citySettings.Latitude.ToString(CultureInfo.InvariantCulture);
                                    lng = citySettings.Longitude.ToString(CultureInfo.InvariantCulture);
                                }
                            }
                            
                            var reading = new SensorReading
                            {
                                Id = reader.GetInt64(0).ToString(),
                                SensorId = sensorId,
                                Timestamp = ParseDateTime(reader.GetString(2)),
                                Temperature = reader.IsDBNull(3) ? null : reader.GetDouble(3),
                                Vibration = reader.IsDBNull(4) ? null : reader.GetDouble(4),
                                Voltage = reader.IsDBNull(5) ? null : reader.GetDouble(5),
                                Status = reader.IsDBNull(6) ? "unknown" : reader.GetInt32(6).ToString(),
                                AnomalyFlag = reader.IsDBNull(7) ? false : reader.GetInt32(7) == 1,
                                AnomalyType = reader.IsDBNull(8) ? null : reader.GetString(8),
                                FirmwareVersion = reader.IsDBNull(9) ? null : reader.GetString(9),
                                Model = reader.IsDBNull(10) ? null : reader.GetString(10),
                                Manufacturer = reader.IsDBNull(11) ? null : reader.GetString(11),
                                Location = location,
                                City = location, // Setting City to the same as Location for consistency
                                Lat = lat,
                                Long = lng,
                                Humidity = null, // No humidity in source data, would need to be generated
                                ProcessingStage = _settings.ProcessingStage, // Set to the configured stage
                                Processed = false
                            };
                            
                            readings.Add(reading);
                        }
                    }
                }
            }
            
            _logger.LogDebug("Read {Count} sensor readings for batch (Offset: {Offset}, Limit: {Limit}).", readings.Count, offset, limit);
            return readings;
        }

        // New method to mark a specific batch of readings as synced using their original IDs
        private async Task MarkBatchAsSyncedAsync(string dbPath, List<SensorReading> readingsToSync, CancellationToken cancellationToken)
        {
            if (readingsToSync == null || readingsToSync.Count == 0) return;

            var idsToUpdate = readingsToSync.Select(r => r.Id).ToList();
            _logger.LogDebug("Marking {Count} readings as synced in {DbPath}...", idsToUpdate.Count, dbPath);

            var connectionString = $"Data Source={dbPath}";
            using (var connection = new SqliteConnection(connectionString))
            {
                await connection.OpenAsync(cancellationToken);
                using (var transaction = connection.BeginTransaction()) 
                {
                    using (var command = connection.CreateCommand()) 
                    {
                        // Use parameterized query with IN clause (less efficient for huge lists, but ok for batches)
                        // Note: Parameter limits might exist. Consider splitting into smaller update batches if idsToUpdate is very large.
                        command.CommandText = $"UPDATE sensor_readings SET synced = 1 WHERE id IN ({string.Join(",", idsToUpdate.Select((_,i) => $"@id{i}"))})";
                        for(int i = 0; i < idsToUpdate.Count; i++)
                        {
                             // Assuming Id is originally stored as INTEGER/BIGINT in SQLite
                            if (long.TryParse(idsToUpdate[i], out long idValue)) {
                                command.Parameters.AddWithValue($"@id{i}", idValue);
                            } else {
                                 _logger.LogWarning("Could not parse reading ID '{ReadingId}' as long for sync update. Skipping this ID.", idsToUpdate[i]);
                                // This might lead to this record not being marked as synced. Handle error appropriately.
                            }
                        }
                        
                        int rowsAffected = await command.ExecuteNonQueryAsync(cancellationToken);
                         _logger.LogDebug("Marked {RowsAffected} rows as synced for the batch.", rowsAffected);
                         if (rowsAffected != idsToUpdate.Count) {
                              _logger.LogWarning("Number of rows marked as synced ({RowsAffected}) does not match the number of readings in the batch ({BatchCount}). Potential issue.", rowsAffected, idsToUpdate.Count);
                         }
                    }
                    await transaction.CommitAsync(cancellationToken);
                }
            }
        }

        // New method to archive a batch of original readings
        private async Task ArchiveReadingsBatchAsync(List<SensorReading> readings, CancellationToken cancellationToken)
        {
             if (string.IsNullOrEmpty(_archivePath) || readings == null || !readings.Any()) {
                return;
            }

            // Group by sensor ID and Location for batch archiving (filename determination)
            var groupedForArchive = readings.GroupBy(r => new { r.SensorId, r.Location });

            foreach(var group in groupedForArchive)
            {
                string sensorId = group.Key.SensorId;
                string location = group.Key.Location;
                var readingsInGroup = group.ToList();

                if (string.IsNullOrEmpty(sensorId) || string.IsNullOrEmpty(location)) {
                    _logger.LogWarning("Skipping archive for {Count} readings with missing SensorId or Location.", readingsInGroup.Count);
                    continue;
                }

                 try
                {
                    string cityName = location.Trim(); 
                    string cityPrefix = "";
                    if (!string.IsNullOrEmpty(cityName) && cityName.Length >= 3)
                    {
                        string cleanCity = new string(cityName.Where(c => char.IsLetterOrDigit(c) || c == '_').ToArray());
                        if (cleanCity.Contains('_')) { cleanCity = cleanCity.Split('_')[0]; }
                        cityPrefix = cleanCity.Substring(0, Math.Min(3, cleanCity.Length)).ToUpper();
                    }
                    string sensorCode = sensorId;
                    if (!sensorId.StartsWith(cityPrefix) && !string.IsNullOrEmpty(cityPrefix)) { sensorCode = $"{cityPrefix}_{sensorId}"; }
                    else if (string.IsNullOrEmpty(cityPrefix)) { sensorCode = sensorId; }
                    
                    string filename = $"{sensorCode}.parquet";
                    string fullPath = Path.Combine(_archivePath, filename);
                    
                    _logger.LogDebug("Archiving {Count} readings for sensor {SensorId} from batch to {File}", 
                        readingsInGroup.Count, sensorId, fullPath);
                    
                    List<SensorReading> existingReadings = new List<SensorReading>();
                    if (File.Exists(fullPath))
                    {
                        // Use try-catch for file operations
                        try {
                            using (var fileStream = File.OpenRead(fullPath))
                            {
                                var deserialized = await ParquetSerializer.DeserializeAsync<SensorReading>(fileStream, cancellationToken: cancellationToken);
                                existingReadings = deserialized.ToList();
                            }
                        } catch (Exception ex) {
                             _logger.LogWarning(ex, "Failed to read existing parquet file {File}. It might be corrupted or locked. Will attempt to overwrite.", fullPath);
                             existingReadings.Clear(); // Clear if read fails
                        }
                    }
                    
                    var allReadings = existingReadings.Concat(readingsInGroup).ToList();
                    
                     try {
                        // Use a temporary file and rename to make the write more atomic
                        string tempPath = fullPath + ".tmp";
                        using (var fileStream = File.Create(tempPath))
                        {
                            await ParquetSerializer.SerializeAsync(allReadings, fileStream, cancellationToken: cancellationToken);
                        }
                        File.Move(tempPath, fullPath, true); // Overwrite if exists

                        _logger.LogDebug("Successfully archived/appended {Count} total readings for sensor {SensorId} to {File}", 
                            allReadings.Count, sensorId, fullPath);
                    } catch (IOException ioEx) {
                         _logger.LogError(ioEx, "IO Error writing/renaming parquet file {File} for sensor {SensorId}. Archive for this batch might be lost.", fullPath, sensorId);
                    } catch (Exception ex) {
                        _logger.LogError(ex, "Error serializing parquet file {File} for sensor {SensorId}. Archive for this batch might be lost.", fullPath, sensorId);
                    }
                }
                catch (Exception ex)
                { // Catch errors creating filename etc.
                    _logger.LogError(ex, "Error preparing archive for sensor {SensorId} in batch: {Message}", sensorId, ex.Message);
                }
            }
        }

        // New method to check if any unsynced records remain
        private async Task<bool> CheckForUnsyncedRecordsAsync(string dbPath, CancellationToken cancellationToken)
        {
            _logger.LogDebug("Checking for remaining unsynced records in {DbPath}...", dbPath);
            var connectionString = $"Data Source={dbPath}";
            using (var connection = new SqliteConnection(connectionString))
            {
                await connection.OpenAsync(cancellationToken);
                using (var command = connection.CreateCommand())
                {
                    command.CommandText = "SELECT 1 FROM sensor_readings WHERE synced = 0 LIMIT 1";
                    var result = await command.ExecuteScalarAsync(cancellationToken);
                    bool remaining = (result != null);
                    _logger.LogDebug("Unsynced records remaining: {Remaining}", remaining);
                    return remaining;
                }
            }
        }

        private async Task EnsureSyncIndexAsync(string dbPath, CancellationToken cancellationToken)
        {
            _logger.LogDebug("Ensuring index 'idx_sensor_readings_synced' exists on {DbPath}", dbPath);
            var connectionString = $"Data Source={dbPath}";
            using (var connection = new SqliteConnection(connectionString))
            {
                await connection.OpenAsync(cancellationToken);

                // Check if table exists first (optional but good practice)
                bool tableExists = false;
                using (var checkCmd = connection.CreateCommand())
                {
                    checkCmd.CommandText = "SELECT name FROM sqlite_master WHERE type='table' AND name='sensor_readings'";
                    if (await checkCmd.ExecuteScalarAsync(cancellationToken) != null)
                    {
                        tableExists = true;
                    }
                }

                if (!tableExists)
                {
                    _logger.LogWarning("Table 'sensor_readings' not found. Cannot create index.");
                    return;
                }

                using (var command = connection.CreateCommand())
                {
                    command.CommandText = "CREATE INDEX IF NOT EXISTS idx_sensor_readings_synced ON sensor_readings (synced);";
                    await command.ExecuteNonQueryAsync(cancellationToken);
                    // Note: ExecuteNonQuery doesn't easily tell us if the index was *newly* created or already existed.
                    // We could query sqlite_master again if we needed that specific info, but IF NOT EXISTS handles the core logic.
                    _logger.LogDebug("Index check/creation command executed successfully.");
                }
            }
        }

        private async Task ResetSyncStatusAsync(string dbPath, CancellationToken cancellationToken)
        {
            _logger.LogWarning("DEVELOPMENT MODE: Resetting sync status for all records in {DbPath}", dbPath);
            var connectionString = $"Data Source={dbPath}";
            using (var connection = new SqliteConnection(connectionString))
            {
                await connection.OpenAsync(cancellationToken);

                // Check if table and column exist before updating
                bool tableExists = false;
                using (var checkCmd = connection.CreateCommand())
                {
                    checkCmd.CommandText = "SELECT name FROM sqlite_master WHERE type='table' AND name='sensor_readings'";
                    if (await checkCmd.ExecuteScalarAsync(cancellationToken) != null)
                    {
                        tableExists = true;
                    }
                }

                if (!tableExists)
                {
                    _logger.LogWarning("Table 'sensor_readings' not found. Skipping sync status reset.");
                    return;
                }

                // Consider checking if 'synced' column exists if schema might vary
                // For now, assume it exists if the table exists

                using (var command = connection.CreateCommand())
                {
                    command.CommandText = "UPDATE sensor_readings SET synced = 0 WHERE synced != 0";
                    int rowsAffected = await command.ExecuteNonQueryAsync(cancellationToken);
                    _logger.LogInformation("Reset sync status for {RowsAffected} records.", rowsAffected);
                }
            }
        }

        /// <summary>
        /// Parse a datetime string safely, handling various formats.
        /// </summary>
        /// <param name="dateTimeStr">The datetime string to parse</param>
        /// <returns>A valid DateTime object</returns>
        private DateTime ParseDateTime(string dateTimeStr)
        {
            try
            {
                // Try parsing as Unix timestamp (seconds since epoch)
                if (double.TryParse(dateTimeStr, out double unixTimestamp))
                {
                    // Convert Unix timestamp to DateTime
                    return DateTimeOffset.FromUnixTimeSeconds((long)unixTimestamp).DateTime;
                }

                // If not a Unix timestamp, try parsing as regular datetime string
                if (DateTime.TryParse(dateTimeStr, out DateTime result))
                {
                    return result;
                }

                _logger.LogWarning("Could not parse datetime: {DateTime}, using current UTC time", dateTimeStr);
                return DateTime.UtcNow;
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Error parsing datetime: {DateTime}, using current UTC time", dateTimeStr);
                return DateTime.UtcNow;
            }
        }

        // Updated method to convert SensorReading to DataItem with the new schema fields
        private IEnumerable<DataItem> ConvertReadingsToDataItems(List<SensorReading> readings)
        {
            _logger.LogDebug("Converting {Count} SensorReading objects to DataItem dictionaries.", readings.Count);
            var dataItems = new List<DataItem>();
            
            // Get the configured processing stage
            string processingStage = _settings.ProcessingStage;
            if (!ProcessingStage.IsValid(processingStage))
            {
                _logger.LogWarning("Invalid processing stage configured: {Stage}. Falling back to Raw.", processingStage);
                processingStage = ProcessingStage.Raw;
            }
            
            foreach(var reading in readings)
            {
                // Create a data item with fields populated based on the processing stage
                var item = new DataItem();
                
                // These fields are always included regardless of processing stage
                item["id"] = reading.Id;
                item["sensorId"] = reading.SensorId;
                item["timestamp"] = reading.Timestamp;
                item["city"] = reading.City;
                item["location"] = reading.Location;
                item["processingStage"] = processingStage;
                
                // Capture raw sensor data as a JSON string for Raw stage
                if (processingStage == ProcessingStage.Raw)
                {
                    // Serialize the original reading to JSON for the rawDataString
                    var rawData = new Dictionary<string, object?>
                    {
                        ["id"] = reading.Id,
                        ["sensorId"] = reading.SensorId,
                        ["timestamp"] = reading.Timestamp,
                        ["temperature"] = reading.Temperature,
                        ["vibration"] = reading.Vibration,
                        ["voltage"] = reading.Voltage,
                        ["status"] = reading.Status,
                        ["location"] = reading.Location,
                        ["city"] = reading.City
                    };
                    item["rawDataString"] = JsonSerializer.Serialize(rawData);
                    
                    // For Raw stage, we might still include some basic parsed data if available
                    if (reading.Temperature.HasValue) item["temperature"] = reading.Temperature.Value;
                    if (reading.Vibration.HasValue) item["vibration"] = reading.Vibration.Value;
                    if (reading.Voltage.HasValue) item["voltage"] = reading.Voltage.Value;
                    item["status"] = reading.Status;
                }
                
                // Include all fields for stages above Raw
                if (processingStage != ProcessingStage.Raw)
                {
                    // Core sensor readings
                    if (reading.Temperature.HasValue) item["temperature"] = reading.Temperature.Value;
                    if (reading.Vibration.HasValue) item["vibration"] = reading.Vibration.Value;
                    if (reading.Voltage.HasValue) item["voltage"] = reading.Voltage.Value;
                    if (reading.Humidity.HasValue) item["humidity"] = reading.Humidity.Value;
                    item["status"] = reading.Status;
                    
                    // Anomaly information
                    item["anomalyFlag"] = reading.AnomalyFlag;
                    if (!string.IsNullOrEmpty(reading.AnomalyType)) item["anomalyType"] = reading.AnomalyType;
                    
                    // Metadata fields
                    if (!string.IsNullOrEmpty(reading.FirmwareVersion)) item["firmwareVersion"] = reading.FirmwareVersion;
                    if (!string.IsNullOrEmpty(reading.Model)) item["model"] = reading.Model;
                    if (!string.IsNullOrEmpty(reading.Manufacturer)) item["manufacturer"] = reading.Manufacturer;
                    
                    // Location with varying precision based on processingStage
                    if (processingStage == ProcessingStage.Sanitized)
                    {
                        // For Sanitized: Reduce precision of lat/long
                        // Extract and sanitize lat/long from location if available
                        SanitizeLocationData(reading, item);
                    }
                    else
                    {
                        // For Schematized: Include precise location data if available
                        if (!string.IsNullOrEmpty(reading.Lat)) item["lat"] = reading.Lat;
                        if (!string.IsNullOrEmpty(reading.Long)) item["long"] = reading.Long;
                    }
                    
                    // For Aggregated: Include aggregation window information
                    if (processingStage == ProcessingStage.Aggregated)
                    {
                        // In a real implementation, these would be calculated based on a time window
                        // Here we're just setting them to examples for demonstration
                        DateTime timestamp = reading.Timestamp;
                        DateTime windowStart = new DateTime(timestamp.Year, timestamp.Month, timestamp.Day, timestamp.Hour, timestamp.Minute, 0);
                        DateTime windowEnd = windowStart.AddMinutes(1);
                        
                        item["aggregationWindowStart"] = windowStart;
                        item["aggregationWindowEnd"] = windowEnd;
                    }
                }
                
                // Handle development mode overrides (e.g., generate new IDs, update timestamps)
                if (_settings.DevelopmentMode)
                {
                    var newId = Guid.NewGuid().ToString();
                    _logger.LogTrace("DEV MODE: Overwriting ID {OldId} with {NewId}", item["id"], newId);
                    item["id"] = newId;
                    
                    var now = DateTime.UtcNow;
                    _logger.LogTrace("DEV MODE: Overwriting timestamp {OldTs} with {NewTs}", item["timestamp"], now);
                    item["timestamp"] = now;
                }
                
                dataItems.Add(item);
            }
            
            return dataItems;
        }

        // Helper method to sanitize location data (reduce precision)
        private void SanitizeLocationData(SensorReading reading, DataItem item)
        {
            // Parse and sanitize latitude if available
            if (!string.IsNullOrEmpty(reading.Lat) && double.TryParse(reading.Lat, out double lat))
            {
                // Reduce precision to 2 decimal places (roughly 1km accuracy)
                string sanitizedLat = Math.Round(lat, 2).ToString("F2", CultureInfo.InvariantCulture);
                item["lat"] = sanitizedLat;
            }
            
            // Parse and sanitize longitude if available
            if (!string.IsNullOrEmpty(reading.Long) && double.TryParse(reading.Long, out double lng))
            {
                // Reduce precision to 2 decimal places
                string sanitizedLong = Math.Round(lng, 2).ToString("F2", CultureInfo.InvariantCulture);
                item["long"] = sanitizedLong;
            }
            
            // Update location string to reflect sanitized coordinates
            if (item.ContainsKey("lat") && item.ContainsKey("long"))
            {
                item["location"] = $"{item["lat"]},{item["long"]}";
            }
        }

        // Helper to wrap IEnumerable in IAsyncEnumerable if needed
        private async IAsyncEnumerable<T> WrapInAsyncEnumerable<T>(IEnumerable<T> source) {
            foreach (var item in source) {
                yield return item;
            }
            await Task.CompletedTask; // Keep the compiler happy
        }
    }
}
