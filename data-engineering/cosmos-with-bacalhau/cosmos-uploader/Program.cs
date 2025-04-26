using System;
using System.Collections.Generic; // Added for List
using System.CommandLine;
using System.IO;
using System.Linq; // Added for LINQ operations
using System.Threading;
using System.Threading.Tasks;
using System.Text.Json; // <-- Add using for JSON
using CosmosUploader.Configuration;
using CosmosUploader.Models; // Added for SensorReading
using CosmosUploader.Services;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Console;
using Microsoft.Extensions.Logging.Abstractions;
using CosmosUploader.Processors; // Add using for processors

namespace CosmosUploader
{
    class Program
    {
        // Define known processor names (excluding Aggregate)
        private static readonly HashSet<string> KnownProcessors = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            "Schematize", "Sanitize" // Removed "Aggregate"
        };
        // private const string AggregateProcessorName = "Aggregate"; // No longer needed here

        // Add this helper class (or move it to a Models/Common file if preferred)
        internal class ProcessingStatus
        {
            public string? LastProcessedTimestampIso { get; set; }
            public string? LastProcessedId { get; set; }
        }

        static async Task<int> Main(string[] args)
        {
            // Set up command line arguments
            var rootCommand = new RootCommand(
                "Azure Cosmos DB Uploader for sensor data. " +
                "Processes data using a pipeline defined in the config file, optionally followed by aggregation. " +
                $"Available pipeline processors: {string.Join(", ", KnownProcessors)}."
            );

            var configOption = new Option<string>(
                name: "--config",
                description: "Path to the YAML configuration file");
            configOption.IsRequired = true;
            rootCommand.AddOption(configOption);

            var sqliteOption = new Option<string>(
                name: "--sqlite",
                description: "Path to a single SQLite database file");
            sqliteOption.IsRequired = true;
            rootCommand.AddOption(sqliteOption);

            var continuousOption = new Option<bool>(
                name: "--continuous",
                description: "Run in continuous mode, polling for new data");
            rootCommand.AddOption(continuousOption);

            var intervalOption = new Option<int>(
                name: "--interval",
                description: "Interval in seconds between upload attempts in continuous mode",
                getDefaultValue: () => 60);
            rootCommand.AddOption(intervalOption);

            var archivePathOption = new Option<string>(
                name: "--archive-path",
                description: "Path to archive uploaded data");
            rootCommand.AddOption(archivePathOption);

            var developmentOption = new Option<bool>(
                name: "--development",
                description: "Enable development mode (generates random IDs and uses current timestamp)",
                getDefaultValue: () => false);
            rootCommand.AddOption(developmentOption);

            // Add debug option
            var debugOption = new Option<bool>(
                name: "--debug",
                description: "Enable verbose debug logging.",
                getDefaultValue: () => false);
            rootCommand.AddOption(debugOption);

            // Transformation options are now controlled via the config file

            // Configure command handler
            rootCommand.SetHandler((Func<string, string, bool, int, string?, bool, bool, Task<int>>)(async (configPath, sqlitePath, continuous, interval, archivePath, developmentMode, debug) =>
            {
                // Build services initial setup
                var services = new ServiceCollection();
                services.AddLogging(builder =>
                {
                    builder.ClearProviders();
                    builder.AddConsole(options => { options.FormatterName = "custom"; })
                           .AddConsoleFormatter<CustomFormatter, SimpleConsoleFormatterOptions>();
                    // Set initial default level - will be overridden after config load if not debugging
                    builder.SetMinimumLevel(LogLevel.Information);
                });

                var initialServiceProvider = services.BuildServiceProvider();
                var initialLogger = initialServiceProvider.GetRequiredService<ILogger<Program>>(); // Use this for early logging

                // Moved stage validation *after* config loading

                // Add configuration
                YamlConfigurationProvider? configProvider = null;
                CosmosConfig? config = null;
                AppSettings? appSettings = null;
                List<string> configuredProcessors = new List<string>(); // Initialize empty list
                TimeSpan? aggregationWindow = null; // Initialize nullable TimeSpan

                try
                {
                    configProvider = new YamlConfigurationProvider(configPath, initialServiceProvider.GetRequiredService<ILogger<YamlConfigurationProvider>>());
                    config = configProvider.GetConfiguration();

                    // --- Validate and retrieve Processor List (Pipeline Processors) ---
                    configuredProcessors = config?.Processing?.Processors ?? new List<string>(); // Default to empty if null

                    if (configuredProcessors.Any())
                    {
                        initialLogger.LogInformation("Configured processing pipeline: [{Processors}]", string.Join(" -> ", configuredProcessors));

                        // Validation 1: Check for unknown processors (excluding Aggregate)
                        var unknownProcessors = configuredProcessors.Where(p => !KnownProcessors.Contains(p)).ToList();
                        if (unknownProcessors.Any())
                        {
                            initialLogger.LogCritical("Invalid configuration: Unknown processor(s) specified in 'processors' list: {Unknown}. Known pipeline processors are: {Known}",
                                string.Join(", ", unknownProcessors), string.Join(", ", KnownProcessors));
                            Console.Error.WriteLine($"ERROR: Unknown processor(s) found in config 'processors': {string.Join(", ", unknownProcessors)}. Valid names: {string.Join(", ", KnownProcessors)}");
                            return 1;
                        }

                        // Validation 2: Removed check for 'Aggregate' position
                    }
                    else
                    {
                        initialLogger.LogInformation("No pipeline processors configured.");
                    }

                    // --- Validate and parse Aggregation configuration ---
                    var aggregationConfig = config?.Processing?.Aggregation;
                    if (aggregationConfig != null)
                    {
                        if (string.IsNullOrWhiteSpace(aggregationConfig.Window))
                        {
                             initialLogger.LogCritical("Invalid configuration: 'aggregation' section found but 'window' is missing or empty.");
                             Console.Error.WriteLine("ERROR: 'aggregation.window' is required in the config file if the 'aggregation' section is present.");
                             return 1;
                        }

                        // Attempt to parse the window string (e.g., "30s", "5m", "1h")
                        // Using System.ComponentModel.TimeSpanConverter for flexibility
                        try
                        {
                            var converter = new System.ComponentModel.TimeSpanConverter();
                            aggregationWindow = (TimeSpan?)converter.ConvertFromString(aggregationConfig.Window);

                            if (aggregationWindow <= TimeSpan.Zero)
                            {
                                initialLogger.LogCritical("Invalid configuration: Aggregation window '{Window}' must be a positive time duration.", aggregationConfig.Window);
                                Console.Error.WriteLine($"ERROR: Aggregation window '{aggregationConfig.Window}' must be positive.");
                                return 1;
                            }
                            initialLogger.LogInformation("Aggregation configured with window: {Window}", aggregationWindow);
                        }
                        catch (Exception ex)
                        {
                            initialLogger.LogCritical(ex, "Invalid configuration: Could not parse aggregation window '{Window}'. Example formats: 30s, 5m, 1.5h", aggregationConfig.Window);
                            Console.Error.WriteLine($"ERROR: Invalid format for aggregation window '{aggregationConfig.Window}'. Use formats like '30s', '5m', '1h'.");
                            return 1;
                        }
                    }
                    else
                    {
                        initialLogger.LogInformation("Aggregation not configured.");
                    }

                    // --- Map to canonical AppSettings (defined in Configuration/AppSettings.cs) ---
                    // Ensure config parts are not null before assigning
                    if (config?.Cosmos == null || config.Performance == null || config.Logging == null)
                    {
                        throw new InvalidOperationException("Core configuration sections (Cosmos, Performance, Logging) are missing in the config file.");
                    }

                    appSettings = new AppSettings
                    {
                        // Assign existing config objects directly
                        Cosmos = config.Cosmos,
                        Performance = config.Performance,
                        Logging = config.Logging, // Assign the existing LoggingSettings object

                        // Map other direct properties
                        DevelopmentMode = developmentMode,
                        DebugMode = debug,
                        Processors = configuredProcessors, // Assign the validated processor list
                        AggregationWindow = aggregationWindow, // Assign the parsed aggregation window
                        StatusFileSuffix = "_processing_status.json" // Set the status file suffix here
                    };

                    // --- Update logging level based on debug flag ---
                    services.AddLogging(builder =>
                    {
                        LogLevel effectiveLevel;
                        if (debug)
                        {
                            effectiveLevel = LogLevel.Debug;
                            initialLogger.LogDebug("--debug flag detected, setting minimum log level to Debug.");
                        }
                        else
                        {
                            // Use the level from the config object directly
                            effectiveLevel = Enum.TryParse<LogLevel>(config?.Logging?.Level ?? "Information", true, out var configLevel)
                                                ? configLevel
                                                : LogLevel.Information; // Default to Info if parsing fails
                        }
                        builder.SetMinimumLevel(effectiveLevel);
                        // Update AppSettings logging level if it wasn't set correctly initially
                        appSettings.Logging.Level = effectiveLevel.ToString();
                    });

                    services.AddSingleton(appSettings); // Add mapped settings
                    services.AddSingleton(config);      // Add raw config if needed elsewhere

                    // Register services
                    // Register SqliteReader as itself
                    services.AddTransient<SqliteReader>();
                    // Register ProcessData as itself
                    services.AddTransient<ProcessData>();
                    // Register Archiver as itself
                    services.AddTransient<Archiver>();
                    // Register CosmosUploader with its interface
                    services.AddTransient<ICosmosUploader, Services.CosmosUploader>();

                    // --- Register Processors based on the configured PIPELINE list ---
                    if (configuredProcessors.Any(p => StringComparer.OrdinalIgnoreCase.Equals(p, "Schematize")))
                    {
                        services.AddTransient<ISchemaProcessor, SchemaProcessor>();
                        initialLogger.LogDebug("Registering SchemaProcessor based on configuration.");
                    }
                    if (configuredProcessors.Any(p => StringComparer.OrdinalIgnoreCase.Equals(p, "Sanitize")))
                    {
                        services.AddTransient<ISanitizeProcessor, SanitizeProcessor>();
                        initialLogger.LogDebug("Registering SanitizeProcessor based on configuration.");
                    }
                    // Removed registration trigger for Aggregate here

                    // --- Register Aggregation Processor conditionally ---
                    if (aggregationWindow.HasValue)
                    {
                        // Provide the window to the constructor via factory
                        services.AddTransient<IAggregateProcessor>(sp => 
                            new AggregateProcessor(
                                sp.GetRequiredService<ILogger<AggregateProcessor>>(), 
                                aggregationWindow.Value // Pass the parsed window
                            )
                        );
                        initialLogger.LogDebug("Registering AggregateProcessor as aggregation is configured with window {Window}.", aggregationWindow.Value);
                    }
                }
                catch (Exception ex)
                {
                    // Use final logger instance if available, else initialLogger
                    var loggerToUse = initialLogger; // Logger might not be fully configured yet
                    // Cannot safely build service provider here if it failed during setup
                    loggerToUse.LogCritical(ex, "Failed during configuration setup: {Message}", ex.Message);
                    return 1; // Return error code
                }

                // Build the final service provider
                var serviceProvider = services.BuildServiceProvider();
                // Ensure logger uses the final provider's configuration
                var logger = serviceProvider.GetRequiredService<ILogger<Program>>();

                // Resolve concrete service types needed for orchestration
                var sqliteReader = serviceProvider.GetRequiredService<SqliteReader>();
                var processDataService = serviceProvider.GetRequiredService<ProcessData>();
                var cosmosUploaderService = serviceProvider.GetRequiredService<ICosmosUploader>();
                var archiverService = serviceProvider.GetRequiredService<Archiver>();
                var settings = serviceProvider.GetRequiredService<AppSettings>();

                // CancellationToken setup
                var cts = new CancellationTokenSource();
                Console.CancelKeyPress += (sender, e) =>
                {
                    logger.LogWarning("Cancellation requested via Ctrl+C.");
                    e.Cancel = true; // Prevent process termination immediately
                    cts.Cancel();
                };

                // Determine archive path - Use provided option or default relative to the directory containing the sqlite path
                string baseDirectoryPath = Path.GetDirectoryName(Path.GetFullPath(sqlitePath)) ?? "."; // Get full path first to handle relative paths correctly
                string defaultArchivePath = Path.Combine(baseDirectoryPath, "archive");
                string effectiveArchivePath = archivePath ?? defaultArchivePath;
                logger.LogInformation("Using archive path: {ArchivePath}", effectiveArchivePath);

                // Main processing loop (single run or continuous)
                do
                {
                    try
                    {
                        logger.LogInformation("Starting data processing cycle...");

                        // Determine if sqlitePath is a file or directory
                        List<string> dbFilesToProcess = new List<string>();
                        if (Directory.Exists(sqlitePath))
                        {
                            logger.LogDebug("Specified SQLite path is a directory: {DirectoryPath}. Searching for *.db files...", sqlitePath);
                            dbFilesToProcess.AddRange(Directory.GetFiles(sqlitePath, "*.db"));
                        }
                        else if (File.Exists(sqlitePath))
                        {
                            // Check if the file has a .db extension (optional, but good practice)
                            if (Path.GetExtension(sqlitePath).Equals(".db", StringComparison.OrdinalIgnoreCase))
                            {
                                logger.LogDebug("Specified SQLite path is a single file: {FilePath}", sqlitePath);
                                dbFilesToProcess.Add(sqlitePath);
                            }
                            else
                            {
                                logger.LogWarning("Specified SQLite path is a file but does not have a .db extension: {FilePath}. Skipping.", sqlitePath);
                            }
                        }
                        else
                        {
                            logger.LogError("Specified SQLite path does not exist or is not accessible: {SqlitePath}", sqlitePath);
                        }

                        if (!dbFilesToProcess.Any())
                        {
                            logger.LogWarning("No SQLite files found to process in the specified path: {PathInput}", sqlitePath);
                        }
                        else
                        {
                            logger.LogInformation("Found {Count} database file(s) to process.", dbFilesToProcess.Count);
                            // Process each database file found
                            foreach (var dbPath in dbFilesToProcess)
                            {
                                if (cts.IsCancellationRequested) break;
                                logger.LogInformation("Processing database file: {DbPath}", dbPath);

                                try
                                {
                                    const int batchSize = 1000; // Max records to read/process per file per cycle

                                    // 1. Read ONE Batch (Max 10k)
                                    logger.LogInformation("Attempting to read up to {BatchSize} records from {DbPath}...", batchSize, dbPath);
                                    // Offset is 0, relying on the synced flag logic within SqliteReader
                                    List<SensorReading> rawReadingsBatch = await sqliteReader.ReadRawDataAsync(dbPath, batchSize, cts.Token);

                                    if (!rawReadingsBatch.Any())
                                    {
                                        logger.LogInformation("No new raw data found in {DbPath} for this cycle.", dbPath);
                                        continue; // Move to the next file
                                    }

                                    logger.LogInformation("Read {Count} raw records from {DbPath}. Processing this batch...", rawReadingsBatch.Count, dbPath);

                                    // 2. Process Data Batch
                                    logger.LogDebug("Processing batch ({Count} records)...", rawReadingsBatch.Count);
                                    List<DataTypes.DataItem> processedDataBatch = await processDataService.ProcessAsync(rawReadingsBatch, cts.Token);

                                    if (!processedDataBatch.Any())
                                    {
                                        logger.LogWarning("Processing resulted in zero records for upload from {DbPath}. Raw data will still be archived.", dbPath);
                                        // Proceed to archive step even if processing yields nothing
                                    }
                                    else
                                    {
                                        logger.LogInformation("Processing completed. {Count} records ready for upload.", processedDataBatch.Count);
                                    }

                                    // 3. Upload Processed Data Batch (if any)
                                    if (processedDataBatch.Any())
                                    {
                                        logger.LogDebug("Uploading batch ({Count} processed records) to Cosmos DB...", processedDataBatch.Count);
                                        await cosmosUploaderService.UploadDataAsync(processedDataBatch, dbPath, cts.Token);
                                        logger.LogInformation("Successfully initiated upload for batch ({Count} processed records) from {DbPath}.", processedDataBatch.Count, dbPath);
                                    }

                                    // 4. Archive Raw Data Batch
                                    logger.LogDebug("Archiving batch ({Count} raw records) to {ArchivePath}...", rawReadingsBatch.Count, effectiveArchivePath);
                                    await archiverService.ArchiveAsync(rawReadingsBatch, effectiveArchivePath, cts.Token);
                                    logger.LogInformation("Successfully initiated archiving for batch ({Count} raw records) from {DbPath}.", rawReadingsBatch.Count, dbPath);

                                    // 5. Update Status File with Last Processed Item (JSON)
                                    try
                                    {
                                        if (rawReadingsBatch.Any()) // Only update if we processed something
                                        {
                                            string statusFilePath = GetStatusFilePath(dbPath);
                                            // Get the last record based on the order from SqliteReader (timestamp, id)
                                            SensorReading lastRecord = rawReadingsBatch.Last(); 
                                            
                                            // Create the new status object
                                            var newStatus = new ProcessingStatus
                                            {
                                                // Format Timestamp in ISO 8601 Round-trip format
                                                LastProcessedTimestampIso = lastRecord.Timestamp.ToUniversalTime().ToString("o"), 
                                                LastProcessedId = lastRecord.Id
                                            };

                                            // Serialize and overwrite the status file
                                            string updatedJson = JsonSerializer.Serialize(newStatus, new JsonSerializerOptions { WriteIndented = true });
                                            await File.WriteAllTextAsync(statusFilePath, updatedJson, cts.Token);

                                            logger.LogInformation("Successfully updated status file {StatusFile} with LastTimestamp={Ts}, LastId={Id}", 
                                                statusFilePath, newStatus.LastProcessedTimestampIso, newStatus.LastProcessedId);
                                        }
                                        else
                                        {
                                            // Optional: Log that status file wasn't updated because no records were processed
                                            logger.LogDebug("No records in the processed batch for {DbPath}. Status file not updated.", dbPath);
                                        }
                                    }
                                    catch (Exception ex)
                                    {
                                        // Log error but don't stop the whole process, as the data *was* processed and archived.
                                        // However, this means duplicates might be processed next time.
                                        logger.LogError(ex, "Failed to update status file {StatusFile} for {DbPath}. Potential for reprocessing duplicates on next run.", GetStatusFilePath(dbPath), dbPath);
                                    }

                                    logger.LogInformation("Finished processing batch for database file: {DbPath}", dbPath);
                                    // End of processing for this file IN THIS CYCLE. If more data exists, it's handled next time.
                                }
                                catch (OperationCanceledException)
                                {
                                    logger.LogWarning("Processing cancelled for database file: {DbPath}", dbPath);
                                    break; // Exit file loop if cancelled
                                }
                                catch (DirectoryNotFoundException dirEx) when (dirEx.Message.Contains("archive directory")) // Catch specific archive creation failure
                                {
                                    logger.LogCritical("Archive directory creation failed: {Reason} - Cannot continue.", dirEx.Message);
                                    cts.Cancel(); // Trigger cancellation for other operations/continuous mode exit
                                    return 1; // Exit the application with an error code
                                }
                                catch (Exception ex)
                                {
                                    logger.LogError(ex, "Error processing database file {DbPath}. Skipping this file for the current cycle.", dbPath);
                                    // Continue to the next file in this cycle
                                }
                            }
                        }
                    }
                    catch (OperationCanceledException)
                    {
                        logger.LogWarning("Processing cycle cancelled.");
                        break; // Exit main loop if cancelled
                    }
                    catch (Exception ex)
                    {
                        logger.LogCritical(ex, "An unexpected error occurred during the processing cycle: {Message}", ex.Message);
                        // Depending on the error, might decide to break or continue
                        if (!continuous) return 1; // Exit if not in continuous mode
                    }

                    if (continuous)
                    {
                        if (cts.IsCancellationRequested)
                        {
                             logger.LogInformation("Continuous mode cancelled. Exiting.");
                             break;
                        }
                        logger.LogInformation("Continuous mode enabled. Waiting {Interval} seconds before next cycle...", interval);
                        await Task.Delay(TimeSpan.FromSeconds(interval), cts.Token);
                    }
                } while (continuous && !cts.IsCancellationRequested);

                logger.LogInformation("CosmosUploader finished.");
                return 0; // Success
            }), configOption, sqliteOption, continuousOption, intervalOption, archivePathOption, developmentOption, debugOption);

            return await rootCommand.InvokeAsync(args);
        }

        // Helper function to get status file path (Updated Suffix)
        private static string GetStatusFilePath(string dbPath)
        {
            const string StatusFileSuffix = "_processing_status.json"; // New suffix
            string? directory = Path.GetDirectoryName(dbPath);
            string dbFileNameWithoutExt = Path.GetFileNameWithoutExtension(dbPath);
            string statusFileName = $"{dbFileNameWithoutExt}{StatusFileSuffix}";

            if (string.IsNullOrEmpty(directory))
            {
                // Fallback if directory is somehow null
                return statusFileName;
            }
            return Path.Combine(directory, statusFileName);
        }
    }

    // CustomFormatter remains
    public sealed class CustomFormatter : ConsoleFormatter
    {
        public CustomFormatter() : base("custom") { }

        public override void Write<TState>(
            in LogEntry<TState> logEntry,
            IExternalScopeProvider? scopeProvider,
            TextWriter textWriter)
        {
            var timestamp = DateTimeOffset.Now.ToString("yyMMddTHH:mm:ss.fffzzz ");
            var level = logEntry.LogLevel.ToString().Substring(0, Math.Min(4, logEntry.LogLevel.ToString().Length)).ToUpper(); // Safer Substring
            string message = logEntry.Formatter(logEntry.State, logEntry.Exception);
            string? exceptionDetails = logEntry.Exception?.ToString(); // Get full exception details if present

            textWriter.Write($"{timestamp}{level}: {message}");
            if (exceptionDetails != null)
            {
                // Indent exception details for readability
                string indentedException = string.Join(Environment.NewLine,
                    exceptionDetails.Split(new[] { Environment.NewLine }, StringSplitOptions.None)
                                    .Select(line => "    " + line));
                textWriter.WriteLine(); // New line before exception
                textWriter.Write(indentedException);
            }
            textWriter.WriteLine(); // Ensure a new line after each log entry
        }
    }
}