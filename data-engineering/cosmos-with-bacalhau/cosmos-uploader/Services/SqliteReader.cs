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

        private async Task ProcessDatabaseAsync(string dbFile, CancellationToken cancellationToken)
        {
            _logger.LogInformation("Processing database: {Database}", dbFile);
            
            try
            {
                var connectionString = $"Data Source={dbFile}";
                List<SensorReading> readings = await ReadSensorDataAsync(connectionString, cancellationToken);
                
                if (readings.Count > 0)
                {
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
                    await DeleteProcessedDataAsync(connectionString, cancellationToken);
                }
                else
                {
                    _logger.LogInformation("No new readings to process in {Database}", dbFile);
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error processing database {Database}", dbFile);
                throw;
            }
        }

        private async Task<List<SensorReading>> ReadSensorDataAsync(string connectionString, CancellationToken cancellationToken)
        {
            var readings = new List<SensorReading>();
            
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
                        SELECT id, sensor_id, timestamp, temperature, humidity, 
                               pressure, vibration, voltage, status, location
                        FROM sensor_readings
                        WHERE processed = 0
                        ORDER BY timestamp
                        LIMIT 10000";
                    
                    using (var reader = await command.ExecuteReaderAsync(cancellationToken))
                    {
                        while (await reader.ReadAsync(cancellationToken))
                        {
                            var reading = new SensorReading
                            {
                                Id = reader.GetString(0),
                                SensorId = reader.GetString(1),
                                Timestamp = DateTime.Parse(reader.GetString(2), CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal),
                                Temperature = reader.IsDBNull(3) ? null : reader.GetDouble(3),
                                Humidity = reader.IsDBNull(4) ? null : reader.GetDouble(4),
                                Pressure = reader.IsDBNull(5) ? null : reader.GetDouble(5),
                                Vibration = reader.IsDBNull(6) ? null : reader.GetDouble(6),
                                Voltage = reader.IsDBNull(7) ? null : reader.GetDouble(7),
                                Status = reader.IsDBNull(8) ? "unknown" : reader.GetString(8),
                                Location = reader.IsDBNull(9) ? "unknown" : reader.GetString(9),
                                City = reader.IsDBNull(9) ? "unknown" : reader.GetString(9),
                                Processed = false
                            };
                            
                            readings.Add(reading);
                        }
                    }
                }
            }
            
            return readings;
        }

        private async Task DeleteProcessedDataAsync(string connectionString, CancellationToken cancellationToken)
        {
            using (var connection = new SqliteConnection(connectionString))
            {
                await connection.OpenAsync(cancellationToken);
                
                using (var command = connection.CreateCommand())
                {
                    // Update processed flag
                    command.CommandText = @"
                        UPDATE sensor_readings
                        SET processed = 1
                        WHERE processed = 0";
                    
                    int rowsAffected = await command.ExecuteNonQueryAsync(cancellationToken);
                    _logger.LogInformation("Marked {Count} readings as processed", rowsAffected);
                    
                    // Optionally perform vacuum to reclaim space
                    command.CommandText = "VACUUM";
                    await command.ExecuteNonQueryAsync(cancellationToken);
                }
            }
        }

        private async Task ArchiveReadingsAsync(List<SensorReading> readings, string sensorId, string location, CancellationToken cancellationToken)
        {
            try
            {
                // Create a timestamped filename
                string timestamp = DateTime.UtcNow.ToString("yyyyMMdd_HHmmss");
                string region = location.Replace(" ", "_");
                string filename = $"{region}_{sensorId}_{timestamp}.parquet";
                string fullPath = Path.Combine(_archivePath, filename);
                
                _logger.LogInformation("Archiving {Count} readings to {File}", readings.Count, fullPath);
                
                // Write the readings to Parquet file using a FileStream
                using (var fileStream = File.Create(fullPath))
                {
                    await ParquetSerializer.SerializeAsync(readings, fileStream, cancellationToken: cancellationToken);
                }
                
                _logger.LogInformation("Successfully archived readings to {File}", fullPath);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error archiving readings to Parquet file");
                throw;
            }
        }
    }
}
