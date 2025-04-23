using Microsoft.Azure.Cosmos;
using Parquet.Data;

namespace CosmosUploader.Configuration
{
    public class AppSettings
    {
        public required CosmosSettings Cosmos { get; set; }
        public required PerformanceSettings Performance { get; set; }
        public required LoggingSettings Logging { get; set; }
        public List<CitySettings>? Cities { get; set; }
        public bool DevelopmentMode { get; set; } = false;
        public bool DebugMode { get; set; } = false;
        public string ProcessingStage { get; set; } = "Raw"; // Default to Raw stage
    }

    public class CosmosSettings
    {
        public required string Endpoint { get; set; }
        public required string Key { get; set; }
        public required string DatabaseName { get; set; }
        public required string ContainerName { get; set; }
        public required string PartitionKey { get; set; }
        public string? ResourceGroup { get; set; }
        public ConnectionSettings? Connection { get; set; }
        public CosmosPerformanceSettings? Performance { get; set; }
        
        // Validate that we have all required fields
        public bool IsValid()
        {
            return !string.IsNullOrEmpty(Endpoint) &&
                   !string.IsNullOrEmpty(Key) &&
                   !string.IsNullOrEmpty(DatabaseName) &&
                   !string.IsNullOrEmpty(ContainerName) &&
                   !string.IsNullOrEmpty(PartitionKey);
        }
    }

    public class ConnectionSettings
    {
        public string Mode { get; set; } = "Gateway";
        public int MaxRetryAttempts { get; set; } = 9;
        public int MaxRetryWaitTimeInSeconds { get; set; } = 30;
        public int ConnectionTimeout { get; set; } = 60;
        public bool EnableEndpointDiscovery { get; set; } = true;
    }

    public class CosmosPerformanceSettings
    {
        public bool EnableEndpointDiscovery { get; set; } = true;
        public bool BulkExecution { get; set; } = true;
        public List<string> PreferredRegions { get; set; } = new();
    }

    public class CitySettings
    {
        public required string Name { get; set; }
        public required double Latitude { get; set; }
        public required double Longitude { get; set; }
    }

    public class PerformanceSettings
    {
        public bool Autoscale { get; set; } = true;
        public bool DisableIndexingDuringBulk { get; set; } = false;
        public int SleepInterval { get; set; } = 60;
    }

    public class LoggingSettings
    {
        public string Level { get; set; } = "INFO";
        public bool LogRequestUnits { get; set; } = true;
        public bool LogLatency { get; set; } = true;
    }
}