using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using CosmosUploader.Models;

namespace CosmosUploader.Processors
{
    /// <summary>
    /// Base interface for all data processors
    /// </summary>
    public interface IProcessor
    {
        /// <summary>
        /// Gets the name of the processor
        /// </summary>
        string Name { get; }

        /// <summary>
        /// Gets the processing stage this processor handles
        /// </summary>
        ProcessingStage Stage { get; }
    }

    /// <summary>
    /// Interface for schema processors that transform raw data into a structured format
    /// </summary>
    public interface ISchemaProcessor : IProcessor
    {
        /// <summary>
        /// Processes data to ensure it matches the expected schema
        /// </summary>
        /// <param name="data">The data to process</param>
        /// <param name="cancellationToken">Cancellation token</param>
        /// <returns>Processed data matching the schema</returns>
        Task<IEnumerable<DataTypes.DataItem>> ProcessAsync(
            IEnumerable<DataTypes.DataItem> data,
            CancellationToken cancellationToken);

        /// <summary>
        /// Processes data in a streaming fashion to ensure it matches the expected schema
        /// </summary>
        /// <param name="data">The data to process</param>
        /// <param name="cancellationToken">Cancellation token</param>
        /// <returns>Stream of processed data items</returns>
        IAsyncEnumerable<DataTypes.DataItem> ProcessStreamAsync(
            IEnumerable<DataTypes.DataItem> data,
            CancellationToken cancellationToken);
    }

    /// <summary>
    /// Interface for sanitization processors that clean and validate data
    /// </summary>
    public interface ISanitizeProcessor : IProcessor
    {
        /// <summary>
        /// Sanitizes data by removing invalid values and normalizing formats
        /// </summary>
        /// <param name="data">The data to sanitize</param>
        /// <param name="cancellationToken">Cancellation token</param>
        /// <returns>Sanitized data</returns>
        Task<IEnumerable<DataTypes.DataItem>> ProcessAsync(
            IEnumerable<DataTypes.DataItem> data,
            CancellationToken cancellationToken);

        /// <summary>
        /// Sanitizes data in a streaming fashion
        /// </summary>
        /// <param name="data">The data to sanitize</param>
        /// <param name="cancellationToken">Cancellation token</param>
        /// <returns>Stream of sanitized data items</returns>
        IAsyncEnumerable<DataTypes.DataItem> ProcessStreamAsync(
            IAsyncEnumerable<DataTypes.DataItem> data,
            CancellationToken cancellationToken);
    }

    /// <summary>
    /// Interface for aggregation processors that combine and summarize data
    /// </summary>
    public interface IAggregateProcessor : IProcessor
    {
        /// <summary>
        /// Aggregates data based on specified criteria
        /// </summary>
        /// <param name="data">The data to aggregate</param>
        /// <param name="cancellationToken">Cancellation token</param>
        /// <returns>Aggregated data</returns>
        Task<IEnumerable<DataTypes.DataItem>> ProcessAsync(
            IEnumerable<DataTypes.DataItem> data,
            CancellationToken cancellationToken);
    }
} 