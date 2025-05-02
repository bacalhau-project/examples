using System;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using YamlDotNet.Serialization;
using YamlDotNet.Serialization.NamingConventions;

namespace CosmosUploader.Configuration
{
    public class YamlConfigurationProvider : IDisposable
    {
        private readonly string _configPath;
        private readonly ILogger<YamlConfigurationProvider> _logger;
        private readonly CancellationTokenSource _cts;
        private CosmosConfig _currentConfig;
        private DateTime _lastWriteTime;

        public event EventHandler<CosmosConfig>? ConfigurationChanged;

        public YamlConfigurationProvider(string configPath, ILogger<YamlConfigurationProvider> logger)
        {
            // Convert relative path to absolute path
            _configPath = Path.GetFullPath(configPath);
            _logger = logger;
            _cts = new CancellationTokenSource();
            
            // Check if file exists before trying to load it
            if (!File.Exists(_configPath))
            {
                var errorMessage = $"Configuration file not found: {_configPath}";
                _logger.LogCritical(errorMessage);
                Console.ForegroundColor = ConsoleColor.Red;
                Console.Error.WriteLine($"\nERROR: {errorMessage}\n");
                Console.ResetColor();
                throw new FileNotFoundException(errorMessage, _configPath);
            }
            
            _currentConfig = LoadConfiguration();
            _lastWriteTime = File.GetLastWriteTime(_configPath);

            // Start background task to check for changes
            Task.Run(WatchConfigurationChanges, _cts.Token);
        }

        private CosmosConfig LoadConfiguration()
        {
            try
            {
                var deserializer = new DeserializerBuilder()
                    .WithNamingConvention(UnderscoredNamingConvention.Instance)
                    .IgnoreUnmatchedProperties()
                    .Build();

                var yaml = File.ReadAllText(_configPath);
                var config = deserializer.Deserialize<CosmosConfig>(yaml);

                ValidateConfiguration(config);
                return config;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error loading configuration from {ConfigPath}", _configPath);
                throw;
            }
        }

        private void ValidateConfiguration(CosmosConfig config)
        {
            if (string.IsNullOrEmpty(config.Cosmos.Endpoint))
                throw new InvalidOperationException("Cosmos endpoint is required");
            
            if (string.IsNullOrEmpty(config.Cosmos.Key))
                throw new InvalidOperationException("Cosmos key is required");
            
            if (config.ConfigWatch.PollIntervalSeconds <= 0)
                throw new InvalidOperationException("Poll interval must be greater than 0");
        }

        private async Task WatchConfigurationChanges()
        {
            while (!_cts.Token.IsCancellationRequested)
            {
                try
                {
                    var currentWriteTime = File.GetLastWriteTime(_configPath);
                    if (currentWriteTime > _lastWriteTime)
                    {
                        _logger.LogInformation("Configuration file changed, reloading...");
                        var newConfig = LoadConfiguration();
                        _currentConfig = newConfig;
                        _lastWriteTime = currentWriteTime;
                        ConfigurationChanged?.Invoke(this, newConfig);
                    }

                    await Task.Delay(TimeSpan.FromSeconds(_currentConfig.ConfigWatch.PollIntervalSeconds), _cts.Token);
                }
                catch (OperationCanceledException)
                {
                    break;
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Error watching configuration file");
                    await Task.Delay(TimeSpan.FromSeconds(5), _cts.Token);
                }
            }
        }

        public CosmosConfig GetConfiguration()
        {
            return _currentConfig;
        }

        public void Dispose()
        {
            _cts.Cancel();
            _cts.Dispose();
        }
    }
} 