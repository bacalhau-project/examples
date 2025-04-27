using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using System.Text.Json;
using CosmosUploader.Configuration;
using CosmosUploader.Models;
using Microsoft.Data.Sqlite;
using Microsoft.Extensions.Logging;

namespace CosmosUploader.Services
{
    // Helper class for status file content
    internal class ProcessingStatus
    {
        public string? LastProcessedTimestampIso { get; set; }
        public string? LastProcessedId { get; set; }
    }

    public class SqliteReader
    {
        private readonly ILogger<SqliteReader> _logger;
        private readonly AppSettings _settings;
        private string? _dataPath; // Add declaration for the data path field

        public SqliteReader(ILogger<SqliteReader> logger, AppSettings settings)
        {
            _logger = logger;
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

        public async Task<List<SensorReading>> ReadRawDataAsync(string dataPath, int limit, CancellationToken cancellationToken)
        {
            string dbPath = Path.GetFullPath(dataPath);
            string statusFilePath = GetStatusFilePath(dbPath);
            _logger.LogInformation("Reading next batch (Limit: {Limit}) from {DbPath} using status file {StatusFile}", limit, dbPath, statusFilePath);

            ProcessingStatus lastStatus = new ProcessingStatus(); // Default empty status
            try
            {
                if (File.Exists(statusFilePath))
                {
                    _logger.LogDebug("Reading last processing status from file: {StatusFile}", statusFilePath);
                    string jsonContent = await File.ReadAllTextAsync(statusFilePath, cancellationToken);
                    if (!string.IsNullOrWhiteSpace(jsonContent))
                    {
                        try
                        {
                            var statusFromFile = JsonSerializer.Deserialize<ProcessingStatus>(jsonContent);
                            if (statusFromFile != null)
                            {
                                lastStatus = statusFromFile;
                                _logger.LogInformation("Read last processed status: Timestamp={Timestamp}, ID={Id}", 
                                    lastStatus.LastProcessedTimestampIso ?? "N/A", lastStatus.LastProcessedId ?? "N/A");
                            }
                        }
                        catch (JsonException jsonEx)
                        {
                            _logger.LogWarning(jsonEx, "Error parsing JSON from status file {StatusFile}. Will read from the beginning.", statusFilePath);
                            // Proceed with empty lastStatus, effectively reading from start
                        }
                    }
                    else
                    {
                         _logger.LogInformation("Status file {StatusFile} is empty. Will read from the beginning.", statusFilePath);
                    }
                }
                else
                {
                    _logger.LogInformation("Status file not found ({StatusFile}). Will read from the beginning.", statusFilePath);
                }
            }
            catch (IOException ioEx)
            {
                 _logger.LogError(ioEx, "Error accessing status file {StatusFile}. Aborting read for {DbPath}.", statusFilePath, dbPath);
                 throw;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Unexpected error reading status file {StatusFile}. Aborting read for {DbPath}.", statusFilePath, dbPath);
                throw; 
            }

            // --- Prepare parameters for the query based on lastStatus ---
            DateTime lastTimestamp = DateTime.MinValue; // Default to earliest possible
            long lastId = -1; // Default to invalid ID
            double lastTimestampEpoch = -1.0;

            if (!string.IsNullOrEmpty(lastStatus.LastProcessedTimestampIso) && 
                DateTime.TryParse(lastStatus.LastProcessedTimestampIso, null, System.Globalization.DateTimeStyles.RoundtripKind, out DateTime parsedTimestamp))
            {
                lastTimestamp = parsedTimestamp;
                // Convert to Unix Epoch seconds (double) for SQLite REAL comparison
                lastTimestampEpoch = new DateTimeOffset(lastTimestamp).ToUnixTimeSeconds(); 
            }
            else if (!string.IsNullOrEmpty(lastStatus.LastProcessedTimestampIso))
            { 
                 _logger.LogWarning("Could not parse LastProcessedTimestampIso '{Timestamp}' from status file. Reading from beginning.", lastStatus.LastProcessedTimestampIso);
            }

            if (!string.IsNullOrEmpty(lastStatus.LastProcessedId) && long.TryParse(lastStatus.LastProcessedId, out long parsedId))
            {
                lastId = parsedId;
            }
             else if (!string.IsNullOrEmpty(lastStatus.LastProcessedId))
            { 
                 _logger.LogWarning("Could not parse LastProcessedId '{Id}' from status file. Reading from beginning if timestamp was also invalid.", lastStatus.LastProcessedId);
            }

            // --- Read the next batch directly using the status --- 
            List<SensorReading> batchReadings;
            try
            {
                // Pass parameters to ReadSensorDataBatchAsync
                batchReadings = await ReadSensorDataBatchAsync(dbPath, limit, lastTimestampEpoch, lastId, cancellationToken);

                if (batchReadings == null || !batchReadings.Any())
                {
                    _logger.LogInformation("No new sensor readings found in {DbPath} after Timestamp={Ts}, ID={Id}.", 
                        dbPath, lastStatus.LastProcessedTimestampIso ?? "Start", lastStatus.LastProcessedId ?? "Start");
                    return new List<SensorReading>();
                }

                _logger.LogInformation("Read {Count} new sensor readings for this cycle's batch (Limit: {Limit}) from {DbPath}.", batchReadings.Count, limit, dbPath);
            }
            catch (Exception ex)
            {
                 _logger.LogError(ex, "Error during batch read for database file: {DbPath}", dbPath);
                 throw; // Re-throw to allow Program.cs to handle it
            }

            // IMPORTANT: Status file update is handled in Program.cs after successful processing/archiving

            return batchReadings;
        }

        private async Task<List<SensorReading>> ReadSensorDataBatchAsync(string dbPath, int limit, double lastTimestampEpoch, long lastId, CancellationToken cancellationToken)
        {
            var readings = new List<SensorReading>();
            var connectionString = $"Data Source={dbPath}";

            using (var connection = new SqliteConnection(connectionString))
            {
                await connection.OpenAsync(cancellationToken);

                // Check if the table exists (optional, but good practice)
                using (var checkCmd = connection.CreateCommand())
                {
                    checkCmd.CommandText = "SELECT name FROM sqlite_master WHERE type='table' AND name='sensor_readings'";
                    if (await checkCmd.ExecuteScalarAsync(cancellationToken) == null)
                    {
                        _logger.LogWarning("sensor_readings table not found in database {DbPath}", dbPath);
                        return readings;
                    }
                }

                // Read data - Added WHERE clause based on timestamp/id, kept LIMIT
                using (var command = connection.CreateCommand())
                {
                    // Note: Assumes 'timestamp' column in SQLite is REAL or comparable numeric type
                    // And 'id' column is INTEGER
                    command.CommandText = $@"
                        SELECT id, timestamp, sensor_id, temperature, 
                               humidity, pressure, vibration, voltage, 
                               status_code, anomaly_flag, anomaly_type, 
                               firmware_version, model, manufacturer, 
                               location, latitude, longitude
                        FROM sensor_readings
                        WHERE (timestamp > @LastTimestamp OR (timestamp = @LastTimestamp AND id > @LastId))
                        ORDER BY timestamp, id -- CRITICAL for correct batching
                        LIMIT @Limit"; 
                    
                    command.Parameters.AddWithValue("@LastTimestamp", lastTimestampEpoch); // Pass epoch double
                    command.Parameters.AddWithValue("@LastId", lastId);
                    command.Parameters.AddWithValue("@Limit", limit);

                    _logger.LogDebug("Executing query: {Query} with LastTimestamp={Ts}, LastId={Id}, Limit={Lim}", 
                        command.CommandText, lastTimestampEpoch, lastId, limit);

                    string? lastLoggedSensorId = null; // Track the last sensor ID for which full log was printed
                    int currentSensorReadCount = 0; // Count reads for the current sensor

                    using (var reader = await command.ExecuteReaderAsync(cancellationToken))
                    {
                        while (await reader.ReadAsync(cancellationToken))
                        {
                            // Capture raw data first
                            var rawValues = new List<string?>();
                            for (int i = 0; i < reader.FieldCount; i++)
                            {
                                rawValues.Add(reader.IsDBNull(i) ? null : reader.GetValue(i)?.ToString());
                            }
                            string rawDataString = string.Join("|", rawValues.Select(v => v ?? string.Empty));

                            // --- Column Index Mapping based on the new SELECT ---
                            // 0: id (INTEGER) -> Read as string for HashSet compatibility
                            // 1: timestamp (REAL/TEXT) - Parsed by ParseDateTime
                            // 2: sensor_id (TEXT)
                            // 3: temperature (REAL)
                            // 4: humidity (REAL)
                            // 5: pressure (REAL)
                            // 6: vibration (REAL)
                            // 7: voltage (REAL)
                            // 8: status_code (INTEGER)
                            // 9: anomaly_flag (INTEGER)
                            // 10: anomaly_type (TEXT)
                            // 11: firmware_version (TEXT)
                            // 12: model (TEXT)
                            // 13: manufacturer (TEXT)
                            // 14: location (TEXT) - Used for deriving City/Location fallback
                            // 15: latitude (REAL)
                            // 16: longitude (REAL)
                            // ----------------------------------------------------

                            string dbRawId = reader.GetInt64(0).ToString(); // Read ID as string
                            string? dbTimestampStr = reader.IsDBNull(1) ? null : reader.GetValue(1).ToString(); // Read as string/object first for ParseDateTime
                            string? dbSensorId = reader.IsDBNull(2) ? null : reader.GetString(2);
                            double? dbTemperature = reader.IsDBNull(3) ? null : reader.GetDouble(3);
                            double? dbHumidity = reader.IsDBNull(4) ? null : reader.GetDouble(4);
                            double? dbPressure = reader.IsDBNull(5) ? null : reader.GetDouble(5);
                            double? dbVibration = reader.IsDBNull(6) ? null : reader.GetDouble(6);
                            double? dbVoltage = reader.IsDBNull(7) ? null : reader.GetDouble(7);
                            int? dbStatusCode = reader.IsDBNull(8) ? null : reader.GetInt32(8);
                            bool dbAnomalyFlag = !reader.IsDBNull(9) && reader.GetInt32(9) == 1;
                            string? dbAnomalyType = reader.IsDBNull(10) ? null : reader.GetString(10);
                            string? dbFirmwareVersion = reader.IsDBNull(11) ? null : reader.GetString(11);
                            string? dbModel = reader.IsDBNull(12) ? null : reader.GetString(12);
                            string? dbManufacturer = reader.IsDBNull(13) ? null : reader.GetString(13);
                            string? dbLocation = reader.IsDBNull(14) ? null : reader.GetString(14);
                            double? dbLatitude = reader.IsDBNull(15) ? null : reader.GetDouble(15);
                            double? dbLongitude = reader.IsDBNull(16) ? null : reader.GetDouble(16);

                            // Parse the directory path to extract meaningful info (fallback logic)
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

                            // Create a better sensor ID based on city and a unique suffix (fallback logic)
                            string uniqueSensorId;
                            if (!string.IsNullOrEmpty(dbSensorId) && !dbSensorId.Equals("SENSOR001", StringComparison.OrdinalIgnoreCase))
                            {
                                uniqueSensorId = dbSensorId; // Use database sensor ID if it's meaningful
                            }
                            else
                            {
                                // Generate a more meaningful ID using path components and file info
                                string cityCode = !string.IsNullOrEmpty(cityNameFromPath) ? cityNameFromPath.Substring(0, Math.Min(3, cityNameFromPath.Length)).ToUpper() : "UNK";
                                string sensorCodePart;
                                if (!string.IsNullOrEmpty(sensorCodeFromPath) && sensorCodeFromPath != "data" && !sensorCodeFromPath.EndsWith(".db"))
                                {
                                    sensorCodePart = sensorCodeFromPath;
                                }
                                else
                                {
                                    sensorCodePart = $"S{DateTime.Now.ToString("HHmmssfff")}";
                                }
                                uniqueSensorId = $"{cityCode}_{sensorCodePart}";
                            }

                            // Determine Location and City
                            // Prefer database location. Fallback to path-derived city name.
                            string finalLocation = !string.IsNullOrEmpty(dbLocation) ? dbLocation : cityNameFromPath;
                            string finalCity = !string.IsNullOrEmpty(dbLocation) ? dbLocation : cityNameFromPath; // Assuming location from DB can represent city too, adjust if needed.
                            // If DB location is structured like 'City, Detail' or similar, parse City here. For now, using the whole string or fallback.

                            // Determine Latitude and Longitude
                            // Prefer direct database columns. Fallback to parsing from location string (legacy logic removed as direct columns exist).
                            string? finalLat = dbLatitude?.ToString(CultureInfo.InvariantCulture);
                            string? finalLng = dbLongitude?.ToString(CultureInfo.InvariantCulture);


                            // --- Modified Debug Logging ---
                            if (uniqueSensorId != lastLoggedSensorId)
                            {
                                // If we were tracking a previous sensor, log its final count
                                if (lastLoggedSensorId != null && currentSensorReadCount > 0)
                                {
                                    Console.WriteLine(); // Newline after dots
                                    _logger.LogDebug("... completed reading {Count} records for sensor {SensorId}", currentSensorReadCount, lastLoggedSensorId);
                                }

                                // Log the full message for the new sensor
                                _logger.LogDebug(
                                    "Reading data for sensor: dbSensorId={DbSensorId}, pathSensorId={PathSensorId}, " +
                                    "dbLocation={DbLocation}, pathLocation={PathLocation}, final sensorId={FinalSensorId}, final location={FinalLocation}, finalCity={FinalCity}",
                                    dbSensorId, $"{cityNameFromPath}_{sensorCodeFromPath}", dbLocation, cityNameFromPath, uniqueSensorId, finalLocation, finalCity);
                                
                                lastLoggedSensorId = uniqueSensorId;
                                currentSensorReadCount = 1; // Reset count for the new sensor
                            }
                            else
                            {
                                // Print a dot for subsequent reads of the same sensor
                                Console.Write(".");
                                currentSensorReadCount++;
                            }
                            // --- End Modified Debug Logging ---


                            var reading = new SensorReading
                            {
                                Id = dbRawId, // Store ID as string
                                SensorId = uniqueSensorId,
                                Timestamp = ParseDateTime(dbTimestampStr ?? DateTime.UtcNow.ToString()), // Handle potential null timestamp string
                                Temperature = dbTemperature,
                                Humidity = dbHumidity, // Assign Humidity
                                Pressure = dbPressure, // Assign Pressure
                                Vibration = dbVibration,
                                Voltage = dbVoltage,
                                Status = dbStatusCode?.ToString() ?? "unknown", // Use db value or default
                                AnomalyFlag = dbAnomalyFlag,
                                AnomalyType = dbAnomalyType,
                                FirmwareVersion = dbFirmwareVersion,
                                Model = dbModel,
                                Manufacturer = dbManufacturer,
                                Location = finalLocation, // Use determined location
                                City = finalCity,         // Use determined city
                                Lat = finalLat,           // Use determined lat
                                Long = finalLng,          // Use determined lng
                                RawData = rawDataString
                            };

                            readings.Add(reading);
                        }

                        // Log the final count for the last sensor processed in the loop
                        if (lastLoggedSensorId != null && currentSensorReadCount > 0)
                        {
                             if (currentSensorReadCount > 1) // Only add newline if dots were printed
                             {
                                Console.WriteLine(); // Newline after dots
                             }
                            _logger.LogDebug("... completed reading {Count} records for sensor {SensorId}", currentSensorReadCount, lastLoggedSensorId);
                        }
                    }
                }
            }
            _logger.LogDebug("Finished reading batch. Found {Count} records.", readings.Count);
            return readings;
        }

        private string GetStatusFilePath(string dbPath)
        {
            string? directory = Path.GetDirectoryName(dbPath);
            string dbFileNameWithoutExt = Path.GetFileNameWithoutExtension(dbPath);
            string statusFileName = $"{dbFileNameWithoutExt}{_settings.StatusFileSuffix}";

            if (string.IsNullOrEmpty(directory))
            {
                // Fallback if directory is somehow null (e.g., dbPath is just a filename)
                return statusFileName;
            }
            return Path.Combine(directory, statusFileName);
        }

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
    }
}
