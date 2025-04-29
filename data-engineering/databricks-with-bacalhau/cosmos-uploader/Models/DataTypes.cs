using System.Collections.Generic;

namespace CosmosUploader.Models
{
    /// <summary>
    /// Central location for data type definitions used across the application
    /// </summary>
    public static class DataTypes
    {
        /// <summary>
        /// Represents a flexible data item that can hold various types of values
        /// </summary>
        public class DataItem : Dictionary<string, object>
        {
            public DataItem() : base() { }
            public DataItem(IDictionary<string, object> dictionary) : base(dictionary) { }
        }
    }
} 