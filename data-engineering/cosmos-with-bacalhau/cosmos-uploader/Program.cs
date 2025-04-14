using System;
using System.CommandLine;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using CosmosUploader.Configuration;
using CosmosUploader.Services;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;

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
                description: "Path to the configuration file");
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
                    // Setup dependency injection
                    var services = new ServiceCollection();
                    
                    // Add logging
                    services.AddLogging(builder =>
                    {
                        builder.AddConsole();
                        builder.SetMinimumLevel(LogLevel.Information);
                    });
                    
                    // Add configuration
                    var configProvider = new ConfigurationProvider(configPath);
                    services.AddSingleton(configProvider.GetAppSettings());
                    
                    // Register services
                    services.AddTransient<ICosmosUploader, Services.CosmosUploader>();
                    services.AddTransient<SqliteReader>();
                    
                    var serviceProvider = services.BuildServiceProvider();
                    var logger = serviceProvider.GetRequiredService<ILogger<Program>>();
                    var uploader = serviceProvider.GetRequiredService<ICosmosUploader>();
                    var sqliteReader = serviceProvider.GetRequiredService<SqliteReader>();
                    
                    // Initialize the uploader
                    await uploader.InitializeAsync();
                    
                    // Set up cancellation token source for graceful shutdown
                    using var cts = new CancellationTokenSource();
                    Console.CancelKeyPress += (s, e) =>
                    {
                        logger.LogInformation("Cancellation requested. Shutting down...");
                        cts.Cancel();
                        e.Cancel = true;
                    };
                    
                    // Set SQLite data path
                    sqliteReader.SetDataPath(sqlitePath);
                    
                    // Set archive path if provided
                    if (!string.IsNullOrEmpty(archivePath))
                    {
                        logger.LogInformation($"Setting archive path to: {archivePath}");
                        sqliteReader.SetArchivePath(archivePath);
                    }
                    
                    // Run in continuous mode if requested
                    if (continuous)
                    {
                        logger.LogInformation($"Running in continuous mode with {interval} second interval");
                        while (!cts.Token.IsCancellationRequested)
                        {
                            try
                            {
                                logger.LogInformation("Starting data upload cycle...");
                                await sqliteReader.ProcessAllDatabasesAsync(cts.Token);
                                logger.LogInformation($"Waiting {interval} seconds before next cycle");
                                await Task.Delay(TimeSpan.FromSeconds(interval), cts.Token);
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
                        logger.LogInformation("Running in single execution mode");
                        await sqliteReader.ProcessAllDatabasesAsync(cts.Token);
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