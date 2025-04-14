using System;
using Newtonsoft.Json;
using System.ComponentModel.DataAnnotations;

namespace CosmosUploader.Models
{
    public class SensorReading
    {
        [JsonProperty("id")]
        public required string Id { get; set; }
        
        [JsonProperty("sensorId")]
        public required string SensorId { get; set; }
        
        [JsonProperty("timestamp")]
        public required DateTime Timestamp { get; set; }
        
        [JsonProperty("temperature")]
        public required double? Temperature { get; set; }
        
        [JsonProperty("humidity")]
        public required double? Humidity { get; set; }
        
        [JsonProperty("pressure")]
        public required double? Pressure { get; set; }
        
        [JsonProperty("vibration")]
        public required double? Vibration { get; set; }
        
        [JsonProperty("voltage")]
        public required double? Voltage { get; set; }
        
        [JsonProperty("status")]
        public required string Status { get; set; }
        
        [JsonProperty("location")]
        public required string Location { get; set; }
        
        [JsonProperty("city")]
        public required string City { get; set; }
        
        [JsonProperty("processed")]
        public required bool Processed { get; set; } = false;
    }
}
