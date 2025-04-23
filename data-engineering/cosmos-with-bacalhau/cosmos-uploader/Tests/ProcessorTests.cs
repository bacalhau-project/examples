using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using CosmosUploader.Processors;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using System.Threading;

namespace CosmosUploader.Tests;

[TestClass]
public class ProcessorTests
{
    // Define placeholder data type consistent with processors
    using DataItem = System.Collections.Generic.Dictionary<string, object>; 

    private readonly NullLogger<SchemaProcessor> _nullSchemaLogger = new NullLogger<SchemaProcessor>();
    private readonly NullLogger<SanitizeProcessor> _nullSanitizeLogger = new NullLogger<SanitizeProcessor>();
    private readonly NullLogger<AggregateProcessor> _nullAggregateLogger = new NullLogger<AggregateProcessor>();

    private List<DataItem> CreateTestData(int count = 1, bool includeValid = true, bool includeInvalid = false, bool includeNullTemp = false) {
        var data = new List<DataItem>();
        for(int i = 0; i < count; i++) {
            if (includeValid) {
                 data.Add(new DataItem {
                    { "id", $"valid_id_{i}" },
                    { "sensor_id", $"sensor_abc_{i}" },
                    { "timestamp", DateTime.UtcNow.AddMinutes(-i) },
                    { "temperature", 25.5 + i },
                    { "extra_field", "value" }
                });
            }
             if (includeInvalid) {
                 data.Add(new DataItem {
                    { "id", $"invalid_id_{i}" },
                    // Missing sensor_id, timestamp, temperature
                });
            }
            if (includeNullTemp) {
                 data.Add(new DataItem {
                    { "id", $"nulltemp_id_{i}" },
                    { "sensor_id", $"sensor_def_{i}" },
                    { "timestamp", DateTime.UtcNow.AddHours(-i) },
                    { "temperature", null }
                });
            }
        }
        return data;
    }

    [TestMethod]
    public async Task SchemaProcessor_ValidData_Passes()
    {
        // Arrange
        var processor = new SchemaProcessor(_nullSchemaLogger);
        var testData = CreateTestData(count: 2, includeValid: true);
        var cancellationToken = CancellationToken.None;

        // Act
        var result = await processor.ProcessAsync(testData, cancellationToken);

        // Assert
        Assert.AreEqual(2, result.Count(), "Should process all valid items.");
        Assert.IsTrue(result.All(item => item["processed_stage"].ToString() == ProcessingStage.Schematized.ToString()));
        Assert.IsTrue(result.All(item => item["temperature"] is double));
    }

     [TestMethod]
    public async Task SchemaProcessor_InvalidData_IsSkipped()
    {
        // Arrange
        var processor = new SchemaProcessor(_nullSchemaLogger);
        var testData = CreateTestData(count: 1, includeValid: true, includeInvalid: true);
        var cancellationToken = CancellationToken.None;

        // Act
        var result = await processor.ProcessAsync(testData, cancellationToken);

        // Assert
        Assert.AreEqual(1, result.Count(), "Should skip invalid item.");
        Assert.AreEqual("valid_id_0", result.First()["id"].ToString());
    }

    [TestMethod]
    public async Task SanitizeProcessor_MasksKey()
    {
        // Arrange
        var processor = new SanitizeProcessor(_nullSanitizeLogger);
        var testData = CreateTestData(count: 1, includeValid: true);
        var cancellationToken = CancellationToken.None;

        // Act
        var result = await processor.ProcessAsync(testData, cancellationToken);

        // Assert
        Assert.AreEqual(1, result.Count());
        Assert.AreEqual("sen***", result.First()["sensor_id"].ToString(), "Sensor ID should be masked.");
        Assert.AreEqual(ProcessingStage.Sanitized.ToString(), result.First()["processed_stage"].ToString());
    }

    [TestMethod]
    public async Task AggregateProcessor_AveragesTemperature()
    { 
        // Arrange
        var processor = new AggregateProcessor(_nullAggregateLogger);
        var testData = new List<DataItem> {
            new DataItem { { "id", "id1" }, { "sensor_id", "sensor_xyz" }, { "timestamp", DateTime.UtcNow.AddMinutes(-5) }, { "temperature", 20.0 } },
            new DataItem { { "id", "id2" }, { "sensor_id", "sensor_xyz" }, { "timestamp", DateTime.UtcNow.AddMinutes(-2) }, { "temperature", 30.0 } },
            new DataItem { { "id", "id3" }, { "sensor_id", "sensor_xyz" }, { "timestamp", DateTime.UtcNow.AddMinutes(-1) }, { "temperature", null } }, // Null temp
            new DataItem { { "id", "id4" }, { "sensor_id", "sensor_abc" }, { "timestamp", DateTime.UtcNow.AddMinutes(-3) }, { "temperature", 10.0 } }
        };
        var cancellationToken = CancellationToken.None;

        // Act
        var result = await processor.ProcessAsync(testData, cancellationToken);
        var resultList = result.ToList();

        // Assert
        Assert.AreEqual(2, resultList.Count, "Should produce one item per sensor_id group.");

        var groupXyz = resultList.FirstOrDefault(item => item["sensor_id"].ToString() == "sensor_xyz");
        Assert.IsNotNull(groupXyz);
        Assert.AreEqual(ProcessingStage.Aggregated.ToString(), groupXyz["processed_stage"].ToString());
        Assert.AreEqual(3, (int)groupXyz["item_count"]); // 3 items in original group
        Assert.AreEqual(25.0, (double?)groupXyz["average_temperature"], 0.001, "Average temp should be (20+30)/2."); 

         var groupAbc = resultList.FirstOrDefault(item => item["sensor_id"].ToString() == "sensor_abc");
        Assert.IsNotNull(groupAbc);
        Assert.AreEqual(1, (int)groupAbc["item_count"]);
        Assert.AreEqual(10.0, (double?)groupAbc["average_temperature"], 0.001);
    }
} 