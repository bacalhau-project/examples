import org.deidentifier.arx.ARXAnonymizer;
import org.deidentifier.arx.ARXConfiguration;
import org.deidentifier.arx.ARXResult;
import org.deidentifier.arx.AttributeType;
import org.deidentifier.arx.Data;
import java.nio.charset.StandardCharsets;
import org.deidentifier.arx.criteria.KAnonymity;
import org.deidentifier.arx.criteria.DistinctLDiversity;
import org.deidentifier.arx.aggregates.HierarchyBuilderIntervalBased;
import org.deidentifier.arx.aggregates.HierarchyBuilderRedactionBased;
import org.deidentifier.arx.aggregates.HierarchyBuilderRedactionBased.Order;
import org.deidentifier.arx.DataType;
import java.util.Arrays;

public class ARXTest1 {

    public static void main(String[] args) throws Exception {
        
        // Read the CSV file
        Data data = Data.create("some.csv", StandardCharsets.UTF_8, ',');

        // Create hierarchy builder for age
        HierarchyBuilderIntervalBased<Long> ageBuilder = HierarchyBuilderIntervalBased.create(
            DataType.INTEGER,
            new HierarchyBuilderIntervalBased.Range<Long>(0L, 0L, 0L),
            new HierarchyBuilderIntervalBased.Range<Long>(100L, 100L, 100L));

        // Define intervals for age
        ageBuilder.setAggregateFunction(DataType.INTEGER.createAggregate().createIntervalFunction(true, false));
        ageBuilder.addInterval(0L, 30L);
        ageBuilder.addInterval(30L, 40L);
        ageBuilder.addInterval(40L, 100L);

        // Create hierarchy builder for zipcode using redaction
        HierarchyBuilderRedactionBased<?> zipcodeBuilder = HierarchyBuilderRedactionBased.create(
            Order.RIGHT_TO_LEFT,  // Replace from right to left
            Order.RIGHT_TO_LEFT,  // Redact from right to left
            ' ',                  // Padding character
            '*'                   // Redaction character
        );

        // Define attribute types and hierarchies
        data.getDefinition().setAttributeType("age", ageBuilder);
        data.getDefinition().setAttributeType("zipcode", zipcodeBuilder);
        data.getDefinition().setAttributeType("disease", AttributeType.SENSITIVE_ATTRIBUTE);

        // Create anonymizer
        ARXAnonymizer anonymizer = new ARXAnonymizer();
        
        // Configure privacy models
        ARXConfiguration config = ARXConfiguration.create();
        config.addPrivacyModel(new KAnonymity(4));
        config.addPrivacyModel(new DistinctLDiversity("disease", 4));
        config.setSuppressionLimit(0.2d);
        
        // Anonymize
        ARXResult result = anonymizer.anonymize(data, config);

        // Print original data
        System.out.println("\nOriginal data:");
        printData(data.getHandle());

        // Print anonymized data
        System.out.println("\nAnonymized data:");
        printData(result.getOutput());

        // Print statistics
        System.out.println("\nTransformation Statistics:");
        System.out.println(" - Transformation level: " + Arrays.toString(result.getGlobalOptimum().getTransformation()));
        System.out.println(" - Quasi-identifiers: " + data.getDefinition().getQuasiIdentifyingAttributes());
        
        // Get the anonymization metrics
        double numRecords = result.getOutput().getNumRows();
        double numSuppressed = result.getOutput().getStatistics().getEquivalenceClassStatistics().getNumberOfSuppressedRecords();
        double suppressionRate = numSuppressed / numRecords;
        
        System.out.printf(" - Suppression rate: %.2f%%\n", suppressionRate * 100);
        System.out.printf(" - Average class size: %.2f\n", result.getOutput().getStatistics().getEquivalenceClassStatistics().getAverageEquivalenceClassSize());
        System.out.println(" - Number of classes: " + result.getOutput().getStatistics().getEquivalenceClassStatistics().getNumberOfEquivalenceClasses());
    }

    private static void printData(org.deidentifier.arx.DataHandle handle) {
        // Print header
        for (int j = 0; j < handle.getNumColumns(); j++) {
            System.out.print(handle.getAttributeName(j) + "\t");
        }
        System.out.println();

        // Print data
        for (int i = 0; i < handle.getNumRows(); i++) {
            for (int j = 0; j < handle.getNumColumns(); j++) {
                System.out.print(handle.getValue(i, j) + "\t");
            }
            System.out.println();
        }
    }
}
