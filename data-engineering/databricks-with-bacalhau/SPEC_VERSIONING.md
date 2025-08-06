# Validation Specification Versioning Strategy

## Overview

This document outlines the versioning strategy for the `sensor_validation_spec.yaml` file, which controls all validation rules for the Databricks pipeline. Proper versioning ensures backward compatibility, enables safe rollbacks, and provides audit trails for compliance.

## Versioning Principles

### 1. Semantic Versioning

We follow semantic versioning (SemVer) for the validation specification:

- **MAJOR.MINOR.PATCH** (e.g., 1.2.3)
  - **MAJOR**: Breaking changes that require code updates
  - **MINOR**: New features that are backward compatible
  - **PATCH**: Bug fixes and minor adjustments

### 2. Version Increment Rules

#### MAJOR Version (Breaking Changes)
- Removing required fields
- Changing field types (e.g., string to float)
- Renaming fields
- Removing validation rules
- Changing the spec structure

#### MINOR Version (New Features)
- Adding new optional fields
- Adding new validation rules
- Adding new routing rules
- Adding new emergency thresholds
- Adding new enum values

#### PATCH Version (Fixes)
- Adjusting threshold values
- Fixing typos in descriptions
- Clarifying documentation
- Adjusting min/max ranges

## Implementation

### 1. Version Tracking

The specification file includes version metadata:

```yaml
# sensor_validation_spec.yaml
version: "1.2.3"
name: "Wind Turbine Sensor Validation"
last_modified: "2024-01-15T10:30:00Z"
author: "data-team@company.com"
changelog_url: "https://docs.company.com/specs/changelog"

# Version compatibility
compatible_with:
  min_version: "1.0.0"  # Minimum version this spec works with
  max_version: "2.0.0"  # Maximum version before breaking changes

# Deprecation notices
deprecations:
  - field: "old_field_name"
    deprecated_since: "1.1.0"
    removed_in: "2.0.0"
    alternative: "new_field_name"
```

### 2. File Structure

```
specs/
├── current/
│   └── sensor_validation_spec.yaml -> ../v1.2.3/sensor_validation_spec.yaml
├── v1.0.0/
│   ├── sensor_validation_spec.yaml
│   └── CHANGELOG.md
├── v1.1.0/
│   ├── sensor_validation_spec.yaml
│   └── CHANGELOG.md
├── v1.2.0/
│   ├── sensor_validation_spec.yaml
│   └── CHANGELOG.md
└── v1.2.3/
    ├── sensor_validation_spec.yaml
    └── CHANGELOG.md
```

### 3. Version Management

Use the `spec_version_manager.py` tool:

```bash
# Create a new version
./spec_version_manager.py create \
  --version 1.2.4 \
  --author "john@company.com" \
  --changelog "Adjusted temperature thresholds for summer operations"

# List all versions
./spec_version_manager.py list

# Compare versions
./spec_version_manager.py diff 1.2.3 1.2.4

# Check compatibility
./spec_version_manager.py check-compatibility 1.0.0
```

## Version Lifecycle

### 1. Development Phase

During development, use pre-release versions:

```yaml
version: "2.0.0-alpha.1"
version: "2.0.0-beta.1"
version: "2.0.0-rc.1"
```

### 2. Release Process

1. **Create Release Branch**
   ```bash
   git checkout -b release/v1.2.4
   ```

2. **Update Version**
   ```bash
   ./spec_version_manager.py create --version 1.2.4 --author "team@company.com" --changelog "..."
   ```

3. **Test Thoroughly**
   ```bash
   # Run validation tests
   ./test_spec_validation.py --spec specs/v1.2.4/sensor_validation_spec.yaml
   
   # Test backward compatibility
   ./test_spec_compatibility.py --old 1.2.3 --new 1.2.4
   ```

4. **Deploy**
   ```bash
   # Tag release
   git tag -a v1.2.4 -m "Release version 1.2.4"
   git push origin v1.2.4
   
   # Deploy to production
   ./deploy_spec.sh v1.2.4
   ```

### 3. Rollback Process

If issues are discovered:

```bash
# Quick rollback
cd specs/
rm current
ln -s v1.2.3 current

# Or use the rollback script
./rollback_spec.sh 1.2.3
```

## Data Compatibility

### 1. Version Stamping

All validated data includes the spec version:

```json
{
  "validation_metadata": {
    "spec_version": "1.2.3",
    "validated_at": "2024-01-15T10:30:00Z",
    "validator": "sensor_data_models_dynamic.py"
  },
  "data": {
    "sensor_id": "NYC_001",
    "temperature": 65.5
  }
}
```

### 2. Compatibility Matrix

Maintain a compatibility matrix:

| Data Version | Compatible Spec Versions | Notes |
|--------------|-------------------------|--------|
| 1.0.x | 1.0.0 - 1.2.x | Full compatibility |
| 1.1.x | 1.0.0 - 1.2.x | New optional fields ignored by old specs |
| 1.2.x | 1.2.0 - 1.2.x | Requires new validation rules |
| 2.0.x | 2.0.0+ | Breaking changes, not backward compatible |

### 3. Migration Strategy

For breaking changes:

```python
# migration_v1_to_v2.py
def migrate_data(old_data: dict) -> dict:
    """Migrate data from v1.x to v2.x format."""
    new_data = old_data.copy()
    
    # Rename fields
    if "old_field" in new_data:
        new_data["new_field"] = new_data.pop("old_field")
    
    # Transform values
    if "temperature_f" in new_data:
        new_data["temperature_c"] = (new_data.pop("temperature_f") - 32) * 5/9
    
    # Add required fields
    new_data["spec_version"] = "2.0.0"
    
    return new_data
```

## Testing Strategy

### 1. Unit Tests

Test each version independently:

```python
# test_spec_v1_2_3.py
def test_temperature_validation():
    spec = load_spec("specs/v1.2.3/sensor_validation_spec.yaml")
    assert spec["fields"]["temperature"]["min"] == 50.0
    assert spec["fields"]["temperature"]["max"] == 80.0
```

### 2. Compatibility Tests

Test version transitions:

```python
# test_compatibility.py
def test_v1_1_to_v1_2_compatibility():
    old_spec = load_spec("specs/v1.1.0/sensor_validation_spec.yaml")
    new_spec = load_spec("specs/v1.2.0/sensor_validation_spec.yaml")
    
    # Ensure all old fields still exist
    for field in old_spec["fields"]:
        assert field in new_spec["fields"]
```

### 3. Integration Tests

Test with real data:

```bash
# Test with production data sample
./validate_with_spec.py \
  --spec specs/v1.2.3/sensor_validation_spec.yaml \
  --data production_sample.json
```

## Monitoring and Alerts

### 1. Version Usage Tracking

Track which versions are in use:

```python
# In the pipeline
logger.log_metric("spec_version_used", spec_version, tags={"component": "validator"})
```

### 2. Deprecation Warnings

Log warnings for deprecated features:

```python
if "deprecated_field" in data:
    logger.warning(
        "Using deprecated field 'deprecated_field'",
        spec_version=current_version,
        deprecated_since="1.1.0",
        removal_version="2.0.0"
    )
```

### 3. Version Mismatch Alerts

Alert on version mismatches:

```python
if data_spec_version != current_spec_version:
    if not is_compatible(data_spec_version, current_spec_version):
        alert.send(
            "Incompatible spec version detected",
            data_version=data_spec_version,
            current_version=current_spec_version
        )
```

## Documentation

### 1. Changelog Format

Each version includes a detailed changelog:

```markdown
# Changelog for Version 1.2.4

**Date**: 2024-01-15
**Author**: data-team@company.com
**Type**: PATCH

## Summary
Adjusted temperature thresholds for summer operations based on analysis of false positive alerts.

## Changes

### Modified
- `fields.temperature.emergency_thresholds.high`: 75°C → 78°C
  - Reason: Reduced false positives during summer months
  - Impact: 30% reduction in non-critical alerts
  
- `fields.humidity.max`: 95% → 98%
  - Reason: Coastal sensors experience higher humidity
  - Impact: Better support for coastal deployments

### Added
- `fields.temperature.seasonal_adjustments`: New optional field
  - Allows dynamic threshold adjustments based on season
  - Backward compatible (optional field)

## Migration Notes
No migration required. This is a backward-compatible change.

## Testing
- Tested with 1M historical records
- Validated against all active sensor types
- Performance impact: negligible
```

### 2. API Documentation

Keep API docs in sync:

```yaml
# In validation_spec_api.py
@app.get("/spec/version")
def get_spec_version():
    """Get current specification version.
    
    Returns:
        Current version and compatibility information
    """
    return {
        "current_version": manager.get_current_version(),
        "compatible_range": {
            "min": "1.0.0",
            "max": "2.0.0"
        },
        "deprecations": [...],
        "changelog_url": "https://docs.company.com/spec/changelog"
    }
```

## Best Practices

### 1. Version Planning

- Plan major versions 6-12 months in advance
- Announce deprecations at least 2 minor versions before removal
- Maintain at least 3 minor versions for compatibility

### 2. Communication

- Email stakeholders for minor/major version changes
- Post to #data-pipeline Slack channel
- Update documentation site
- Create migration guides for major versions

### 3. Emergency Patches

For critical fixes:

```bash
# Create hotfix branch
git checkout -b hotfix/v1.2.4 v1.2.3

# Make minimal changes
vim specs/current/sensor_validation_spec.yaml

# Fast-track deployment
./emergency_deploy_spec.sh 1.2.4 --skip-full-tests
```

### 4. Long-Term Support

Maintain LTS versions:

- Version 1.0.x - LTS until 2025-01-01
- Version 2.0.x - LTS until 2026-01-01

## Governance

### 1. Approval Process

- **PATCH**: Data team lead approval
- **MINOR**: Data team + Engineering review
- **MAJOR**: Architecture review board

### 2. Change Request Template

```markdown
## Spec Change Request

**Version**: 1.3.0
**Type**: MINOR
**Requester**: john@company.com
**Date**: 2024-01-15

### Motivation
Explain why this change is needed

### Changes
List all changes with justification

### Impact Analysis
- Backward compatibility: ✓ Yes / ✗ No
- Performance impact: None / Minor / Major
- Migration required: ✓ Yes / ✗ No

### Testing Plan
Describe testing approach

### Rollout Plan
Describe deployment strategy
```

### 3. Review Checklist

- [ ] Version number follows SemVer
- [ ] Changelog is complete and clear
- [ ] Backward compatibility verified
- [ ] Tests updated/added
- [ ] Documentation updated
- [ ] Migration guide created (if needed)
- [ ] Stakeholders notified
- [ ] Performance impact assessed

## Automation

### 1. CI/CD Integration

```yaml
# .github/workflows/spec-validation.yml
name: Spec Validation
on:
  pull_request:
    paths:
      - 'specs/**/*.yaml'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Validate Spec
        run: |
          ./validate_spec_schema.py specs/current/sensor_validation_spec.yaml
          
      - name: Check Version
        run: |
          ./check_version_increment.py
          
      - name: Test Compatibility
        run: |
          ./test_spec_compatibility.py
          
      - name: Run Migration Tests
        run: |
          ./test_migrations.py
```

### 2. Automated Notifications

```python
# notify_spec_changes.py
def notify_version_change(old_version: str, new_version: str, changes: dict):
    """Send notifications for spec version changes."""
    
    # Determine notification level
    old_v = semantic_version.Version(old_version)
    new_v = semantic_version.Version(new_version)
    
    if new_v.major > old_v.major:
        # Major version - notify everyone
        notify_slack("#general", f"⚠️ Major spec update: v{new_version}")
        send_email("all-users@company.com", subject="Major Validation Spec Update")
    elif new_v.minor > old_v.minor:
        # Minor version - notify data teams
        notify_slack("#data-pipeline", f"📘 New spec version: v{new_version}")
        send_email("data-teams@company.com", subject="Validation Spec Update")
    else:
        # Patch - just log it
        logger.info(f"Spec patch released: v{new_version}")
```

## Conclusion

This versioning strategy ensures:

1. **Predictability**: Clear rules for version increments
2. **Compatibility**: Well-defined compatibility ranges
3. **Traceability**: Complete audit trail of changes
4. **Safety**: Ability to rollback when needed
5. **Communication**: Clear communication of changes

By following this strategy, we maintain a robust and reliable validation specification system that can evolve with changing requirements while maintaining stability for existing systems.