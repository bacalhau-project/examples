using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using YamlDotNet.Serialization;

namespace CosmosUploader.Configuration
{
    public class CosmosConfig
    {
        [YamlMember(Alias = "cosmos")]
        public required CosmosSettings Cosmos { get; set; }

        [YamlMember(Alias = "performance")]
        public required PerformanceSettings Performance { get; set; }

        [YamlMember(Alias = "logging")]
        public required LoggingSettings Logging { get; set; }

        [YamlMember(Alias = "config_watch")]
        public ConfigWatchSettings ConfigWatch { get; set; } = new();

        [YamlMember(Alias = "processing")]
        public ProcessingSettings? Processing { get; set; }
    }

    public class ConfigWatchSettings
    {
        [YamlMember(Alias = "enabled")]
        public bool Enabled { get; set; } = true;

        [YamlMember(Alias = "poll_interval_seconds")]
        public int PollIntervalSeconds { get; set; } = 5;
    }

    public class ProcessingSettings
    {
        [YamlMember(Alias = "processors")]
        public List<string>? Processors { get; set; }

        [YamlMember(Alias = "aggregation")]
        public AggregationSettings? Aggregation { get; set; }
    }

    public class AggregationSettings
    {
        [YamlMember(Alias = "window")]
        public required string Window { get; set; }
    }

    public class PerformanceSettings
    {
        [YamlMember(Alias = "upload_interval_seconds")]
        public int UploadIntervalSeconds { get; set; } = 30;

        [YamlMember(Alias = "upload_jitter_seconds")]
        public int UploadJitterSeconds { get; set; } = 10;

        [YamlMember(Alias = "disable_indexing_during_bulk")]
        public bool DisableIndexingDuringBulk { get; set; } = false;

        [YamlMember(Alias = "sleep_interval")]
        public int SleepInterval { get; set; } = 60;

        [YamlMember(Alias = "autoscale")]
        public bool Autoscale { get; set; } = true;
    }

    public class CosmosSettings
    {
        public required string Endpoint { get; set; }
        public required string Key { get; set; }
        public required string DatabaseName { get; set; }
        public required string ContainerName { get; set; }
        public required string PartitionKey { get; set; }
        public string? ResourceGroup { get; set; }
    }

    public class LoggingSettings
    {
        public string Level { get; set; } = "INFO";
        public bool LogRequestUnits { get; set; } = true;
        public bool LogLatency { get; set; } = true;
    }
}
