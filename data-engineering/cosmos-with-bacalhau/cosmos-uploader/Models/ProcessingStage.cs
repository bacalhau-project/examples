using System;
using System.Collections.Generic;

namespace CosmosUploader.Models
{
    public static class ProcessingStage
    {
        public const string Raw = "Raw";
        public const string Schematized = "Schematized";
        public const string Sanitized = "Sanitized";
        public const string Aggregated = "Aggregated";

        // Validate if a given stage string is valid
        public static bool IsValid(string stage)
        {
            return stage == Raw || stage == Schematized || stage == Sanitized || stage == Aggregated;
        }

        // Get all possible stages
        public static IEnumerable<string> GetAllStages()
        {
            return new[] { Raw, Schematized, Sanitized, Aggregated };
        }

        // Helper method to determine which fields should be populated for a given stage
        public static class FieldRequirements
        {
            // Fields required/populated for Raw stage
            public static readonly HashSet<string> Raw = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
            {
                "id", "sensorId", "timestamp", "city", "location", "processingStage", "rawDataString"
            };

            // Fields required/populated for Schematized stage
            public static readonly HashSet<string> Schematized = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
            {
                "id", "sensorId", "timestamp", "city", "location", "lat", "long", "processingStage",
                "temperature", "vibration", "voltage", "humidity", "status",
                "anomalyFlag", "anomalyType", "firmwareVersion", "model", "manufacturer"
            };

            // Fields required/populated for Sanitized stage (same as Schematized but with sanitized location)
            public static readonly HashSet<string> Sanitized = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
            {
                "id", "sensorId", "timestamp", "city", "location", "lat", "long", "processingStage",
                "temperature", "vibration", "voltage", "humidity", "status",
                "anomalyFlag", "anomalyType", "firmwareVersion", "model", "manufacturer"
            };

            // Fields required/populated for Aggregated stage
            public static readonly HashSet<string> Aggregated = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
            {
                "id", "sensorId", "timestamp", "city", "location", "processingStage",
                "temperature", "vibration", "voltage", "humidity", "status",
                "anomalyFlag", "anomalyType", "firmwareVersion", "model", "manufacturer",
                "aggregationWindowStart", "aggregationWindowEnd"
            };

            // Get fields for a specific stage
            public static HashSet<string> GetForStage(string stage)
            {
                return stage switch
                {
                    ProcessingStage.Raw => Raw,
                    ProcessingStage.Schematized => Schematized,
                    ProcessingStage.Sanitized => Sanitized,
                    ProcessingStage.Aggregated => Aggregated,
                    _ => throw new ArgumentException($"Invalid processing stage: {stage}")
                };
            }
        }
    }
} 