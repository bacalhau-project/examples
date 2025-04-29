using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using CosmosUploader.Configuration;
using CosmosUploader.Models;
using Microsoft.Extensions.Logging;
using Parquet;
using Parquet.Serialization;

namespace CosmosUploader.Services
{
    public class Archiver
    {
        private readonly ILogger<Archiver> _logger;
        private readonly AppSettings _settings; // AppSettings might be needed for future config, include for consistency

        public Archiver(ILogger<Archiver> logger, AppSettings settings)
        {
            _logger = logger;
            _settings = settings;
        }

        // Renamed from ArchiveReadingsBatchAsync and moved from SqliteReader
        public async Task ArchiveAsync(List<SensorReading> readings, string archivePath, CancellationToken cancellationToken)
        {
            if (string.IsNullOrEmpty(archivePath))
            {
                _logger.LogError("Archive path cannot be null or empty. Skipping archiving.");
                return;
            }
            if (readings == null || !readings.Any())
            {
                _logger.LogInformation("No readings provided to archive.");
                return;
            }

            // Ensure archive directory exists
            try
            {
                if (!Directory.Exists(archivePath))
                {
                    _logger.LogInformation("Archive directory does not exist, attempting to create: {Path}", archivePath);
                    Directory.CreateDirectory(archivePath);
                    _logger.LogInformation("Successfully created archive directory: {Path}", archivePath);
                }
                else
                {
                    _logger.LogDebug("Archive directory already exists: {Path}", archivePath);
                }
            }
            catch (UnauthorizedAccessException)
            {
                _logger.LogCritical("Permission denied: Cannot create archive directory: {Path}. Please check permissions. Exiting.", archivePath);
                // Re-throw a specific, commonly handled exception to signal failure upward
                throw new DirectoryNotFoundException($"Permission denied for archive directory: {archivePath}");
            }
            catch (IOException ioEx) // Catch other IO errors like invalid path, disk full etc.
            {
                 _logger.LogCritical("IO Error creating archive directory: {Path}. Reason: {Reason}. Exiting.", archivePath, ioEx.Message);
                 // Re-throw to signal failure
                 throw new DirectoryNotFoundException($"Failed to create archive directory due to IO error: {archivePath}");
            }
            catch (Exception ex) // Catch unexpected errors
            {
                _logger.LogCritical("Unexpected error creating archive directory: {Path}. Reason: {Reason}. Exiting.", archivePath, ex.Message);
                 // Re-throw to signal failure
                throw new DirectoryNotFoundException($"Unexpected error creating archive directory: {archivePath}");
            }

            _logger.LogInformation("Starting archiving of {Count} raw readings to {Path}...", readings.Count, archivePath);

            // Group by sensor ID and Location for batch archiving (filename determination)
            var groupedForArchive = readings.GroupBy(r => new { r.SensorId, r.Location });

            foreach (var group in groupedForArchive)
            {
                cancellationToken.ThrowIfCancellationRequested();

                string sensorId = group.Key.SensorId;
                string location = group.Key.Location;
                var readingsInGroup = group.ToList();

                if (string.IsNullOrEmpty(sensorId) || string.IsNullOrEmpty(location))
                {
                    _logger.LogWarning("Skipping archive for {Count} readings with missing SensorId or Location.", readingsInGroup.Count);
                    continue;
                }

                try
                {
                    // Generate filename based on SensorId and Location (similar logic as before)
                    string cityName = location.Trim();
                    string cityPrefix = "";
                    if (!string.IsNullOrEmpty(cityName) && cityName.Length >= 3)
                    {
                        // Basic sanitization for filename part
                        string cleanCity = new string(cityName.Where(c => char.IsLetterOrDigit(c) || c == '_').ToArray());
                        // Handle cases like 'New_York' -> 'New'
                        if (cleanCity.Contains('_')) { cleanCity = cleanCity.Split('_')[0]; }
                        // Take first 3 chars for prefix
                        cityPrefix = cleanCity.Substring(0, Math.Min(3, cleanCity.Length)).ToUpperInvariant();
                    }
                    string sensorCode = sensorId;
                    // Prefix sensor ID with city code if not already present
                    if (!sensorId.StartsWith(cityPrefix, StringComparison.OrdinalIgnoreCase) && !string.IsNullOrEmpty(cityPrefix))
                    { 
                        sensorCode = $"{cityPrefix}_{sensorId}"; 
                    }
                    else if (string.IsNullOrEmpty(cityPrefix))
                    { 
                        // Use sensorId directly if no city prefix could be generated
                        sensorCode = sensorId; 
                    }

                    string filename = $"{sensorCode}.parquet";
                    string fullPath = Path.Combine(archivePath, filename);

                    _logger.LogDebug("Archiving {Count} readings for sensor {SensorId} (Group Key) to {File}",
                        readingsInGroup.Count, sensorId, fullPath);

                    List<SensorReading> existingReadings = new List<SensorReading>();
                    if (File.Exists(fullPath))
                    {
                        _logger.LogDebug("Appending to existing archive file: {File}", fullPath);
                        try
                        {
                            using (var fileStream = File.OpenRead(fullPath))
                            {
                                // Use ParquetSerializer.DeserializeAsync
                                var deserialized = await ParquetSerializer.DeserializeAsync<SensorReading>(fileStream, cancellationToken: cancellationToken);
                                existingReadings = deserialized.ToList();
                                _logger.LogDebug("Read {ExistingCount} existing records from {File}", existingReadings.Count, fullPath);
                            }
                        }
                        catch (Exception ex)
                        {
                            _logger.LogWarning(ex, "Failed to read existing parquet file {File}. It might be corrupted or locked. Will attempt to overwrite.", fullPath);
                            existingReadings.Clear(); // Clear if read fails to avoid data loss
                        }
                    }
                    else
                    {
                        _logger.LogDebug("Creating new archive file: {File}", fullPath);
                    }

                    // Combine existing and new readings
                    var allReadings = existingReadings.Concat(readingsInGroup).ToList();

                    try
                    {
                        // Use a temporary file and rename for atomic write
                        string tempPath = fullPath + ".tmp";
                        using (var fileStream = File.Create(tempPath))
                        {
                            // Use ParquetSerializer.SerializeAsync
                           await ParquetSerializer.SerializeAsync(allReadings, fileStream, cancellationToken: cancellationToken);
                        }
                        File.Move(tempPath, fullPath, true); // Overwrite if exists

                        _logger.LogDebug("Successfully archived/appended {Count} total readings for sensor {SensorId} to {File}",
                            allReadings.Count, sensorId, fullPath);
                    }
                    catch (IOException ioEx)
                    {
                        _logger.LogError(ioEx, "IO Error writing/renaming parquet file {File} for sensor {SensorId}. Archive for this batch might be lost.", fullPath, sensorId);
                        // Consider retry logic or marking these records as failed to archive
                    }
                    catch (Exception ex)
                    {
                        _logger.LogError(ex, "Error serializing parquet file {File} for sensor {SensorId}. Archive for this batch might be lost.", fullPath, sensorId);
                    }
                }
                catch (Exception ex)
                { // Catch errors during filename generation or grouping logic
                    _logger.LogError(ex, "Error preparing archive for sensor group (SensorId: {SensorId}, Location: {Location}): {Message}", sensorId, location, ex.Message);
                }
            }
             _logger.LogInformation("Finished archiving batch of {Count} readings.", readings.Count);
        }
    }
} 