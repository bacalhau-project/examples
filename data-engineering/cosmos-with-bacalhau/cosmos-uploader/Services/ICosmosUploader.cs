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
        Task InitializeAsync(CancellationToken cancellationToken);
        // Use DataTypes.DataItem directly
        Task UploadDataAsync(List<DataTypes.DataItem> data, string dataPath, CancellationToken cancellationToken);
        Task<int> GetContainerItemCountAsync();
        Task<long> GetTotalRequestUnitsAsync();
    }
}