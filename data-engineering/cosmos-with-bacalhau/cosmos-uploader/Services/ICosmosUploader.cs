using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using CosmosUploader.Models; // Added for DataTypes

namespace CosmosUploader.Services
{
    // Removed DataItem alias

    public interface ICosmosUploader
    {
        /// <summary>
        /// Initializes the Cosmos DB connection
        /// </summary>
        Task InitializeAsync(CancellationToken cancellationToken);
        
        /// <summary>
        /// Uploads a batch of data items to Cosmos DB
        /// </summary>
        /// <param name="data">The data items to upload</param>
        /// <param name="dataPath">The source path of the data (for logging/context)</param>
        /// <param name="cancellationToken">Cancellation token</param>
        Task UploadDataAsync(List<DataTypes.DataItem> data, string dataPath, CancellationToken cancellationToken);
        
        /// <summary>
        /// Gets the approximate count of items in the Cosmos container
        /// </summary>
        /// <returns>The number of items, or -1 if the count could not be retrieved</returns>
        Task<int> GetContainerItemCountAsync();
        
        /// <summary>
        /// Gets the total request units consumed by this uploader instance
        /// </summary>
        /// <returns>The total RUs consumed</returns>
        Task<long> GetTotalRequestUnitsAsync();
    }
}