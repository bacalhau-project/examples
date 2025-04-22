using System;
using System.CommandLine;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using CosmosUploader.Configuration;
using CosmosUploader.Services;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Console;
using Microsoft.Extensions.Logging.Abstractions;

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
            
            // Configure command handler
            rootCommand.SetHandler(async (configPath, sqlitePath, continuous, interval, archivePath) =>
            {
                try
                {
                    // Check if config file exists
                    if (!File.Exists(configPath))
                    {
                        Console.Error.WriteLine($"Error: Configuration file not found at '{configPath}'");
                        Console.Error.WriteLine("Please ensure the config file exists and the path is correct.");
                        Environment.Exit(1);
                    }

                    // Setup dependency injection
                    var services = new ServiceCollection();
                                        
                    services.AddLogging(builder => 
                    {
                        builder.ClearProviders();
                        builder.AddConsole(options => 
                        {
                            options.FormatterName = "custom";
                        })
                        .AddConsoleFormatter<CustomFormatter, SimpleConsoleFormatterOptions>();
                    });


                                        
                    var serviceProvider = services.BuildServiceProvider();
                    var logger = serviceProvider.GetRequiredService<ILogger<Program>>();
                    
                    // Add configuration
                    var configProvider = new YamlConfigurationProvider(configPath, serviceProvider.GetRequiredService<ILogger<YamlConfigurationProvider>>());
                    var config = configProvider.GetConfiguration();
                    
                    // Update logging level based on config
                    services.AddLogging(builder =>
                    {
                        builder.AddConsole();
                        builder.SetMinimumLevel(Enum.Parse<LogLevel>(config.Logging.Level, true));
                    });
                    
                    // Register services with updated configuration
                    services.AddSingleton(config);
                    
                    // Map CosmosConfig to AppSettings
                    var appSettings = new AppSettings
                    {
                        Cosmos = new CosmosSettings
                        {
                            Endpoint = config.Cosmos.Endpoint,
                            Key = config.Cosmos.Key,
                            DatabaseName = config.Cosmos.DatabaseName,
                            ContainerName = config.Cosmos.ContainerName,
                            PartitionKey = config.Cosmos.PartitionKey
                        },
                        Performance = new PerformanceSettings
                        {
                            Throughput = config.Performance.Throughput,
                            BatchSize = config.Performance.BatchSize,
                            MaxParallelOperations = config.Performance.MaxParallelOperations
                        },
                        Logging = new LoggingSettings
                        {
                            Level = config.Logging.Level,
                            LogRequestUnits = config.Logging.LogRequestUnits,
                            LogLatency = config.Logging.LogLatency
                        }
                    };
                    
                    services.AddSingleton(appSettings);
                    services.AddTransient<ICosmosUploader, Services.CosmosUploader>();
                    services.AddTransient<SqliteReader>();
                    
                    serviceProvider = services.BuildServiceProvider();
                    var uploader = serviceProvider.GetRequiredService<ICosmosUploader>();
                    var sqliteReader = serviceProvider.GetRequiredService<SqliteReader>();
                    
                    // Set up configuration change handler
                    configProvider.ConfigurationChanged += (sender, newConfig) =>
                    {
                        logger.LogInformation("Configuration changed at {Time}, updating services...", DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"));
                        // Update services with new configuration
                        // This is a simplified example - in a real application, you might need to
                        // recreate some services or handle the changes more carefully
                    };
                    
                    // Initialize the uploader
                    await uploader.InitializeAsync();
                    
                    // Set up cancellation token source for graceful shutdown
                    using var cts = new CancellationTokenSource();
                    Console.CancelKeyPress += (s, e) =>
                    {
                        logger.LogInformation("Shutting down...");
                        cts.Cancel();
                        e.Cancel = true;
                    };
                    
                    // Set SQLite data path
                    sqliteReader.SetDataPath(sqlitePath);
                    
                    // Set archive path if provided, otherwise use the same directory as the SQLite file
                    if (!string.IsNullOrEmpty(archivePath))
                    {
                        logger.LogDebug($"Setting archive path to: {archivePath}");
                        sqliteReader.SetArchivePath(archivePath);
                    }
                    else
                    {
                        var sqliteDirectory = Path.GetDirectoryName(sqlitePath);
                        if (string.IsNullOrEmpty(sqliteDirectory))
                        {
                            sqliteDirectory = Directory.GetCurrentDirectory();
                        }
                        logger.LogDebug($"Setting archive path to SQLite directory: {sqliteDirectory}");
                        sqliteReader.SetArchivePath(sqliteDirectory);
                    }
                    
                    // Print connection information
                    logger.LogInformation("Starting Cosmos Uploader");
                    logger.LogInformation("Configuration file: {ConfigPath}", configPath);
                    logger.LogInformation("SQLite database: {SqlitePath}", sqlitePath);
                    logger.LogInformation("Cosmos DB endpoint: {Endpoint}", config.Cosmos.Endpoint);
                    logger.LogInformation("Database: {Database}/{Container}", config.Cosmos.DatabaseName, config.Cosmos.ContainerName);
                    
                    // Run in continuous mode if requested
                    if (continuous)
                    {
                        logger.LogInformation("Running in continuous mode with {Interval} seconds interval", config.Performance.SleepInterval);
                        while (!cts.Token.IsCancellationRequested)
                        {
                            try
                            {
                                await sqliteReader.ProcessDatabaseAsync(cts.Token);
                                var nextWakeTime = DateTime.Now.AddSeconds(config.Performance.SleepInterval);
                                logger.LogInformation("Sleeping until {NextWakeTime}", nextWakeTime.ToString("HH:mm:ss"));
                                await Task.Delay(TimeSpan.FromSeconds(config.Performance.SleepInterval), cts.Token);
                            }
                            catch (OperationCanceledException)
                            {
                                logger.LogInformation("Operation cancelled");
                                break;
                            }
                            catch (Exception ex)
                            {
                                logger.LogError(ex, "Error during continuous processing");
                                // Wait a bit before retrying
                                await Task.Delay(TimeSpan.FromSeconds(5), cts.Token);
                            }
                        }
                    }
                    else
                    {
                        // Run once
                        logger.LogDebug("Running in single execution mode");
                        await sqliteReader.ProcessDatabaseAsync(cts.Token);
                    }
                    
                    logger.LogInformation("Upload completed successfully");
                }
                catch (Exception ex)
                {
                    Console.Error.WriteLine($"Error: {ex.Message}");
                    Console.Error.WriteLine($"Inner error: {ex.InnerException?.Message}");
                    Console.Error.WriteLine(ex.StackTrace);
                    Environment.Exit(1);
                }
            }, configOption, sqliteOption, continuousOption, intervalOption, archivePathOption);
            
            // Parse and execute
            return await rootCommand.InvokeAsync(args);
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