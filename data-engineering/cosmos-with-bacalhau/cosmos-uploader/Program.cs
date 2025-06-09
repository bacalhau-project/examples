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
using System.Globalization; // Add for CultureInfo
using Humanizer; // <-- Add Humanizer

namespace CosmosUploader
{
    class Program
    {
        // Define known processor names (excluding Aggregate)
        private static readonly HashSet<string> KnownProcessors = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            "Schematize", "Sanitize" // Aggregate is handled separately
        };

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

            // Add update notification file path option
            var updateNotificationFilePathOption = new Option<string>(
                name: "--update-notification-file-path",
                description: "Path to the file used to signal configuration updates.",
                getDefaultValue: () => "/tmp/.update_config"); // Updated Default path
            rootCommand.AddOption(updateNotificationFilePathOption);

            // Transformation options are now controlled via the config file

            // Configure command handler
            rootCommand.SetHandler((Func<string, string, bool, int, string?, bool, bool, string, Task<int>>)(async (configPath, sqlitePath, continuous, interval, archivePath, developmentMode, debug, updateNotificationFilePath) =>
            {
                // Build services initial setup
                var services = new ServiceCollection();
                services.AddLogging(builder =>
                {
                    builder.ClearProviders();
                    builder.AddConsole(options => { options.FormatterName = "custom"; })
                           .AddConsoleFormatter<CustomFormatter, SimpleConsoleFormatterOptions>();
                    // Set initial default level - will be overridden after config load if not debugging
                    builder.SetMinimumLevel(debug ? LogLevel.Debug : LogLevel.Information); // Set initial based on debug flag
                });

                var initialServiceProvider = services.BuildServiceProvider();
                //var initialLogger = initialServiceProvider.GetRequiredService<ILogger<Program>>(); // No longer needed here

                // --- Initial Configuration Load ---
                AppSettings? settings = null;
                IServiceProvider? serviceProvider = null;
                DateTime lastConfigLoadTimeUtc = DateTime.MinValue; // Initialize

                try
                {
                    // Pass the initial provider to load config and setup final services
                    var loadResult = LoadAndConfigureServices(configPath, developmentMode, debug, updateNotificationFilePath, services, initialServiceProvider);
                    if (loadResult.AppSettings == null || loadResult.ServiceProvider == null)
                    {
                        // Use the initial provider to get a logger for this critical error
                        initialServiceProvider.GetRequiredService<ILogger<Program>>().LogCritical("Initial configuration failed. Exiting.");
                        
                        // Also write to console directly to ensure visibility even if logger configuration failed
                        Console.ForegroundColor = ConsoleColor.Red;
                        Console.Error.WriteLine("\nERROR: Initial configuration failed. Application cannot start.\n");
                        Console.Error.WriteLine("Check that the config file exists and is valid: " + configPath);
                        Console.Error.WriteLine("Check that the SQLite path exists: " + sqlitePath + "\n");
                        Console.ResetColor();
                        
                        return 1;
                    }
                    settings = loadResult.AppSettings;
                    serviceProvider = loadResult.ServiceProvider;
                    lastConfigLoadTimeUtc = DateTime.UtcNow; // Record initial load time
                }
                catch (Exception ex) // Catch potential errors during initial load not caught inside the method
                {
                    initialServiceProvider.GetRequiredService<ILogger<Program>>().LogCritical(ex, "Unhandled exception during initial configuration load: {Message}", ex.Message);
                    
                    // Also write to console directly to ensure visibility even if logger configuration failed
                    Console.ForegroundColor = ConsoleColor.Red;
                    Console.Error.WriteLine("\nERROR: Unhandled exception during startup:\n");
                    Console.Error.WriteLine(ex.Message);
                    
                    if (ex is System.IO.DirectoryNotFoundException || ex is System.IO.FileNotFoundException)
                    {
                        Console.Error.WriteLine("\nCheck that all required files exist:");
                        Console.Error.WriteLine("- Config file: " + configPath);
                        Console.Error.WriteLine("- SQLite path: " + sqlitePath);
                    }
                    
                    Console.Error.WriteLine("\nStack trace:");
                    Console.Error.WriteLine(ex.StackTrace);
                    Console.Error.WriteLine();
                    Console.ResetColor();
                    
                    return 1;
                }
                
                // Ensure logger uses the final provider's configuration
                var logger = serviceProvider.GetRequiredService<ILogger<Program>>();

                // Log if the default update notification file path is being used
                const string defaultUpdatePath = "/tmp/.update_config";
                if (settings.UpdateNotificationFilePath == defaultUpdatePath)
                {
                    logger.LogInformation("Using default configuration update notification file path: {DefaultPath}. Use --update-notification-file-path to specify a different location.", defaultUpdatePath);
                }

                // Resolve concrete service types needed for orchestration
                var sqliteReader = serviceProvider.GetRequiredService<SqliteReader>();
                var processDataService = serviceProvider.GetRequiredService<ProcessData>();
                var cosmosUploaderService = serviceProvider.GetRequiredService<ICosmosUploader>();
                var archiverService = serviceProvider.GetRequiredService<Archiver>();

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

                // Random number generator for jitter
                Random jitterRandom = new Random();
                const int JitterSeconds = 10; // +/- 10 seconds
                const int MinSleepSeconds = 1; // Minimum sleep time

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
                                                LastProcessedId = lastRecord.OriginalSqliteId.ToString()
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

                        // --- Check for Configuration Update --- 
                        try
                        {
                            if (File.Exists(settings.UpdateNotificationFilePath))
                            {
                                logger.LogInformation("Configuration update triggered by presence of notification file: {File}", settings.UpdateNotificationFilePath);

                                // --- Attempt Reload --- 
                                // Rebuild services collection for reload (safer than modifying existing)
                                var updatedServices = new ServiceCollection();
                                updatedServices.AddLogging(builder => // Re-add basic logging config
                                {
                                    builder.ClearProviders();
                                    builder.AddConsole(options => { options.FormatterName = "custom"; })
                                        .AddConsoleFormatter<CustomFormatter, SimpleConsoleFormatterOptions>();
                                    // Level will be set within LoadAndConfigureServices
                                });

                                var reloadResult = LoadAndConfigureServices(configPath, settings.DevelopmentMode, settings.DebugMode, settings.UpdateNotificationFilePath, updatedServices, serviceProvider); // Use current provider for reload messages

                                if (reloadResult.AppSettings != null && reloadResult.ServiceProvider != null)
                                {
                                    settings = reloadResult.AppSettings; // Update settings reference
                                    serviceProvider = reloadResult.ServiceProvider; // Update service provider reference
                                    lastConfigLoadTimeUtc = DateTime.UtcNow; // Update load time

                                    // Re-resolve services that might depend on the new configuration
                                    logger = serviceProvider.GetRequiredService<ILogger<Program>>(); // IMPORTANT: Update logger instance
                                    sqliteReader = serviceProvider.GetRequiredService<SqliteReader>();
                                    processDataService = serviceProvider.GetRequiredService<ProcessData>();
                                    cosmosUploaderService = serviceProvider.GetRequiredService<ICosmosUploader>();
                                    archiverService = serviceProvider.GetRequiredService<Archiver>();

                                    logger.LogInformation("Configuration successfully reloaded.");
                                }
                                else
                                {
                                    logger.LogError("Configuration reload failed. Continuing with previous configuration.");
                                }

                                // --- Always Attempt Delete After Reload Attempt --- 
                                try
                                {
                                    File.Delete(settings.UpdateNotificationFilePath);
                                    logger.LogInformation("Attempted deletion of configuration notification file: {File}", settings.UpdateNotificationFilePath);
                                }
                                catch (Exception deleteEx)
                                {
                                    logger.LogWarning(deleteEx, "Failed during attempt to delete configuration notification file {File} after reload attempt.", settings.UpdateNotificationFilePath);
                                }
                            }
                        }
                        catch (Exception ex)
                        {
                             logger.LogError(ex, "Error checking or processing configuration update notification file: {File}", settings.UpdateNotificationFilePath);
                        }
                        // --- End Check for Configuration Update ---

                        // Calculate sleep duration with jitter
                        int baseIntervalSeconds = interval; // Use the command-line provided interval
                        int jitter = jitterRandom.Next(-JitterSeconds, JitterSeconds + 1); // Range is inclusive min, exclusive max
                        int sleepDurationSeconds = Math.Max(MinSleepSeconds, baseIntervalSeconds + jitter);

                        logger.LogInformation("Continuous mode enabled. Waiting {Duration} seconds (Interval: {BaseInterval}s, Jitter: {JitterValue}s) before next cycle...",
                            sleepDurationSeconds, baseIntervalSeconds, jitter);
                        await Task.Delay(TimeSpan.FromSeconds(sleepDurationSeconds), cts.Token);
                    }
                } while (continuous && !cts.IsCancellationRequested);

                logger.LogInformation("CosmosUploader finished.");
                return 0; // Success
            }), configOption, sqliteOption, continuousOption, intervalOption, archivePathOption, developmentOption, debugOption, updateNotificationFilePathOption);

            return await rootCommand.InvokeAsync(args);
        }

        // --- Refactored Configuration Loading and Service Setup ---  
        private static (AppSettings? AppSettings, IServiceProvider? ServiceProvider) LoadAndConfigureServices(
            string configPath, 
            bool developmentMode, 
            bool debug, 
            string updateNotificationFilePath, 
            IServiceCollection services, 
            IServiceProvider initialServiceProvider) // Accept provider instead of logger
        {
            CosmosConfig? config = null;
            AppSettings? appSettings = null;
            List<string> configuredProcessors = new List<string>();
            TimeSpan? aggregationWindow = null;
            // Get loggers from the initial provider
            var logger = initialServiceProvider.GetRequiredService<ILogger<Program>>(); 
            var configProviderLogger = initialServiceProvider.GetRequiredService<ILogger<CosmosUploader.Configuration.YamlConfigurationProvider>>();

            try
            {
                // Pass the correctly typed logger
                var configProvider = new CosmosUploader.Configuration.YamlConfigurationProvider(configPath, configProviderLogger);
                config = configProvider.GetConfiguration();

                // --- Validate and retrieve Processor List (Pipeline Processors) ---
                configuredProcessors = config?.Processing?.Processors ?? new List<string>();
                if (configuredProcessors.Any())
                {
                    logger.LogInformation("Configured processing pipeline: [{Processors}]", string.Join(" -> ", configuredProcessors));
                    var unknownProcessors = configuredProcessors.Where(p => !KnownProcessors.Contains(p)).ToList();
                    if (unknownProcessors.Any())
                    {
                        logger.LogCritical("Invalid configuration: Unknown processor(s) specified: {Unknown}. Known: {Known}", string.Join(", ", unknownProcessors), string.Join(", ", KnownProcessors));
                        Console.Error.WriteLine($"ERROR: Unknown processor(s) in config 'processors': {string.Join(", ", unknownProcessors)}. Valid: {string.Join(", ", KnownProcessors)}");
                        return (null, null); // Indicate failure
                    }
                }
                else
                {
                    logger.LogInformation("No pipeline processors configured.");
                }

                // --- Validate and parse Aggregation configuration ---
                var aggregationConfig = config?.Processing?.Aggregation;
                if (aggregationConfig != null)
                {
                    if (string.IsNullOrWhiteSpace(aggregationConfig.Window))
                    {
                         logger.LogCritical("Invalid configuration: 'aggregation.window' is required.");
                         Console.Error.WriteLine("ERROR: 'aggregation.window' is required in config.");
                         return (null, null);
                    }
                    try
                    {
                        // Use TimeSpan.TryParse for robust parsing
                        if (TimeSpan.TryParse(aggregationConfig.Window, out var parsedWindow) && parsedWindow > TimeSpan.Zero)
                        {
                            aggregationWindow = parsedWindow;
                        }
                        else
                        {
                             logger.LogCritical("Invalid configuration: Could not parse aggregation window '{Window}' or it was not positive. Use formats like '00:05:00' (5 minutes) or '1.00:00:00' (1 day).", aggregationConfig.Window);
                             Console.Error.WriteLine($"ERROR: Invalid format or non-positive value for aggregation window '{aggregationConfig.Window}'. Use standard TimeSpan formats (e.g., '00:05:00', '1.00:00:00').");
                             return (null, null);
                        }

                        logger.LogInformation("Aggregation configured with window: {Window} ({WindowHumanized})", aggregationWindow, aggregationWindow.Value.Humanize());
                    }
                    catch (Exception ex) // Catch potential errors during parsing
                    {
                        logger.LogCritical(ex, "Error processing aggregation window configuration '{Window}'.", aggregationConfig.Window);
                        return (null, null);
                    }
                }
                else
                {
                    logger.LogInformation("Aggregation not configured.");
                }

                // --- Map to canonical AppSettings ---
                if (config?.Cosmos == null || config.Performance == null || config.Logging == null)
                {                    
                    logger.LogCritical("Core configuration sections (Cosmos, Performance, Logging) are missing.");
                    return (null, null);
                }
                appSettings = new AppSettings
                {
                    Cosmos = config.Cosmos,
                    Performance = config.Performance,
                    Logging = config.Logging,
                    DevelopmentMode = developmentMode,
                    DebugMode = debug,
                    Processors = configuredProcessors,
                    AggregationWindow = aggregationWindow,
                    StatusFileSuffix = "_processing_status.json",
                    UpdateNotificationFilePath = updateNotificationFilePath
                };

                // --- Update logging level based on final settings ---
                services.AddLogging(builder =>
                {
                    LogLevel effectiveLevel = LogLevel.Information; // Default
                    if (appSettings.DebugMode)
                    {
                        effectiveLevel = LogLevel.Debug;
                    }
                    else if (Enum.TryParse<LogLevel>(appSettings.Logging?.Level ?? "Information", true, out var configLevel))
                    {
                         effectiveLevel = configLevel;
                    }
                    builder.SetMinimumLevel(effectiveLevel);
                    // Add HttpClientFactory registration
                    services.AddHttpClient();
                    if (appSettings.Logging != null)
                    {
                        appSettings.Logging.Level = effectiveLevel.ToString(); // Ensure AppSettings reflects the actual level
                    }
                });

                // Clear potentially existing singletons/transients before adding new ones
                // This is crucial for reload scenarios
                var serviceDescriptors = services.Where(d => d.ServiceType == typeof(AppSettings) || 
                                                         d.ServiceType == typeof(CosmosConfig) ||
                                                         d.ServiceType == typeof(ISchemaProcessor) ||
                                                         d.ServiceType == typeof(ISanitizeProcessor) ||
                                                         d.ServiceType == typeof(IAggregateProcessor) ||
                                                         // Add other services that depend directly on config if needed
                                                         d.ImplementationType == typeof(SqliteReader) || 
                                                         d.ImplementationType == typeof(ProcessData) ||
                                                         d.ImplementationType == typeof(Archiver) ||
                                                         d.ImplementationType == typeof(Services.CosmosUploader)
                                                         ).ToList();
                foreach (var descriptor in serviceDescriptors)
                {
                    services.Remove(descriptor);
                }

                // Register services with potentially new configuration
                services.AddSingleton(appSettings); 
                services.AddSingleton(config); // Keep raw config available if needed
                services.AddTransient<SqliteReader>();
                services.AddTransient<ProcessData>();
                services.AddTransient<Archiver>();
                services.AddTransient<ICosmosUploader, Services.CosmosUploader>();

                // Register pipeline processors based on the config
                if (appSettings.Processors.Any(p => StringComparer.OrdinalIgnoreCase.Equals(p, "Schematize")))
                {
                    services.AddTransient<ISchemaProcessor, SchemaProcessor>();
                }
                if (appSettings.Processors.Any(p => StringComparer.OrdinalIgnoreCase.Equals(p, "Sanitize")))
                {
                    services.AddTransient<ISanitizeProcessor, SanitizeProcessor>();
                }

                // Register aggregation processor conditionally
                if (appSettings.AggregationWindow.HasValue)
                {
                    services.AddTransient<IAggregateProcessor>(sp => 
                        new AggregateProcessor(
                            sp.GetRequiredService<ILogger<AggregateProcessor>>(), 
                            appSettings.AggregationWindow.Value
                        )
                    );
                }
                
                // Build the service provider
                var serviceProvider = services.BuildServiceProvider();
                logger = serviceProvider.GetRequiredService<ILogger<Program>>(); // Get the fully configured logger
                logger.LogInformation("Configuration loaded and services configured successfully.");
                return (appSettings, serviceProvider);

            }
            catch (Exception ex)
            {                
                logger.LogCritical(ex, "Failed during configuration load or service setup: {Message}", ex.Message);
                return (null, null); // Indicate failure
            }
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