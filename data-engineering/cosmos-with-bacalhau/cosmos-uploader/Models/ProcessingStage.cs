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
            // Common fields required for all processing stages
            public static readonly HashSet<string> CommonFields = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
            {
                // Basic Identification
                "id",           // Unique identifier for the document
                "sensorId",     // Unique identifier for the sensor
                "timestamp",    // Time when reading was taken
                
                // Location and Processing
                "location",     // Location where the sensor is located (Partition Key)
                "processingStage"  // Processing stage marker
            };

            // Fields required/populated for Raw stage
            public static readonly HashSet<string> Raw = new HashSet<string>(CommonFields, StringComparer.OrdinalIgnoreCase)
            {
                "rawDataString" // The original raw data string from the sensor
            };

            // Fields required/populated for Schematized stage
            public static readonly HashSet<string> Schematized = new HashSet<string>(CommonFields, StringComparer.OrdinalIgnoreCase)
            {
                // Sensor Readings
                "temperature",      // Sensor reading: Temperature
                "vibration",        // Sensor reading: Vibration
                "voltage",          // Sensor reading: Voltage
                "humidity",         // Sensor reading: Humidity
                "status",           // Sensor status
                
                // Anomaly Information
                "anomalyFlag",      // True if this reading indicates an anomaly
                "anomalyType",      // Type of anomaly
                
                // Metadata Fields
                "firmwareVersion",  // Sensor firmware version
                "model",            // Sensor model
                "manufacturer",     // Sensor manufacturer
                
                // Location (precise for Schematized)
                "lat",              // Latitude
                "long"              // Longitude
            };

            // Fields required/populated for Sanitized stage (same fields as Schematized but with sanitized location)
            public static readonly HashSet<string> Sanitized = new HashSet<string>(Schematized, StringComparer.OrdinalIgnoreCase);

            // Fields required/populated for Aggregated stage
            public static readonly HashSet<string> Aggregated = new HashSet<string>(CommonFields, StringComparer.OrdinalIgnoreCase)
            {
                // Sensor Readings (averaged or representative values)
                "temperature",      // Sensor reading: Temperature
                "vibration",        // Sensor reading: Vibration
                "voltage",          // Sensor reading: Voltage
                "humidity",         // Sensor reading: Humidity
                "status",           // Sensor status
                
                // Anomaly Information
                "anomalyFlag",      // True if this reading indicates an anomaly
                "anomalyType",      // Type of anomaly
                
                // Metadata Fields
                "firmwareVersion",  // Sensor firmware version
                "model",            // Sensor model
                "manufacturer",     // Sensor manufacturer
                
                // Location
                "lat",              // Latitude
                "long",             // Longitude
                
                // Aggregation Fields
                "aggregationWindowStart", // Start timestamp of the aggregation window
                "aggregationWindowEnd"    // End timestamp of the aggregation window
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