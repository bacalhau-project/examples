using CosmosUploader.Models;
using System.Threading.Tasks;

namespace CosmosUploader.Services
{
    public interface IAnomalyDetector
    {
        /// <summary>
        /// Process a sensor reading to detect anomalies based on averages of the first 100 readings
        /// </summary>
        /// <param name="reading">The sensor reading to process</param>
        /// <returns>The processed reading with anomaly flags set if applicable</returns>
        Task<SensorReading> ProcessReadingAsync(SensorReading reading);
        
        /// <summary>
        /// Gets the current average values for all tracked metrics
        /// </summary>
        /// <returns>A dictionary of metric names and their current average values</returns>
        Task<IDictionary<string, double>> GetAveragesAsync();
        
        /// <summary>
        /// Gets the current count of readings processed for baseline calculation
        /// </summary>
        /// <returns>The number of readings processed so far</returns>
        Task<int> GetBaselineCountAsync();
    }
} 