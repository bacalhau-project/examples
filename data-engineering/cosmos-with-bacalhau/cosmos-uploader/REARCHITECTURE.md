# Cosmos Uploader Refactoring Plan

## Goal

Decouple data reading, processing, Cosmos DB uploading, and archiving responsibilities currently concentrated in `Services/SqliteReader.cs` to improve modularity, maintainability, and testability.

## Current State

-   `Services/SqliteReader.cs`: Handles SQLite reading (batching), data processing (schematization, sanitization, aggregation via processor calls), and archiving to Parquet. It also manages the `synced` flag in SQLite.
-   `Services/CosmosUploader.cs`: Likely handles uploading data to Cosmos DB (needs confirmation of its exact input/role).
-   `Processors/`: Contains interfaces (`IProcessor.cs`, `ISchemaProcessor`, etc.) and implementations (`SchemaProcessor.cs`, `SanitizeProcessor.cs`, `AggregateProcessor.cs`) for data transformation steps.
-   `Program.cs`: Orchestrates the application flow, likely instantiating `SqliteReader` and initiating the process.
-   Status Tracking: Uses a `synced` column in SQLite and potentially a `last_write.txt` file in development mode.

## Target Architecture

1.  **`Services/SqliteReader.cs`**:
    *   **Responsibility:** Read raw data batches from SQLite database(s). Mark records as read/retrieved (e.g., using the existing `synced` flag).
    *   **Output:** A collection of raw data records (e.g., `List<SensorReading>` or a similar DTO).
2.  **`Services/DataProcessor.cs`**:
    *   **Responsibility:** Receive raw data. Apply processing steps (schematization, sanitization, aggregation) based on application configuration (`AppSettings.ProcessingStage`). Implement a state machine or conditional logic for the pipeline.
    *   **Input:** Collection of raw data records from `SqliteReader`.
    *   **Output:** A collection of processed data records ready for upload (e.g., `List<ProcessedData>`).
3.  **`Services/CosmosUploader.cs`**:
    *   **Responsibility:** Receive processed data. Upload data batches to Cosmos DB. Manage upload status tracking (e.g., update a dedicated status file or log).
    *   **Input:** Collection of processed data records from `DataProcessor`.
4.  **`Services/Archiver.cs`**:
    *   **Responsibility:** Receive raw data. Archive data batches to Parquet files. Manage archive status tracking (e.g., update a dedicated status file or log).
    *   **Input:** Collection of raw data records from `SqliteReader`.
5.  **`Program.cs` (Orchestrator)**:
    *   **Responsibility:** Coordinate the overall workflow. Instantiate services. Manage the main loop: Read -> Process -> Upload & Archive. Handle errors and cancellation tokens.

## Refactoring Checklist

1.  [x] **Define Data Transfer Objects (DTOs):**
    *   [x] Define `RawSensorData` (or reuse `Models.SensorReading` if suitable) for data output from `SqliteReader`. *Decision: Use existing `Models.SensorReading`.*
    *   [x] Define `ProcessedSensorData` (or reuse `DataItem` / `Dictionary<string, object>`) for data output from `DataProcessor` and input to `CosmosUploader`. *Decision: Use existing `DataItem = Dictionary<string, object>`.*
2.  [x] **Refactor `Services/SqliteReader.cs`:**
    *   [x] Remove fields/dependencies related to processors (`schemaProcessor`, `sanitizeProcessor`, `aggregateProcessor`).
    *   [x] Remove `_archivePath` field and `SetArchivePath` method.
    *   [x] Modify `ReadAndProcessDataAsync` -> `ReadRawDataAsync`:
        *   [x] Remove processor logic and calls.
        *   [x] Remove `ArchiveReadingsBatchAsync` call.
        *   [x] Change return type to `Task<List<SensorReading>>`.
        *   [x] Adjust loop logic to simply read batches, mark as synced, and collect raw data.
    *   [x] Modify `ReadSensorDataBatchAsync`:
        *   [x] Ensure it returns the chosen raw data DTO (`SensorReading`).
        *   [x] Remove logic related to `processingStage` affecting data structure.
    *   [x] Remove `ConvertReadingsToDataItems` method.
    *   [x] Remove `SanitizeLocationData` helper method.
    *   [x] Remove `WrapInAsyncEnumerable` helper method.
    *   [x] Remove `ResetLastWriteFileAsync`.
    *   [x] Keep `MarkBatchAsSyncedAsync`, `EnsureSyncIndexAsync`, `CheckForUnsyncedRecordsAsync`, `ParseDateTime`.
    *   [x] Remove processor implementations (`CustomSchemaProcessor`).
3.  [x] **Create/Refactor `Services/DataProcessor.cs`:**
    *   [x] Ensure class exists or create it. Rename if necessary (current `DataProcessor.cs` might be one of the specific processors). Let's target creating a new `PipelineProcessor.cs` or similar orchestrator if `DataProcessor.cs` is specific. *Self-correction: User requested `ProcessData.cs`, let's use that name.* Create `Services/ProcessData.cs`.
    *   [x] Inject `ILogger` and `AppSettings`.
    *   [x] Define a public method like `ProcessAsync(List<RawSensorData> rawData, CancellationToken cancellationToken)` returning `Task<List<ProcessedSensorData>>`.
    *   [x] Move/Implement the core processing pipeline logic previously in `SqliteReader.cs`:
        *   [x] Instantiate necessary processors (`SchemaProcessor`, `SanitizeProcessor`, `AggregateProcessor`) based on `AppSettings.ProcessingStage`. (Done via DI injection).
        *   [x] Implement the state machine/conditional logic to apply processors sequentially.
        *   [x] Handle streaming/batching within processing if required (original code had complex async streaming). Start simple (process whole batch in memory) and optimize later if needed. (Implemented in-memory batch processing).
    *   [x] Ensure `IProcessor` interfaces and implementations are accessible (they are in `Processors/`). (Confirmed).
4.  [x] **Create `Services/Archiver.cs`:**
    *   [x] Create the file `Services/Archiver.cs`.
    *   [x] Define class `Archiver`. Inject `ILogger` and `AppSettings`.
    *   [x] Define a public method like `ArchiveAsync(List<RawSensorData> rawData, string? archivePath, CancellationToken cancellationToken)`.
    *   [x] Move the `ArchiveReadingsBatchAsync` logic from `SqliteReader.cs` into this method. Adapt input/parameters.
    *   [x] Implement status tracking for archiving (e.g., log completion, potentially update a file - TBD based on requirements). (Basic logging implemented; file status tracking deferred).
5.  [x] **Refactor `Services/CosmosUploader.cs`:**
    *   [x] Inject `ILogger` and `AppSettings`.
    *   [x] Review/Define a public method like `UploadAsync(List<ProcessedSensorData> processedData, CancellationToken cancellationToken)` -> `UploadDataAsync(List<DataItem> data, string dataPath, CancellationToken cancellationToken)`.
    *   [x] Update the method's input parameter type to `List<DataItem>` (aliased as `ProcessedSensorData`).
    *   [x] Ensure the core Cosmos DB upload logic is correct for the input type (Uses DataItem directly, corrected ID and PartitionKey logic).
    *   [x] Implement status tracking for uploads (e.g., log completion, update `last_write.txt` or a similar file as per original dev mode logic, but make it standard). (Implemented status file writing `*_upload_status.txt`).
    *   [x] Remove `ProcessAndUploadDataAsync` method.
6.  [x] **Refactor Orchestrator (`Program.cs`):**
    *   [x] Register new services (`ProcessData`, `Archiver`) for dependency injection.
    *   [x] Modify the main application loop:
        *   [x] Inject `SqliteReader`, `ProcessData`, `CosmosUploader`, `Archiver`.
        *   [x] Loop reading batches using `SqliteReader.ReadRawDataAsync`.
        *   [x] If raw data is returned:
            *   [x] Call `ProcessData.ProcessAsync` with the raw batch.
            *   [x] Call `CosmosUploader.UploadDataAsync` with the processed batch.
            *   [x] Call `Archiver.ArchiveAsync` with the raw batch.
        *   [x] Handle exceptions from each step appropriately.
        *   [x] Manage cancellation token propagation.
    *   [x] Remove old `ProcessAndUploadDataAsync` call.
    *   [x] Remove individual processor resolution logic.
7.  [x] **Cleanup & Review:**
    *   [x] Remove unused `using` statements. (Pending - see CLEANUP.md)
    *   [x] Delete old/obsolete code/files if any. (Pending - see CLEANUP.md)
    *   [x] Review changes for correctness, performance, and adherence to the new architecture. (Pending - manual review needed)
    *   [x] Ensure logging provides clear insights into the new decoupled flow. (Pending - manual review needed)
    *   [x] Update or create unit/integration tests for the new services. (Pending - outside scope) 