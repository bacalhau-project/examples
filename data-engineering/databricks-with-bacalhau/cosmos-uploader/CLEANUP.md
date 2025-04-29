# Cleanup Findings

This document lists potential cleanup items identified after the refactoring process.

## `Services/SqliteReader.cs`

*   **Unused `using`:** `System.Data` appears unused.
*   **Redundant Check:** `SetDataPath` checks if the directory exists and creates it. `Program.cs` also creates the archive directory. This check might be redundant if `Program.cs` ensures the base SQLite directory exists. However, keeping it might be safer if `SqliteReader` could theoretically be used independently or with paths not validated by `Program.cs`. Consider if this check is necessary here.
*   **Comment:** Line `// This flag seems irrelevant here now, but leave for consistency with model? Or remove from model? Let's leave it for now.` in `ReadSensorDataBatchAsync` regarding `Processed` flag. Decision should be made whether to keep/remove this property from `SensorReading` model if it's truly unused by the reader.

## `Services/ProcessData.cs`

*   **Unused `using`:** `System.Globalization`, `System.Text.Json` appear unused.
*   **Commented Code:** `IAnomalyDetector` is commented out in the constructor and field declarations. Decide if anomaly detection will be added later or remove the commented code.
*   **TODO Comment:** Line `// TODO: Add Anomaly Detection step here if required as a separate stage`. Needs action or removal.

## `Services/Archiver.cs`

*   **Unused `using`:** `CosmosUploader.Configuration` (`AppSettings` is used, but maybe not the full namespace import?).
*   **Redundant Check:** `ArchiveAsync` creates the `archivePath`. `Program.cs` also creates this directory. One of these could potentially be removed. The check in `Program.cs` seems more appropriate as a pre-flight check.
*   **TODO Comment:** Line `// TODO: Implement status tracking if needed...`. Decide if status tracking beyond logging is required for archiving and implement or remove the comment.

## `Services/CosmosUploader.cs`

*   **Unused `using`:** `System.Net.NetworkInformation`, `System.Net`, `CosmosUploader.Processors`, `CosmosUploader.Models` (if `CosmosItem` model is not defined here or needed).
*   **Interface Mismatch:** The class `CosmosUploader` is no longer declared as implementing `ICosmosUploader` (commented out during `Program.cs` refactoring), but `ICosmosUploader.cs` still exists.
    *   The signature of `UploadDataAsync` in `CosmosUploader` (`List<DataItem> data, string dataPath, CancellationToken cancellationToken`) differs from the one in `ICosmosUploader` (`IEnumerable<DataItem> data, CancellationToken cancellationToken`).
    *   **Action:** Either update `ICosmosUploader` to match the new signature (including the `dataPath` parameter) and make `CosmosUploader` implement it again, or delete `ICosmosUploader.cs` if the interface is no longer desired/needed for DI abstraction.
*   **`Models.CosmosItem`:** Check if `Models.CosmosItem` is still needed anywhere in the project, as `CosmosUploader` now uploads `DataItem` directly.
*   **Error Handling:** `UploadDataAsync` logs individual item failures but throws a generic exception at the end if `failedUploads > 0`. Consider if more specific error information or a different return type (e.g., a result object) would be better than a generic exception.
*   **Initialization:** `UploadDataAsync` attempts `InitializeAsync` if `_isInitialized` is false. This might be better enforced by the orchestrator (`Program.cs`) calling `InitializeAsync` once before starting the processing loop.

## `Program.cs`

*   **Unused `using`:** `Microsoft.Azure.Cosmos` (used in `CosmosUploader`, but not directly here), `Polly`, `Polly.Retry`, `System.Net`, `System.Collections`, `Microsoft.Data.Sqlite`.
*   **Commented Code:** Old DI registration for `SqliteReader`, old `ICosmosUploader` registration, old processor resolution logic, extensive old main loop logic (including Polly policies, config reloading, etc.). This should be removed.
*   **Placeholder Config:** The `AppSettings`, `CosmosSettings`, etc., classes are defined *within* `Program.cs` as placeholders. These should ideally live in their own files (e.g., within `CosmosUploader.Configuration` or `CosmosUploader.Models` namespaces) and be integrated with the actual `CosmosConfig` read from YAML. The comments indicate this (`// --- Placeholder/Example Configuration Classes ---`).
*   **Redundant Directory Creation:** Creates the `effectiveArchivePath`. `Archiver.cs` *also* creates this directory. One check can likely be removed.
*   **`ProcessingStage` Enum:** Defined both in `Program.cs` and `Models/ProcessingStage.cs` (based on file list). One definition should be removed. Assume `Models/ProcessingStage.cs` is the canonical one.
*   **DI Registration:** `CosmosUploader` is registered as `services.AddTransient<Services.CosmosUploader>();`. If `ICosmosUploader` is updated and implemented, this should be changed back to `services.AddTransient<ICosmosUploader, Services.CosmosUploader>();`.

## General

*   Review all modified files for consistency in logging levels and messages.
*   Ensure cancellation tokens are respected correctly in all `async` operations.
*   Consider adding XML documentation comments (`/// <summary>...`) to new public classes and methods (`ProcessData`, `Archiver`, and their methods). 