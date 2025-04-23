# Build Aggregator Feature Plan

This document outlines the steps to add schematization, sanitization, and aggregation functionality to the Cosmos Uploader, controlled via the configuration file.

## Phase 1: Configuration and Logic Flow

- [ ] **Update Configuration Structure:**
    - [ ] Define a `ProcessingSettings` class (with `Schematize`, `Sanitize`, `Aggregate` booleans).
    - [ ] Add a `Processing` property (of type `ProcessingSettings`) to the main `CosmosConfig` class.
    - [ ] Update `cosmos-config.yaml` to include a `processing:` section with the boolean flags (e.g., `schematize: false`).
- [ ] **Modify `Program.cs`:**
    - [ ] Map the new `processing` section from `CosmosConfig` to `AppSettings`.
    - [ ] **In the handler body, enforce ordering based on config values:**
        - [ ] If `sanitize` is `true` but `schematize` is `false` in config → error exit (“Cannot sanitize before schematization”)
        - [ ] If `aggregate` is `true` but `sanitize` is `false` in config → error exit (“Cannot aggregate before sanitization”)
    - [ ] **Introduce an enum or string variable `stage`** that resolves based on config values to one of:
        - [ ] `"raw"` (no flags true)
        - [ ] `"schematized"` (`schematize: true`)
        - [ ] `"sanitized"` (`schematize: true`, `sanitize: true`)
        - [ ] `"aggregated"` (`schematize: true`, `sanitize: true`, `aggregate: true`)
    - [ ] Store the determined `stage` in `AppSettings`.
    - [ ] **Refactor upload logic** (placeholder) to eventually branch on `stage`:
        - [ ] For `"schematized"` ⇒ call schema‐validation/transform service
        - [ ] For `"sanitized"` ⇒ call PII‐masking service
        - [ ] For `"aggregated"` ⇒ call aggregation service
    - [ ] **Implement basic live config reload** (optional but included) in continuous mode loop to update `stage`.

## Phase 2: Processing Services

- [ ] **Create or update three processing classes/methods if not already present:**
    - [ ] `SchemaProcessor.Process(...)`
    - [ ] `SanitizeProcessor.Process(...)`
    - [ ] `AggregateProcessor.Process(...)`
- [ ] **Ensure each processor writes the output document back to Cosmos DB** with a `"stage"` property set to the current stage
- [ ] **Register processor services** in `Program.cs` dependency injection container.
- [ ] **Update upload logic** in `Program.cs` (continuous and single modes) to call the correct processor chain based on the determined `stage`.

## Phase 3: Testing

- [ ] **Add or update unit tests for each stage path:**
    - [ ] Config `processing` flags all false ⇒ raw upload only
    - [ ] Config `schematize: true` ⇒ raw → structured
    - [ ] Config `schematize: true, sanitize: true` ⇒ raw → structured → sanitized
    - [ ] All three config flags true ⇒ full pipeline
- [ ] **Update integration test or sample run script** to exercise each config combination and verify document counts and `"stage"` tags

## Phase 4: Documentation and Release

- [ ] **Enhance logging** in `Program.cs` and processors to include the chosen stage and configured flag values at startup and during processing.
- [ ] **Update the README or user guide section on “Configuration”** to document the new `processing` section in the YAML file, its flags, defaults, and examples.
- [ ] **Bump the application version** in `csproj` or assembly info, commit, and tag a new release 