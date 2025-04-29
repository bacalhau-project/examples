using System.Text.Json;
using System.IO;

namespace CosmosUploader.Services
{
    public class SyncStateService
    {
        private readonly string _syncStatePath;
        private readonly JsonSerializerOptions _jsonOptions;

        public SyncStateService(string syncStatePath = "sync_state.json")
        {
            _syncStatePath = syncStatePath;
            _jsonOptions = new JsonSerializerOptions { WriteIndented = true };
        }

        public async Task<long> GetLastSyncedIdAsync()
        {
            if (!File.Exists(_syncStatePath))
            {
                return 0;
            }

            var json = await File.ReadAllTextAsync(_syncStatePath);
            var state = JsonSerializer.Deserialize<SyncState>(json);
            return state?.LastSyncedId ?? 0;
        }

        public async Task UpdateLastSyncedIdAsync(long lastId)
        {
            var state = new SyncState { LastSyncedId = lastId };
            var json = JsonSerializer.Serialize(state, _jsonOptions);
            
            // Write to temp file first, then rename for atomic operation
            var tempPath = _syncStatePath + ".tmp";
            await File.WriteAllTextAsync(tempPath, json);
            File.Move(tempPath, _syncStatePath, overwrite: true);
        }
    }

    public class SyncState
    {
        public long LastSyncedId { get; set; }
    }
} 