using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using CosmosUploader.Models;

namespace CosmosUploader.Services
{
    public interface ICosmosUploader
    {
        Task InitializeAsync(CancellationToken cancellationToken);
        Task UploadReadingsAsync(List<SensorReading> readings, CancellationToken cancellationToken);
        Task<int> GetContainerItemCountAsync();
        Task<long> GetTotalRequestUnitsAsync();
    }
}