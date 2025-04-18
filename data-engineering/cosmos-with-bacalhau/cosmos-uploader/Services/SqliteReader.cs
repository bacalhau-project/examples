using System;
using System.Collections.Generic;
using System.Data;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using CosmosUploader.Models;
using Microsoft.Data.Sqlite;
using Microsoft.Extensions.Logging;
using Parquet;
using Parquet.Data;
using Parquet.Serialization;

namespace CosmosUploader.Services
{
    public class SqliteReader
    {
        private readonly ILogger<SqliteReader> _logger;
        private readonly ICosmosUploader _cosmosUploader;
        public required string _dataPath { get; set; }
        public required string _archivePath { get; set; }

        public SqliteReader(ILogger<SqliteReader> logger, ICosmosUploader cosmosUploader)
        {
            _logger = logger;
            _cosmosUploader = cosmosUploader;
        }

        public void SetDataPath(string path)
        {
            _dataPath = path;
            _logger.LogInformation("SQLite data path set to: {Path}", _dataPath);
        }

        public void SetArchivePath(string path)
        {
            _archivePath = path;
            _logger.LogInformation("Archive path set to: {Path}", _archivePath);
            Directory.CreateDirectory(_archivePath);
        }

        public async Task ProcessAllDatabasesAsync(CancellationToken cancellationToken)
        {
            _logger.LogInformation("Starting to process all databases in {Path}", _dataPath);
            
            // Ensure Cosmos DB is initialized before processing
            try
            {
                await _cosmosUploader.InitializeAsync();
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to initialize Cosmos DB connection");
                throw;
            }
            
            // Find all SQLite databases
            var dbFiles = Directory.GetFiles(_dataPath, "*.db", SearchOption.AllDirectories);
            _logger.LogInformation("Found {Count} database files", dbFiles.Length);
            
            foreach (var dbFile in dbFiles)
            {
                if (cancellationToken.IsCancellationRequested)
                {
                    _logger.LogWarning("Processing cancelled by user");
                    break;
                }
                
                try
                {
                    await ProcessDatabaseAsync(dbFile, cancellationToken);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Error processing database {Database}", dbFile);
                }
            }
        }

        public async Task ProcessDatabaseAsync(string dbPath, CancellationToken cancellationToken)
        {
            try
            {
                _logger.LogInformation("Processing database: {DbPath}", dbPath);

                // Read sensor data from the database
                var readings = await ReadSensorDataAsync(dbPath, cancellationToken);
                if (readings == null || readings.Count == 0)
                {
                    _logger.LogWarning("No readings found in database: {DbPath}", dbPath);
                    return;
                }

                // Upload readings to Cosmos DB
                try
                {
                    await _cosmosUploader.UploadReadingsAsync(readings, cancellationToken);
                }
                catch (InvalidOperationException ex) when (ex.Message.Contains("Cosmos DB container has not been initialized"))
                {
                    _logger.LogError(ex, "Failed to upload readings to Cosmos DB: {Message}", ex.Message);
                    throw;
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Failed to upload readings to Cosmos DB: {Message}", ex.Message);
                    throw;
                }

                // Archive the database
                await ArchiveDatabaseAsync(dbPath, cancellationToken);

                // Delete the processed database
                DeleteProcessedDatabase(dbPath);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error processing database {DbPath}: {Message}", dbPath, ex.Message);
                throw;
            }
        }

        private async Task<List<SensorReading>> ReadSensorDataAsync(string dbPath, CancellationToken cancellationToken)
        {
            var readings = new List<SensorReading>();
            
            // Format the connection string properly
            var connectionString = $"Data Source={dbPath}";
            
            using (var connection = new SqliteConnection(connectionString))
            {
                await connection.OpenAsync(cancellationToken);
                
                // Check if the table exists
                using (var command = connection.CreateCommand())
                {
                    command.CommandText = @"
                        SELECT name FROM sqlite_master 
                        WHERE type='table' AND name='sensor_readings'";
                    
                    var result = await command.ExecuteScalarAsync(cancellationToken);
                    if (result == null)
                    {
                        _logger.LogWarning("sensor_readings table not found in database");
                        return readings;
                    }
                }
                
                // Read data
                using (var command = connection.CreateCommand())
                {
                    command.CommandText = @"
                        SELECT id, sensor_id, timestamp, temperature, 
                               vibration, voltage, status_code, anomaly_flag,
                               anomaly_type, firmware_version, model, 
                               manufacturer, location
                        FROM sensor_readings
                        WHERE synced = 0
                        ORDER BY timestamp
                        LIMIT 10000";
                    
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
                                    sensorCodePart = $"S{DateTime.Now.ToString("HHmmss")}";
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
                                Processed = false
                            };
                            
                            readings.Add(reading);
                        }
                    }
                }
            }
            
            return readings;
        }

        private async Task DeleteProcessedDataAsync(string dbPath, CancellationToken cancellationToken)
        {
            var connectionString = $"Data Source={dbPath}";
            using (var connection = new SqliteConnection(connectionString))
            {
                await connection.OpenAsync(cancellationToken);
                
                using (var command = connection.CreateCommand())
                {
                    command.CommandText = "DELETE FROM sensor_readings WHERE synced = 1";
                    await command.ExecuteNonQueryAsync(cancellationToken);
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

        private async Task ArchiveReadingsAsync(List<SensorReading> readings, string sensorId, string location, CancellationToken cancellationToken)
        {
            try
            {
                /* 
                 * IMPORTANT NOTE ABOUT DIRECTORY STRUCTURE:
                 * In Docker setup, the archive path is mounted as:
                 * ./archive/{{ city_clean }}:/app/archive
                 * 
                 * This means each uploader container already has its archive path
                 * set to a city-specific directory. We need to ensure files are
                 * named correctly within that city directory.
                 */
                string cityName = location.Trim(); // For logging purposes
                
                // Ensure archive directory exists
                Directory.CreateDirectory(_archivePath);
                
                // Get the city abbreviation (first 3 letters, uppercase)
                string cityPrefix = "";
                if (!string.IsNullOrEmpty(cityName) && cityName.Length >= 3)
                {
                    // Remove any spaces or special characters
                    string cleanCity = new string(cityName.Where(c => char.IsLetterOrDigit(c) || c == '_').ToArray());
                    if (cleanCity.Contains('_'))
                    {
                        cleanCity = cleanCity.Split('_')[0]; // Take first part if it contains underscore
                    }
                    cityPrefix = cleanCity.Substring(0, Math.Min(3, cleanCity.Length)).ToUpper();
                }
                
                // Create a filename that includes the city prefix and preserves the sensor's identity
                string sensorCode = sensorId;
                
                // If sensorId doesn't have city prefix already, add it
                if (!sensorId.StartsWith(cityPrefix) && !string.IsNullOrEmpty(cityPrefix))
                {
                    sensorCode = $"{cityPrefix}_{sensorId}";
                }
                else if (string.IsNullOrEmpty(cityPrefix))
                {
                    // If we couldn't determine a city prefix, use the original sensorId
                    sensorCode = sensorId;
                }
                
                string filename = $"{sensorCode}.parquet";
                string fullPath = Path.Combine(_archivePath, filename);
                
                _logger.LogInformation("Archiving {Count} readings for sensor {SensorId} from {City} to {File}", 
                    readings.Count, sensorId, cityName, fullPath);
                
                // If file exists, read existing data
                List<SensorReading> existingReadings = new List<SensorReading>();
                if (File.Exists(fullPath))
                {
                    using (var fileStream = File.OpenRead(fullPath))
                    {
                        var deserialized = await ParquetSerializer.DeserializeAsync<SensorReading>(fileStream, cancellationToken: cancellationToken);
                        existingReadings = deserialized.ToList();
                    }
                }
                
                // Combine existing and new readings
                var allReadings = existingReadings.Concat(readings).ToList();
                
                // Write all readings to the file
                using (var fileStream = File.Create(fullPath))
                {
                    await ParquetSerializer.SerializeAsync(allReadings, fileStream, cancellationToken: cancellationToken);
                }
                
                _logger.LogInformation("Successfully archived {Count} readings for sensor {SensorId} to {File}", 
                    allReadings.Count, sensorId, fullPath);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error archiving readings to Parquet file for sensor {SensorId}: {Message}", 
                    sensorId, ex.Message);
                throw;
            }
        }

        private async Task ArchiveDatabaseAsync(string dbPath, CancellationToken cancellationToken)
        {
            try
            {
                _logger.LogInformation("Archiving database: {DbPath}", dbPath);

                // Read sensor data from the database
                var readings = await ReadSensorDataAsync(dbPath, cancellationToken);
                if (readings == null || readings.Count == 0)
                {
                    _logger.LogWarning("No readings found in database: {DbPath}", dbPath);
                    return;
                }

                // Extract metadata from the first reading for archiving
                var firstReading = readings[0];
                var sensorId = firstReading.SensorId;
                var location = firstReading.Location;
                
                _logger.LogInformation("Read {Count} readings from sensor {SensorId} in {Location}", 
                    readings.Count, sensorId, location);
                
                // Upload to Cosmos DB
                await _cosmosUploader.UploadReadingsAsync(readings, cancellationToken);
                
                // Archive the uploaded data if archive path is set
                if (!string.IsNullOrEmpty(_archivePath))
                {
                    await ArchiveReadingsAsync(readings, sensorId, location, cancellationToken);
                }
                
                // Delete processed data from SQLite
                await DeleteProcessedDataAsync(dbPath, cancellationToken);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error archiving database {DbPath}: {Message}", dbPath, ex.Message);
                throw;
            }
        }

        private void DeleteProcessedDatabase(string dbPath)
        {
            _logger.LogInformation("Deleting processed database: {DbPath}", dbPath);
            File.Delete(dbPath);
        }
    }
}
