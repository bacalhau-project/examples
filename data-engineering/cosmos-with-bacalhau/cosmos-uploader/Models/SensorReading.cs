using Newtonsoft.Json; 
namespace CosmosUploader.Models
{
    public class SensorReading
    {
        public SensorReading()
        {
            Id = Guid.NewGuid().ToString();
            SensorId = "UNKNOWN";
            Timestamp = DateTime.UtcNow;
            Status = "UNKNOWN";
            Location = "UNKNOWN";
            City = "UNKNOWN";
            ProcessingStage = ProcessingStages.Raw.ToString();
        }

        [JsonProperty("id")]
        public string Id { get; set; }
        
        [JsonProperty("sensorId")]
        public string SensorId { get; set; }
        
        [JsonProperty("timestamp")]
        public DateTime Timestamp { get; set; }

        [JsonProperty("city")]
        public string City { get; set; }
        
        [JsonProperty("processingStage")]
        public string ProcessingStage { get; set; }

        [JsonProperty("rawDataString")]
        public string? RawDataString { get; set; }
        
        // New property to store the raw SQLite data
        [JsonIgnore] // Don't include in JSON serialization
        public string? RawSqliteData { get; set; }
        
        [JsonProperty("temperature")]
        public double? Temperature { get; set; }
        
        [JsonProperty("vibration")]
        public double? Vibration { get; set; }
        
        [JsonProperty("voltage")]
        public double? Voltage { get; set; }

        [JsonProperty("humidity")]
        public double? Humidity { get; set; }
        
        [JsonProperty("pressure")]
        public double? Pressure { get; set; }
        
        [JsonProperty("status")]
        public string Status { get; set; }
        
        [JsonProperty("anomalyFlag")]
        public bool AnomalyFlag { get; set; }
        
        [JsonProperty("anomalyType")]
        public string? AnomalyType { get; set; }
        
        [JsonProperty("firmwareVersion")]
        public string? FirmwareVersion { get; set; }
        
        [JsonProperty("model")]
        public string? Model { get; set; }
        
        [JsonProperty("manufacturer")]
        public string? Manufacturer { get; set; }
        
        [JsonProperty("location")]
        public string Location { get; set; }

        [JsonProperty("lat")]
        public string? Lat { get; set; }

        [JsonProperty("long")]
        public string? Long { get; set; }

        [JsonProperty("aggregationWindowStart")]
        public DateTime? AggregationWindowStart { get; set; }

        [JsonProperty("aggregationWindowEnd")]
        public DateTime? AggregationWindowEnd { get; set; }

        [JsonProperty("rawData")]
        public string? RawData { get; set; }
    }

    // Define the processing stages as an enum to ensure consistency
    public enum ProcessingStages
    {
        Raw,
        Schematized,
        Sanitized,
        Aggregated
    }
}
