using Microsoft.Azure.Cosmos;
using Parquet.Data;

namespace CosmosUploader.Configuration
{
    public class AppSettings
    {
        public required CosmosSettings Cosmos { get; set; }
        public required PerformanceSettings Performance { get; set; }
        public required LoggingSettings Logging { get; set; }
    }

    public class CosmosSettings
    {
        public required string Endpoint { get; set; }
        public required string Key { get; set; }
        public required string DatabaseName { get; set; }
        public required string ContainerName { get; set; }
        public required string PartitionKey { get; set; }
        
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

    public class PerformanceSettings
    {
        public int Throughput { get; set; } = 400;
        public int BatchSize { get; set; } = 100;
        public int MaxParallelOperations { get; set; } = 10;
    }

    public class LoggingSettings
    {
        public string Level { get; set; } = "INFO";
        public bool LogRequestUnits { get; set; } = true;
        public bool LogLatency { get; set; } = true;
    }
}