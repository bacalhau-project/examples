using CosmosUploader.Services;
using Microsoft.Data.Sqlite;
using Microsoft.Azure.Cosmos;
using System.Text.Json;
using Microsoft.Extensions.Configuration;

namespace CosmosUploader.Processors
{
    public class DataProcessor
    {
        private readonly SqliteReaderService _sqliteReader;
        private readonly SyncStateService _syncState;
        private readonly CosmosClient _cosmosClient;
        private readonly IConfiguration _config;
        private readonly int _batchSize;
        private readonly int _maxParallelOperations;
        private readonly int _sleepInterval;

        public DataProcessor(
            string dbPath,
            IConfiguration config)
        {
            _sqliteReader = new SqliteReaderService(dbPath);
            _syncState = new SyncStateService();
            _config = config;

            // Initialize CosmosClient with configuration
            var cosmosConfig = config.GetSection("cosmos");
            _cosmosClient = new CosmosClient(
                cosmosConfig["endpoint"],
                cosmosConfig["key"],
                new CosmosClientOptions
                {
                    AllowBulkExecution = true,
                    MaxRetryAttemptsOnRateLimitedRequests = 9,
                    MaxRetryWaitTimeOnRateLimitedRequests = TimeSpan.FromSeconds(30)
                }
            );

            // Get performance settings
            var perfConfig = config.GetSection("performance");
            _batchSize = perfConfig.GetValue<int>("batch_size", 1000);
            _maxParallelOperations = perfConfig.GetValue<int>("max_parallel_operations", 20);
            _sleepInterval = perfConfig.GetValue<int>("sleep_interval", 10);
        }

        public async Task ProcessNewDataAsync()
        {
            // Get the last ID we processed
            var lastId = await _syncState.GetLastSyncedIdAsync();

            // Query for new data
            var sql = "SELECT * FROM your_table WHERE id > @lastId ORDER BY id";
            var parameters = new[] { new SqliteParameter("@lastId", lastId) };

            var newData = await _sqliteReader.QueryAsync(sql, reader => new
            {
                Id = reader.GetInt64(0),
                Data = reader.GetString(1),
                Timestamp = reader.GetDateTime(2),
                City = reader.GetString(3) // Assuming city is used for partitioning
            }, parameters);

            var container = _cosmosClient.GetContainer(
                _config["cosmos:database_name"],
                _config["cosmos:container_name"]
            );

            // Process in batches
            var batches = newData.Chunk(_batchSize);
            foreach (var batch in batches)
            {
                var tasks = new List<Task>();
                foreach (var item in batch)
                {
                    try
                    {
                        var document = new
                        {
                            id = Guid.NewGuid().ToString(),
                            sourceId = item.Id,
                            data = item.Data,
                            timestamp = item.Timestamp,
                            city = item.City, // Partition key
                            processedAt = DateTime.UtcNow
                        };

                        tasks.Add(container.CreateItemAsync(document));

                        // Respect max parallel operations
                        if (tasks.Count >= _maxParallelOperations)
                        {
                            await Task.WhenAll(tasks);
                            tasks.Clear();
                            await Task.Delay(_sleepInterval);
                        }
                    }
                    catch (Exception ex)
                    {
                        Console.WriteLine($"Error processing item {item.Id}: {ex.Message}");
                    }
                }

                // Wait for any remaining tasks
                if (tasks.Any())
                {
                    await Task.WhenAll(tasks);
                }

                // Update the last processed ID from the batch
                if (batch.Any())
                {
                    await _syncState.UpdateLastSyncedIdAsync(batch.Last().Id);
                }
            }
        }
    }
}