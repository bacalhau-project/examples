using System;
using System.CommandLine;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using CosmosUploader.Configuration;
using CosmosUploader.Services;
using Microsoft.Azure.Cosmos;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Console;
using Microsoft.Extensions.Logging.Abstractions;
using Polly;
using Polly.Retry;
using System.Net; // Added for DNS lookup
using System.Collections; // Added for Environment Variables

// Define the expected handler delegate signature
using HandlerFunc = System.Func<string, string, bool, int, string?, bool, bool, System.Threading.Tasks.Task<int>>;

namespace CosmosUploader
{
    class Program
    {
        static async Task<int> Main(string[] args)
        {
            // Set up command line arguments
            var rootCommand = new RootCommand("Azure Cosmos DB Uploader for sensor data");
            
            var configOption = new Option<string>(
                name: "--config",
                description: "Path to the YAML configuration file");
            configOption.IsRequired = true;
            rootCommand.AddOption(configOption);
            
            var sqliteOption = new Option<string>(
                name: "--sqlite",
                description: "Directory containing SQLite databases");
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
            
            // Configure command handler
            rootCommand.SetHandler((HandlerFunc)(async (configPath, sqlitePath, continuous, interval, archivePath, developmentMode, debug) =>
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

                // Add configuration
                YamlConfigurationProvider? configProvider = null;
                CosmosConfig? config = null;
                AppSettings? appSettings = null;
                try
                {
                    configProvider = new YamlConfigurationProvider(configPath, initialServiceProvider.GetRequiredService<ILogger<YamlConfigurationProvider>>());
                    config = configProvider.GetConfiguration();

                     // Update logging level based on config OR debug flag
                     // Rebuild the provider to apply the new level.
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
                             effectiveLevel = Enum.TryParse<LogLevel>(config?.Logging?.Level ?? "Information", true, out var configLevel) 
                                                 ? configLevel 
                                                 : LogLevel.Information; // Default to Info if parsing fails
                         }
                         builder.SetMinimumLevel(effectiveLevel);
                     });

                     // Map CosmosConfig to AppSettings
                     appSettings = new AppSettings
                     {
                         Cosmos = new CosmosSettings
                         {
                            Endpoint = config!.Cosmos.Endpoint,
                            Key = config.Cosmos.Key,
                            DatabaseName = config.Cosmos.DatabaseName,
                            ContainerName = config.Cosmos.ContainerName,
                            PartitionKey = config.Cosmos.PartitionKey,
                            ResourceGroup = config.Cosmos.ResourceGroup
                         },
                         Performance = new PerformanceSettings
                         {
                            DisableIndexingDuringBulk = config.Performance.DisableIndexingDuringBulk,
                            SleepInterval = interval // Use command-line interval here if needed, or keep config value? Let's use config for performance tuning section.
                         },
                         Logging = new LoggingSettings
                         {
                            Level = config.Logging.Level,
                            LogRequestUnits = config.Logging.LogRequestUnits,
                            LogLatency = config.Logging.LogLatency
                         },
                         DevelopmentMode = developmentMode,
                         DebugMode = debug // Add debug flag to settings if needed elsewhere
                     };

                     services.AddSingleton(appSettings); // Add mapped settings
                     services.AddSingleton(config);      // Add raw config if needed elsewhere

                     services.AddSingleton<ICosmosUploader, Services.CosmosUploader>();
                     services.AddTransient<SqliteReader>(sp =>
                         new SqliteReader(
                             sp.GetRequiredService<ILogger<SqliteReader>>(),
                             sp.GetRequiredService<ICosmosUploader>(),
                             sp.GetRequiredService<AppSettings>()
                         )
                     );
                }
                catch (Exception ex)
                {
                    // Use final logger instance if available, else initialLogger
                    var loggerToUse = initialLogger;
                    loggerToUse.LogCritical(ex, "Failed during configuration setup: {Message}", ex.Message);
                    return 1; // Return error code
                }

                // Build the final service provider
                var serviceProvider = services.BuildServiceProvider();
                var logger = serviceProvider.GetRequiredService<ILogger<Program>>(); // Final logger instance

                // Get required services
                ICosmosUploader uploader;
                SqliteReader sqliteReader;
                try {
                    uploader = serviceProvider.GetRequiredService<ICosmosUploader>();
                    sqliteReader = serviceProvider.GetRequiredService<SqliteReader>();
                } catch (Exception ex) {
                     logger.LogCritical(ex, "Failed to resolve core services: {Message}", ex.Message);
                     return 1;
                }


                // Set up configuration change handler (if needed)
                // configProvider.ConfigurationChanged += ... ;

                // Set up cancellation token source for graceful shutdown
                using var cts = new CancellationTokenSource();
                Console.CancelKeyPress += (s, e) =>
                {
                    logger.LogInformation("Shutdown signal received...");
                    cts.Cancel();
                    e.Cancel = true;
                };

                // Set paths
                sqliteReader!.SetDataPath(sqlitePath);
                if (!string.IsNullOrEmpty(archivePath)) {
                    logger.LogDebug($"Setting archive path to: {archivePath}");
                    sqliteReader!.SetArchivePath(archivePath);
                } else {
                    var sqliteDirectory = Path.GetDirectoryName(sqlitePath) ?? Directory.GetCurrentDirectory();
                    logger.LogDebug($"Setting archive path to SQLite directory: {sqliteDirectory}");
                    sqliteReader!.SetArchivePath(sqliteDirectory);
                }

                 // Print connection information
                 logger.LogInformation("Starting Cosmos Uploader");
                 if (appSettings!.DevelopmentMode) { logger.LogWarning("DEVELOPMENT MODE ENABLED: IDs and timestamps will be overwritten."); }
                 if (appSettings!.DebugMode) { logger.LogInformation("DEBUG MODE ENABLED: Verbose logging active."); }
                 logger.LogInformation("Configuration file: {ConfigPath}", configPath);
                 logger.LogInformation("SQLite database: {SqlitePath}", sqlitePath);
                 logger.LogInformation("Cosmos DB endpoint: {Endpoint}", config!.Cosmos.Endpoint);
                 logger.LogInformation("Database: {Database}/{Container}", config.Cosmos.DatabaseName, config.Cosmos.ContainerName);

                 // Random number generator for jitter
                 var random = new Random();

                try
                {
                    // Run mode logic
                    if (continuous)
                    {
                        logger.LogInformation("Running in continuous mode with {Interval} seconds interval between processing cycles", interval);

                        // --- Polly Policy for Initialization --- 
                        // Retries indefinitely on any exception during initialization
                        // Waits exponentially: 5s, 10s, 20s, ... up to 5 minutes
                        AsyncRetryPolicy initPolicy = Policy
                            .Handle<Exception>()
                            .WaitAndRetryForeverAsync(
                                sleepDurationProvider: retryAttempt => TimeSpan.FromSeconds(Math.Min(Math.Pow(2, retryAttempt -1) * 5, 300)), // 5s * 2^(attempt-1), max 300s
                                onRetryAsync: async (Exception exception, TimeSpan timespan) => 
                                {
                                    // Log exception details on retry
                                    logger.LogWarning(exception, 
                                        "Initialization failed. Retrying after {Timespan}s... Exception: {ExceptionType} - {ExceptionMessage}", 
                                        timespan.TotalSeconds, exception.GetType().Name, exception.Message);

                                    // --- Debug Diagnostics on Timeout ---
                                    if (appSettings?.DebugMode == true && IsPotentialTimeoutException(exception))
                                    {
                                        logger.LogDebug("DEBUG: Timeout detected during initialization retry. Collecting diagnostics...");
                                        
                                        // 1. Log Environment Variables
                                        try 
                                        {
                                            logger.LogDebug("DEBUG: Environment Variables:");
                                            foreach (DictionaryEntry de in Environment.GetEnvironmentVariables())
                                            {
                                                logger.LogDebug("  {Key} = {Value}", de.Key, de.Value);
                                            }
                                        } 
                                        catch (Exception envEx) 
                                        {
                                            logger.LogWarning(envEx, "DEBUG: Failed to retrieve environment variables.");
                                        }

                                        // 2. Perform DNS Lookup
                                        if (!string.IsNullOrEmpty(appSettings?.Cosmos?.Endpoint))
                                        {
                                            try
                                            {
                                                Uri endpointUri = new Uri(appSettings.Cosmos.Endpoint);
                                                logger.LogDebug("DEBUG: Attempting DNS lookup for host: {Host}", endpointUri.Host);
                                                IPHostEntry entry = await Dns.GetHostEntryAsync(endpointUri.Host);
                                                logger.LogDebug("DEBUG: DNS resolved host {Host} to {IPCount} IP addresses. First IP: {IPAddress}",
                                                    endpointUri.Host, entry.AddressList.Length, entry.AddressList.FirstOrDefault()?.ToString() ?? "N/A");
                                            }
                                            catch (Exception dnsEx)
                                            {
                                                logger.LogWarning(dnsEx, "DEBUG: DNS lookup failed for {Host}.", new Uri(appSettings.Cosmos.Endpoint).Host);
                                            }
                                        } else {
                                            logger.LogWarning("DEBUG: Cannot perform DNS lookup because Cosmos endpoint is not configured in AppSettings.");
                                        }
                                        logger.LogDebug("DEBUG: Diagnostics collection finished.");
                                    }
                                    // --- End Debug Diagnostics ---

                                    await Task.CompletedTask; // Required for async onRetry
                                }
                            );

                         // --- Polly Policy for Processing --- 
                         // Retries 3 times on specific processing errors
                         // Waits exponentially based on the --interval: interval*1, interval*2, interval*4
                         const int maxProcessingRetries = 3;
                         IAsyncPolicy processingPolicy = Policy
                             .Handle<CosmosException>() // Add other transient exceptions if needed
                             .Or<Exception>() // Catch potentially other transient issues during processing
                             .WaitAndRetryAsync(
                                 retryCount: maxProcessingRetries,
                                 sleepDurationProvider: retryAttempt => TimeSpan.FromSeconds(interval * Math.Pow(2, retryAttempt - 1)), // interval * 2^(attempt-1)
                                 onRetryAsync: async (Exception exception, TimeSpan timespan, int retryAttempt, Context context) =>
                                 {
                                     logger.LogWarning(exception, 
                                         "Processing failed (Attempt {RetryAttempt}/{MaxRetries}). Waiting {Timespan} seconds before next retry...",
                                         retryAttempt, maxProcessingRetries, timespan.TotalSeconds);
                                      await Task.CompletedTask;
                                 }
                             );


                        bool firstInitialization = true;
                        while (!cts.Token.IsCancellationRequested)
                        {
                            bool initialized = false;
                            try
                            {
                                // Execute Initialization with Polly Policy
                                logger.LogDebug("Attempting Cosmos DB initialization via Polly policy (Attempt Context: first={isFirst})", firstInitialization);
                                await initPolicy.ExecuteAsync(async token => 
                                {
                                    logger.LogDebug("Calling uploader.InitializeAsync() within Polly attempt...");
                                    try {
                                        await uploader!.InitializeAsync(token);
                                        initialized = true; // Set flag inside successful execution
                                        logger.LogDebug("uploader.InitializeAsync() completed successfully within Polly attempt.");
                                        if (!firstInitialization) { // Only log subsequent successful inits
                                            logger.LogInformation("Cosmos DB connection successfully re-established after previous failure(s).");
                                        }
                                        firstInitialization = false; // Mark that initial attempt (or first success) happened
                                    } catch (Exception ex) {
                                        // Log the specific exception from InitializeAsync *before* Polly handles it for retry
                                        logger.LogError(ex, "Exception caught directly from uploader.InitializeAsync() within Polly attempt: {ExceptionType} - {Message}", ex.GetType().Name, ex.Message);
                                        throw; // Rethrow so Polly can handle the retry according to the policy
                                    }
                                }, cts.Token);

                                if (initialized)
                                {
                                    try
                                    {
                                        // Execute Processing with Polly Policy
                                        await processingPolicy.ExecuteAsync(async token => {
                                             await sqliteReader!.ProcessDatabaseAsync(token);
                                        }, cts.Token);

                                        // Calculate delay with jitter (+/- 30 seconds)
                                        int jitterMilliseconds = random.Next(-30000, 30001); // -30s to +30s
                                        TimeSpan baseInterval = TimeSpan.FromSeconds(interval);
                                        TimeSpan jitter = TimeSpan.FromMilliseconds(jitterMilliseconds);
                                        TimeSpan delay = baseInterval + jitter;
                                        // Ensure minimum delay (e.g., 1 second)
                                        if (delay.TotalSeconds < 1) delay = TimeSpan.FromSeconds(1);

                                        var nextWakeTime = DateTime.Now + delay;
                                        logger.LogInformation("Processing complete. Sleeping for {DelaySeconds:F1} seconds (interval {BaseInterval}s + jitter {JitterSeconds:F1}s) until {NextWakeTime}", 
                                            delay.TotalSeconds, interval, jitter.TotalSeconds, nextWakeTime.ToString("HH:mm:ss"));

                                        // Check cancellation before delaying
                                        try
                                        {
                                            await Task.Delay(delay, cts.Token);
                                        } catch (OperationCanceledException) {
                                             logger.LogInformation("Operation cancelled during sleep period.");
                                             break; // Exit loop if cancelled
                                        }
                                    }
                                    catch (OperationCanceledException) {
                                        logger.LogInformation("Processing operation cancelled.");
                                        break; // Exit loop if cancelled
                                    }
                                    catch (Exception ex) {
                                        // This catch block is reached if the processingPolicy fails after all retries
                                        logger.LogCritical(ex, "Processing failed after {MaxRetries} retries. Stopping continuous processing.", maxProcessingRetries);
                                        // Optionally, re-throw or handle differently, but breaking the loop is common.
                                        break; // Exit the while loop on processing policy failure
                                    }
                                }
                                else
                                {
                                    // This case should ideally not be reached if initPolicy retries indefinitely
                                    logger.LogError("Initialization flag not set after initPolicy execution. This should not happen.");
                                    await Task.Delay(TimeSpan.FromSeconds(interval), cts.Token);
                                }

                            }
                            catch (OperationCanceledException) when (cts.IsCancellationRequested)
                            {
                                logger.LogInformation("Cancellation requested during continuous loop. Exiting...");
                                break;
                            }
                            catch (Exception ex)
                            {
                                // Catch exceptions that might escape Polly policies (e.g., during policy setup, or unhandled exceptions)
                                // This might indicate a non-transient issue or a bug.
                                logger.LogCritical(ex, "Unhandled exception in continuous processing loop: {Message}. Exiting loop.", ex.Message);
                                break; // Exit the loop on critical unhandled errors
                            }
                            
                            // Wait before the next cycle
                            try
                            {
                                logger.LogDebug("Waiting {Interval} seconds before next processing cycle...", interval);
                                await Task.Delay(TimeSpan.FromSeconds(interval), cts.Token);
                            }
                            catch (OperationCanceledException)
                            {
                                logger.LogInformation("Cancellation requested during wait interval. Exiting...");
                                break;
                            }
                        }
                         logger.LogInformation("Continuous mode loop exited.");
                    }
                    else // Single run mode
                    {
                        logger.LogInformation("Running in single mode");
                        logger.LogInformation("Initializing Cosmos DB connection...");
                        try
                        {
                            await uploader!.InitializeAsync(cts.Token);
                            logger.LogInformation("Cosmos DB connection initialized successfully.");
                            await sqliteReader!.ProcessDatabaseAsync(cts.Token);
                        }
                        catch (Exception ex)
                        {
                             logger.LogCritical(ex, "Failed during single run: {Message}", ex.Message);
                             return 1; // Indicate failure
                        }
                    }

                    logger.LogInformation("Cosmos Uploader finished.");
                    return 0; // Indicate success
                }
                catch (OperationCanceledException) when (cts.IsCancellationRequested)
                {
                    logger.LogWarning("Operation cancelled.");
                    return 130; // Standard exit code for Ctrl+C
                }
                catch (Exception ex)
                {
                    logger.LogCritical(ex, "An unhandled error occurred: {Message}", ex.Message);
                    return 1; // Indicate failure
                }
                finally
                {
                    // Dispose resources if needed (e.g., ServiceProvider)
                    if (serviceProvider is IDisposable disposableProvider)
                    {
                        disposableProvider.Dispose();
                    }
                }
            }), configOption, sqliteOption, continuousOption, intervalOption, archivePathOption, developmentOption, debugOption);
            
            // Parse and execute
            return await rootCommand.InvokeAsync(args);
        }

        // Helper function to identify potential timeout exceptions
        private static bool IsPotentialTimeoutException(Exception ex)
        {
            // Check for the specific Cosmos DB Gateway Timeout error
            if (ex is CosmosException cosmosEx && 
                cosmosEx.StatusCode == System.Net.HttpStatusCode.ServiceUnavailable && 
                cosmosEx.SubStatusCode == 20003)
            {
                return true;
            }

            // Check if it's a general operation cancellation, possibly due to overall timeout
            if (ex is OperationCanceledException)
            {
                return true;
            }
            
            // Check inner exceptions recursively
            if (ex.InnerException != null)
            {
                return IsPotentialTimeoutException(ex.InnerException);
            }

            return false;
        }
    }
}

// Add this class to your project
public sealed class CustomFormatter : ConsoleFormatter
{
    public CustomFormatter() : base("custom") { }

    public override void Write<TState>(
        in LogEntry<TState> logEntry,
        IExternalScopeProvider? scopeProvider,
        TextWriter textWriter)
    {
        var timestamp = DateTimeOffset.Now.ToString("yyMMddTHH:mm:ss.fffzzz ");
        var level = logEntry.LogLevel.ToString().Substring(0, 4).ToUpper();
        textWriter.WriteLine($"{timestamp}{level}: {logEntry.Formatter(logEntry.State, logEntry.Exception)}");
    }
}