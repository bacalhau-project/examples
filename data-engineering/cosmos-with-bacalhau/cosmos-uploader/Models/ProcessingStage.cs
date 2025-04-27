using System;

namespace CosmosUploader.Models
{
    /// <summary>
    /// Enum representing the data processing stages in the pipeline
    /// </summary>
    public enum ProcessingStage
    {
        Raw,
        Schematized,
        Sanitized,
        Aggregated
    }

    /// <summary>
    /// Static class providing string constants and conversion utilities for processing stages
    /// </summary>
    public static class ProcessingStages
    {
        // String constants for backward compatibility
        public const string Raw = "Raw";
        public const string Schematized = "Schematized";
        public const string Sanitized = "Sanitized";
        public const string Aggregated = "Aggregated";

        /// <summary>
        /// Converts ProcessingStage enum to its string representation
        /// </summary>
        public static string ToString(ProcessingStage stage) => stage.ToString();

        /// <summary>
        /// Attempts to parse a string into a ProcessingStage enum value
        /// </summary>
        public static bool TryParse(string? value, out ProcessingStage stage)
        {
            if (string.IsNullOrEmpty(value))
            {
                stage = ProcessingStage.Raw;
                return false;
            }

            return Enum.TryParse(value, true, out stage);
        }

        /// <summary>
        /// Gets the next stage in the processing pipeline
        /// </summary>
        public static ProcessingStage GetNextStage(ProcessingStage currentStage)
        {
            return currentStage switch
            {
                ProcessingStage.Raw => ProcessingStage.Schematized,
                ProcessingStage.Schematized => ProcessingStage.Sanitized,
                ProcessingStage.Sanitized => ProcessingStage.Aggregated,
                ProcessingStage.Aggregated => ProcessingStage.Aggregated, // No next stage
                _ => throw new ArgumentOutOfRangeException(nameof(currentStage))
            };
        }
    }
}