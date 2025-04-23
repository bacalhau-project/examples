**Project Title:** Implement Multi-Stage Data Processing for Cosmos DB Uploader

**SCHEMA**:
We have an updated schema for every sensor reading.

```
{
  "id": "string", // Unique identifier for the document (e.g., GUID)
  "sensorId": "string", // ID of the sensor
  "timestamp": "datetime", // Timestamp of the data point (original reading time for Raw/Schematized/Sanitized, end of window for Aggregated)
  "city": "string", // City where the sensor is located (Partition Key)

  // --- Data Processing Stage ---
  // Indicates the primary processing level of the data in this document.
  // Possible values: "Raw", "Schematized", "Sanitized", "Aggregated"
  "processingStage": "string",

  // --- Raw Data ---
  "rawDataString": "string", // The original raw data string from the sensor (primarily populated when processingStage is "Raw", optional otherwise)

  // --- Sensor Readings (Populated for Schematized, Sanitized, Aggregated) ---
  // For "Aggregated", these will store averaged or representative values.
  "temperature": "double", // Sensor reading: Temperature
  "vibration": "double", // Sensor reading: Vibration
  "voltage": "double", // Sensor reading: Voltage
  "humidity": "double", // Sensor reading: Humidity (added based on discussion in transcript)
  "status": "string", // Sensor status

  // --- Anomaly Information (Populated for Schematized, Sanitized, Aggregated where applicable) ---
  "anomalyFlag": "boolean", // True if this reading/aggregate indicates an anomaly
  "anomalyType": "string", // Type of anomaly (e.g., "Temperature High", "Vibration Spike")

  // --- Metadata Fields (Populated for Schematized, Sanitized, Aggregated) ---
  "firmwareVersion": "string", // Sensor firmware version
  "model": "string", // Sensor model
  "manufacturer": "string", // Sensor manufacturer

  // --- Location (Populated for Schematized, Sanitized, Aggregated) ---
  // Value precision depends on the 'processingStage' ("Schematized" is precise, "Sanitized" is less precise)
  "location": "string", // City Name
  "lat": "string", // latitude
  "long": "string", //longitude

  // --- Aggregation Fields (Populated when processingStage is "Aggregated") ---
  "aggregationWindowStart": "datetime", // Start timestamp of the aggregation window
  "aggregationWindowEnd": "datetime" // End timestamp of the aggregation window (should match 'timestamp')
}
```

**Goal:** Modify the existing C# `CosmosUploader` and related components to produce and upload sensor data to Cosmos DB according to the defined multi-stage JSON document structure, enabling the demo scenarios (Raw, Schematized, Sanitized, Aggregated).

**Target Components:**
1.  C# `CosmosUploader` application/service (main focus).
2.  Local SQLite Database interaction logic (within the uploader).
3.  Cosmos DB data model and interaction code (within the uploader).
4.  Configuration mechanism for the uploader.
5.  (Coordination Needed) Data Generation/Simulation (e.g., C# `sunset log generator`, Python scripts).
6.  (Coordination Needed) Frontend/UI and its backend API for querying and display.

**New Document Structure Reference:**
Use the refined JSON structure provided previously, with the `processingStage` field defining the data type ("Raw", "Schematized", "Sanitized", "Aggregated").

**Plan Steps:**

**Phase 1: Foundation & Data Model**

1.  **Review and Understand:**
    * Thoroughly review the provided transcript, the old C# `SensorReading` model, and the new refined JSON document structure.
    * Understand the purpose and expected content for each `processingStage` ("Raw", "Schematized", "Sanitized", "Aggregated").

2.  **Update C# Data Model (`SensorReading.cs` or similar):**
    * Modify or create a C# class (likely extending/replacing the existing `SensorReading`) that precisely matches *all* fields in the new refined JSON document structure.
    * Ensure appropriate `JsonProperty` attributes are used for serialization/deserialization to/from JSON.
    * Include fields for `processingStage` (string), `rawDataString` (string), `aggregationWindowStart` (DateTime), `aggregationWindowEnd` (DateTime), and `humidity` (double?). Ensure existing fields like `temperature`, `vibration`, `voltage`, `location`, `anomalyFlag`, etc., are present. Make nullable types (`double?`, `string?`, `bool?`, `DateTime?`) where fields may not be populated in all `processingStage` types (e.g., aggregation fields in Raw stage).

**Phase 2: Uploader Logic Implementation**

3.  **Implement Uploader Configuration:**
    * Add configuration options to the `CosmosUploader` application (e.g., using environment variables, a config file parser like `Microsoft.Extensions.Configuration`) to specify the desired `processingStage` for the data it will upload *in the current run*. Example configuration: `UPLOADER_PROCESSING_STAGE = "Schematized"`. This configuration will control the logic executed in the next steps.

4.  **Modify SQLite Reading Logic:**
    * Ensure the logic that reads from the local SQLite database can retrieve the necessary raw data string or parsed components needed for subsequent processing stages. It needs access to the fundamental reading data (like the raw string or core values + timestamp, sensor ID).

5.  **Implement Multi-Stage Document Creation Logic:**
    * Refactor the uploader's core processing loop. Based on the configured `UPLOADER_PROCESSING_STAGE`:
        * **If "Raw":** Create `SensorReading` objects where `processingStage` is set to `"Raw"`. Populate `id`, `sensorId`, `timestamp`, `city`, `location`, and `rawDataString` using the raw data read from SQLite. Leave other fields (sensor readings, anomaly, metadata, aggregation) as default/null.
        * **If "Schematized":** Create `SensorReading` objects where `processingStage` is set to `"Schematized"`. Parse the raw data from SQLite to populate all standard fields: `id`, `sensorId`, `timestamp`, `city`, precise `location`, `temperature`, `vibration`, `voltage`, `humidity`, `status`, `anomalyFlag`, `anomalyType`, `firmwareVersion`, `model`, `manufacturer`. Leave `rawDataString` and aggregation fields as default/null.
        * **If "Sanitized":** Create `SensorReading` objects where `processingStage` is set to `"Sanitized"`. This logic should be similar to "Schematized", but apply the GPS sanitization (reducing precision of the `location` string) *before* populating the `location` field in the `SensorReading` object. Leave `rawDataString` and aggregation fields as default/null. Implement the sanitization logic (e.g., truncating the GPS coordinate string to a specific number of decimal places, as discussed).
        * **If "Aggregated":** Implement the aggregation logic. This will require state management within the uploader (e.g., buffering readings for a specific time window per sensor/city). At the end of each window (e.g., every minute), calculate the aggregates (e.g., average temperature, vibration, voltage, humidity) for all readings within that window for a given sensor/city. Create a *single* `SensorReading` object for the window where `processingStage` is set to `"Aggregated"`. Populate `id`, the relevant `sensorId` and `city`, `timestamp` (set to `aggregationWindowEnd`), `aggregationWindowStart`, `aggregationWindowEnd`, the calculated aggregated sensor readings, and carry over `anomalyFlag`/`anomalyType` if applicable based on anomaly rules within the window. Populate `location` with the sensor's location. Leave `rawDataString` and non-aggregate-specific fields as default/null.
    * Ensure consistent handling of `id`, `sensorId`, `timestamp`, `city`, and `location` across all stages where they are populated.

6.  **Update Cosmos DB Insertion Logic:**
    * Modify the code that inserts documents into Cosmos DB to use the new, comprehensive `SensorReading` model.
    * Verify that the `city` field is correctly set on every document and used as the partition key value when inserting.

**Phase 3: Coordination & Testing**

7.  **Coordinate with Data Generation:**
    * Confirm that the data generation source (SQLite DB populated by `sunset log generator` or Python scripts) provides the necessary raw data string or structured data that the updated C# uploader needs to parse and process for *all* intended stages ("Schematized", "Sanitized", "Aggregated"). If the generator needs modification (e.g., to include humidity, firmware, model, manufacturer hints in the raw data string or source data), this is a dependency that needs to be addressed.

8.  **Coordinate with Frontend/API Development:**
    * Communicate the final document structure and the meaning of the `processingStage` field to the frontend/API developer (Sean).
    * Confirm the frontend/API can:
        * Query Cosmos DB filtering by `processingStage` and `timestamp` range.
        * Correctly interpret the data fields based on the `processingStage`.
        * Implement the UI switches/toggles to select which `processingStage` data to display.
        * Develop the throughput visualization by querying total document counts across different `processingStage` types over time.

9.  **Testing:**
    * Write and execute unit tests for the individual processing logic paths (Raw, Schematized, Sanitized, Aggregated) to ensure documents are created correctly with the right fields populated and the right `processingStage` value.
    * Perform integration tests:
        * Run the data generator to populate SQLite.
        * Run the `CosmosUploader` configured for each `processingStage` ("Raw", "Schematized", "Sanitized", "Aggregated") sequentially or in parallel if needed.
        * Verify in Cosmos DB (using Data Explorer or queries) that documents for each stage are created correctly with the expected structure, populated fields, and the correct `city` partition key.
        * Verify that sanitization reduces location precision as expected.
        * Verify that aggregation produces fewer documents per time window with correct averaged values and window times.
    * Coordinate with the frontend developer for end-to-end testing to ensure the UI correctly displays data from each stage.

**Outcome:**
A `CosmosUploader` application capable of being configured via `UPLOADER_PROCESSING_STAGE` to upload sensor data to Cosmos DB formatted as "Raw", "Schematized", "Sanitized", or "Aggregated" documents, enabling the planned demo flow and visualizations on the frontend.