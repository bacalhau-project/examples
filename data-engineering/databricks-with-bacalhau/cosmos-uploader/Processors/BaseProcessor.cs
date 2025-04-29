using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using CosmosUploader.Models;

namespace CosmosUploader.Processors
{
    /// <summary>
    /// Base class for all processors that provides common functionality
    /// </summary>
    public abstract class BaseProcessor : IProcessor
    {
        protected readonly ILogger _logger;
        protected readonly string _name;
        protected readonly ProcessingStage _stage;

        protected BaseProcessor(ILogger logger, string name, ProcessingStage stage)
        {
            _logger = logger ?? throw new ArgumentNullException(nameof(logger));
            _name = name ?? throw new ArgumentNullException(nameof(name));
            _stage = stage;
        }

        public string Name => _name;
        public ProcessingStage Stage => _stage;

        /// <summary>
        /// Validates that the processor is appropriate for the current processing stage
        /// </summary>
        protected void ValidateProcessingStage(ProcessingStage currentStage)
        {
            if (Stage != currentStage)
            {
                throw new InvalidOperationException(
                    $"Processor {Name} is configured for {Stage} stage but current stage is {currentStage}");
            }
        }

        /// <summary>
        /// Validates input data is not null or empty
        /// </summary>
        protected void ValidateInputData(IEnumerable<DataTypes.DataItem> data)
        {
            if (data == null)
            {
                throw new ArgumentNullException(nameof(data));
            }
        }

        /// <summary>
        /// Logs the start of processing
        /// </summary>
        protected void LogProcessingStart(int inputCount)
        {
            _logger.LogInformation("Starting {Processor} processing {Count} items", _name, inputCount);
        }

        /// <summary>
        /// Logs the completion of processing
        /// </summary>
        protected void LogProcessingComplete(int inputCount, int outputCount)
        {
            _logger.LogInformation("Completed {Processor} processing. Input: {InputCount}, Output: {OutputCount}",
                _name, inputCount, outputCount);
        }

        /// <summary>
        /// Converts an IEnumerable to IAsyncEnumerable for streaming processing
        /// </summary>
        protected static async IAsyncEnumerable<DataTypes.DataItem> WrapInAsyncEnumerable(IEnumerable<DataTypes.DataItem> data)
        {
            await Task.Yield(); // Yield to allow async context

            foreach (var item in data)
            {
                yield return item;
            }
        }
    }
}