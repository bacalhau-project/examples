using System;
using YamlDotNet.Serialization;

namespace CosmosUploader.Configuration
{
    public class CosmosConfig
    {
        [YamlMember(Alias = "cosmos")]
        public CosmosSettings Cosmos { get; set; } = new CosmosSettings
        {
            Endpoint = string.Empty,
            Key = string.Empty,
            DatabaseName = "SensorData",
            ContainerName = "SensorReadings",
            PartitionKey = "/city"
        };

        [YamlMember(Alias = "performance")]
        public PerformanceSettings Performance { get; set; } = new();

        [YamlMember(Alias = "logging")]
        public LoggingSettings Logging { get; set; } = new();

        [YamlMember(Alias = "config_watch")]
        public ConfigWatchSettings ConfigWatch { get; set; } = new();
    }

    public class ConfigWatchSettings
    {
        [YamlMember(Alias = "enabled")]
        public bool Enabled { get; set; } = true;

        [YamlMember(Alias = "poll_interval_seconds")]
        public int PollIntervalSeconds { get; set; } = 5;
    }
}
