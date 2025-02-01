import org.deidentifier.arx.*;
import org.deidentifier.arx.aggregates.HierarchyBuilderIntervalBased;
import org.deidentifier.arx.aggregates.HierarchyBuilderRedactionBased;
import org.deidentifier.arx.aggregates.HierarchyBuilderRedactionBased.Order;
import org.deidentifier.arx.criteria.KAnonymity;

import java.io.BufferedWriter;
import java.io.FileWriter;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Iterator;

public class ARXTest2 {

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
        ageBuilder.addInterval(30L, 50L);
        ageBuilder.addInterval(50L, 70L);
        ageBuilder.addInterval(70L, 100L);

        // Create hierarchy builder for zipcode using redaction
        HierarchyBuilderRedactionBased<?> zipcodeBuilder = HierarchyBuilderRedactionBased.create(
            Order.RIGHT_TO_LEFT,
            Order.RIGHT_TO_LEFT,
            ' ',
            '*'
        );

        // Define attribute types
        data.getDefinition().setAttributeType("first_name", AttributeType.IDENTIFYING_ATTRIBUTE);
        data.getDefinition().setAttributeType("last_name", AttributeType.IDENTIFYING_ATTRIBUTE);
        data.getDefinition().setAttributeType("ssn", AttributeType.IDENTIFYING_ATTRIBUTE);
        data.getDefinition().setAttributeType("credit_card_number", AttributeType.IDENTIFYING_ATTRIBUTE);
        data.getDefinition().setAttributeType("city", AttributeType.IDENTIFYING_ATTRIBUTE);
        data.getDefinition().setAttributeType("country", AttributeType.INSENSITIVE_ATTRIBUTE);
        data.getDefinition().setAttributeType("age", ageBuilder);
        data.getDefinition().setAttributeType("zip_code", zipcodeBuilder);

        System.out.println("Starting anonymization...");
        
        // Create anonymizer
        ARXAnonymizer anonymizer = new ARXAnonymizer();
        ARXConfiguration config = ARXConfiguration.create();
        config.addPrivacyModel(new KAnonymity(3));
        config.setSuppressionLimit(0.2d);
        
        // Anonymize
        ARXResult result = anonymizer.anonymize(data, config);

        System.out.println("Anonymization complete. Writing results...");

        // Write anonymized data to CSV efficiently
        String outputFile = "data-generator/anonymized_output.csv";
        writeAnonymizedData(result.getOutput(), outputFile);

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
        System.out.println(" - Output file: " + outputFile);
    }

    private static void writeAnonymizedData(DataHandle handle, String outputFile) throws Exception {
        try (BufferedWriter writer = new BufferedWriter(new FileWriter(outputFile))) {
            // Write header
            int numColumns = handle.getNumColumns();
            for (int j = 0; j < numColumns; j++) {
                writer.write(handle.getAttributeName(j));
                writer.write(j < numColumns - 1 ? "," : "\n");
            }

            // Write data using efficient buffering
            Iterator<String[]> iterator = handle.iterator();
            while (iterator.hasNext()) {
                String[] row = iterator.next();
                for (int j = 0; j < row.length; j++) {
                    writer.write(row[j] == null ? "" : row[j]);
                    writer.write(j < row.length - 1 ? "," : "\n");
                }
            }
        }
        
        System.out.println("Data written successfully to: " + outputFile);
    }
}
