using Microsoft.Data.Sqlite;
using System.Data;

namespace CosmosUploader.Services
{
    public class SqliteReaderService
    {
        private readonly string _connectionString;

        public SqliteReaderService(string dbPath)
        {
            _connectionString = $"Data Source={dbPath};Mode=ReadOnly;";
        }

        public async Task<IEnumerable<T>> QueryAsync<T>(string sql, Func<IDataReader, T> mapper, params SqliteParameter[] parameters)
        {
            using var connection = new SqliteConnection(_connectionString);
            await connection.OpenAsync();

            // Enable WAL mode for concurrent reads
            using var walCommand = connection.CreateCommand();
            walCommand.CommandText = "PRAGMA journal_mode=WAL;";
            await walCommand.ExecuteNonQueryAsync();

            using var command = connection.CreateCommand();
            command.CommandText = sql;
            command.Parameters.AddRange(parameters);

            var results = new List<T>();
            using var reader = await command.ExecuteReaderAsync();
            while (await reader.ReadAsync())
            {
                results.Add(mapper(reader));
            }

            return results;
        }
    }
} 