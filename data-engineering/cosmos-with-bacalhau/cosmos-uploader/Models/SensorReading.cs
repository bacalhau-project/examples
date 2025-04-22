using System;
using Newtonsoft.Json;
using System.ComponentModel.DataAnnotations;

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
        }

        [JsonProperty("id")]
        public string Id { get; set; }
        
        [JsonProperty("sensorId")]
        public string SensorId { get; set; }
        
        [JsonProperty("timestamp")]
        public DateTime Timestamp { get; set; }
        
        [JsonProperty("temperature")]
        public double? Temperature { get; set; }
        
        [JsonProperty("vibration")]
        public double? Vibration { get; set; }
        
        [JsonProperty("voltage")]
        public double? Voltage { get; set; }
        
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
        
        [JsonProperty("city")]
        public string City { get; set; }
        
        [JsonProperty("processed")]
        public bool Processed { get; set; } = false;
    }
}
