using System;
using System.IO;
using System.Text.RegularExpressions;
using YamlDotNet.Serialization;
using YamlDotNet.Serialization.NamingConventions;

namespace CosmosUploader.Configuration
{
    public class ConfigurationProvider
    {
        private readonly string _configPath;
        private readonly IDeserializer _deserializer;

        public ConfigurationProvider(string configPath)
        {
            _configPath = configPath ?? throw new ArgumentNullException(nameof(configPath));
            
            // Setup YAML deserializer
            _deserializer = new DeserializerBuilder()
                .WithNamingConvention(UnderscoredNamingConvention.Instance)
                .Build();
        }

        public AppSettings GetAppSettings()
        {
            // Verify the file exists
            if (!File.Exists(_configPath))
            {
                throw new FileNotFoundException($"Configuration file not found: {_configPath}", _configPath);
            }
            
            // Read and process the YAML file
            string yaml = File.ReadAllText(_configPath);
            
            // Expand environment variables in the YAML
            yaml = ExpandEnvironmentVariables(yaml);
            
            // Deserialize the YAML into our settings object
            var settings = _deserializer.Deserialize<AppSettings>(yaml);
            
            // Validate settings
            if (settings.Cosmos == null || !settings.Cosmos.IsValid())
            {
                throw new ArgumentException("Invalid Cosmos DB settings in configuration file");
            }
            
            // Set defaults if not provided
            if (settings.Performance == null)
            {
                settings.Performance = new PerformanceSettings();
            }
            
            if (settings.Logging == null)
            {
                settings.Logging = new LoggingSettings();
            }
            
            return settings;
        }

        // Replace ${ENV_VAR} or ${ENV_VAR:-default} with environment variable values
        private string ExpandEnvironmentVariables(string yaml)
        {
            // Match pattern: ${VAR_NAME} or ${VAR_NAME:-default_value}
            var pattern = @"\${([a-zA-Z0-9_]+)(?::-([^}]*))?}";
            
            return Regex.Replace(yaml, pattern, match =>
            {
                var envVarName = match.Groups[1].Value;
                var defaultValue = match.Groups[2].Success ? match.Groups[2].Value : "";
                
                // Get environment variable or use default
                var envValue = Environment.GetEnvironmentVariable(envVarName);
                return envValue ?? defaultValue;
            });
        }
    }
}