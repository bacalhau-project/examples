using CosmosUploader.Models;
using Microsoft.Extensions.Logging;
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;

namespace CosmosUploader.Services
{
    public class AnomalyDetector : IAnomalyDetector
    {
        private readonly ILogger<AnomalyDetector> _logger;
        private const int BASELINE_SAMPLE_SIZE = 100;
        private const double ANOMALY_THRESHOLD = 0.10; // 10% threshold
        
        // Track readings for each metric
        private readonly ConcurrentDictionary<string, List<double>> _readings = new();
        
        // Track calculated averages for each metric after baseline is established
        private readonly ConcurrentDictionary<string, double> _averages = new();
        
        // Track count of processed readings for baseline calculation
        private int _baselineCount = 0;
        private readonly object _lockObject = new object();
        
        // List of metrics to track
        private readonly List<string> _trackedMetrics = new() 
        { 
            "Temperature", 
            "Vibration", 
            "Voltage", 
            "Humidity" 
        };
        
        public AnomalyDetector(ILogger<AnomalyDetector> logger)
        {
            _logger = logger ?? throw new ArgumentNullException(nameof(logger));
            
            // Initialize collections for each tracked metric
            foreach (var metric in _trackedMetrics)
            {
                _readings[metric] = new List<double>();
            }
        }
        
        public async Task<SensorReading> ProcessReadingAsync(SensorReading reading)
        {
            if (reading == null)
                throw new ArgumentNullException(nameof(reading));
                
            // Process each metric that has a value
            ProcessMetric(reading.Temperature, "Temperature", reading);
            ProcessMetric(reading.Vibration, "Vibration", reading);
            ProcessMetric(reading.Voltage, "Voltage", reading);
            ProcessMetric(reading.Humidity, "Humidity", reading);
            
            return await Task.FromResult(reading);
        }
        
        private void ProcessMetric(double? value, string metricName, SensorReading reading)
        {
            if (!value.HasValue)
                return;
                
            lock (_lockObject)
            {
                // If we're still building our baseline (first 100 readings)
                if (_baselineCount < BASELINE_SAMPLE_SIZE)
                {
                    _readings[metricName].Add(value.Value);
                    
                    // If we've reached 100 readings for any metric, calculate the average
                    if (_readings[metricName].Count == BASELINE_SAMPLE_SIZE)
                    {
                        double average = _readings[metricName].Average();
                        _averages[metricName] = average;
                        _logger.LogInformation("Baseline established for {Metric}: {Average}", metricName, average);
                    }
                    
                    // Update the baseline count only once per reading regardless of metrics
                    if (metricName == _trackedMetrics.First() && _baselineCount < BASELINE_SAMPLE_SIZE)
                    {
                        _baselineCount++;
                        if (_baselineCount == BASELINE_SAMPLE_SIZE)
                        {
                            _logger.LogInformation("Baseline of {Count} readings completed. Beginning anomaly detection.", BASELINE_SAMPLE_SIZE);
                        }
                    }
                }
                else
                {
                    // If we already have an average for this metric, check for anomalies
                    if (_averages.TryGetValue(metricName, out double average))
                    {
                        double deviation = Math.Abs(value.Value - average) / average;
                        
                        // If deviation is greater than threshold, mark as anomaly
                        if (deviation > ANOMALY_THRESHOLD)
                        {
                            reading.AnomalyFlag = true;
                            reading.AnomalyType = string.IsNullOrEmpty(reading.AnomalyType)
                                ? $"{metricName} deviation of {deviation:P0}"
                                : $"{reading.AnomalyType}, {metricName} deviation of {deviation:P0}";
                                
                            _logger.LogWarning("Anomaly detected: {SensorId} {Metric} value {Value} deviates by {Deviation:P0} from average {Average}",
                                reading.SensorId, metricName, value.Value, deviation, average);
                        }
                    }
                }
            }
        }
        
        public Task<IDictionary<string, double>> GetAveragesAsync()
        {
            return Task.FromResult<IDictionary<string, double>>(_averages);
        }
        
        public Task<int> GetBaselineCountAsync()
        {
            return Task.FromResult(_baselineCount);
        }
    }
} 