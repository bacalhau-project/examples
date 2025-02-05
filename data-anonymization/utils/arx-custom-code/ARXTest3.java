import org.deidentifier.arx.*;
import org.deidentifier.arx.criteria.KAnonymity;
import org.deidentifier.arx.metric.Metric;
import java.io.BufferedWriter;
import java.io.FileWriter;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Iterator;
import java.io.File;
import java.io.FilenameFilter;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class ARXTest3 {

    public static void main(String[] args) throws Exception {
        
        // Read the CSV file
        Data data = Data.create("some.csv", StandardCharsets.UTF_8, ',');

        // Define attribute types
        data.getDefinition().setAttributeType("first_name", AttributeType.IDENTIFYING_ATTRIBUTE);
        data.getDefinition().setAttributeType("last_name", AttributeType.IDENTIFYING_ATTRIBUTE);
        data.getDefinition().setAttributeType("ssn", AttributeType.IDENTIFYING_ATTRIBUTE);
        data.getDefinition().setAttributeType("credit_card_number", AttributeType.IDENTIFYING_ATTRIBUTE);
        data.getDefinition().setAttributeType("city", AttributeType.IDENTIFYING_ATTRIBUTE);
        data.getDefinition().setAttributeType("country", AttributeType.INSENSITIVE_ATTRIBUTE);
        
        // Create generalization hierarchies
        AttributeType.Hierarchy.DefaultHierarchy age = AttributeType.Hierarchy.create();
        // Define age hierarchy
        for (int i = 0; i < 100; i++) {
            String[] level = new String[3];
            level[0] = String.valueOf(i);
            level[1] = String.valueOf(i / 10 * 10) + "-" + String.valueOf(i / 10 * 10 + 9);
            level[2] = "*";
            age.add(level);
        }
        
        AttributeType.Hierarchy.DefaultHierarchy zipcode = AttributeType.Hierarchy.create();
        // Define zipcode hierarchy
        String[] zips = data.getHandle().getDistinctValues(data.getHandle().getColumnIndexOf("zip_code"));
        for (String zip : zips) {
            String[] level = new String[4];
            level[0] = zip;
            level[1] = zip.substring(0, 3) + "**";
            level[2] = zip.substring(0, 2) + "***";
            level[3] = "*****";
            zipcode.add(level);
        }

        // Set hierarchies
        data.getDefinition().setAttributeType("age", age);
        data.getDefinition().setAttributeType("zip_code", zipcode);

        System.out.println("Starting anonymization...");

        // Create anonymizer
        ARXAnonymizer anonymizer = new ARXAnonymizer();
        ARXConfiguration config = ARXConfiguration.create();
        config.addPrivacyModel(new KAnonymity(3));
        config.setSuppressionLimit(0.04d);
        config.setQualityModel(Metric.createEntropyMetric());

        // Anonymize
        ARXResult result = anonymizer.anonymize(data, config);

        System.out.println("Anonymization complete. Writing results...");

        // Write anonymized data to CSV
        String outputFile = "data-generator/anonymized_output_test3.csv";
        writeAnonymizedData(result.getOutput(), outputFile);

        // Print statistics
        System.out.println("\nTransformation Statistics:");
        System.out.println(" - Transformation level: " + Arrays.toString(result.getGlobalOptimum().getTransformation()));
        System.out.println(" - Quasi-identifiers: " + data.getDefinition().getQuasiIdentifyingAttributes());
        
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