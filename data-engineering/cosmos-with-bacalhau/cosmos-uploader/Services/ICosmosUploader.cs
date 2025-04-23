using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using CosmosUploader.Models;

namespace CosmosUploader.Services
{
    // Define placeholder data type consistent with processors
    using DataItem = System.Collections.Generic.Dictionary<string, object>;

    public interface ICosmosUploader
    {
        Task InitializeAsync(CancellationToken cancellationToken);
        Task UploadDataAsync(IEnumerable<DataItem> data, CancellationToken cancellationToken);
        Task<int> GetContainerItemCountAsync();
        Task<long> GetTotalRequestUnitsAsync();
    }
}