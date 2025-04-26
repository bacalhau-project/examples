using Microsoft.Azure.Cosmos;
using Parquet.Data;
using CosmosUploader.Models;

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
        public List<string> Processors { get; set; } = new List<string>(); // Initialize to empty list
        public TimeSpan? AggregationWindow { get; set; }
        public required string StatusFileSuffix { get; set; }
    }

    public class CitySettings
    {
        public required string Name { get; set; }
        public required double Latitude { get; set; }
        public required double Longitude { get; set; }
    }
}