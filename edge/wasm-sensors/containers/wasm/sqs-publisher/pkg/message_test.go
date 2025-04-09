package pkg

import (
	"os"
	"testing"
	"time"
)

func TestNewMessageGenerator(t *testing.T) {
	// Set environment variables for testing
	originalJobID := os.Getenv("BACALHAU_JOB_ID")
	originalExecID := os.Getenv("BACALHAU_EXECUTION_ID")
	originalHostname := os.Getenv("HOSTNAME")

	defer func() {
		// Restore original environment variables
		os.Setenv("BACALHAU_JOB_ID", originalJobID)
		os.Setenv("BACALHAU_EXECUTION_ID", originalExecID)
		os.Setenv("HOSTNAME", originalHostname)
	}()

	// Set test values
	testJobID := "test-job-123"
	testExecID := "test-exec-456"
	testHostname := "test-host"

	os.Setenv("BACALHAU_JOB_ID", testJobID)
	os.Setenv("BACALHAU_EXECUTION_ID", testExecID)
	os.Setenv("HOSTNAME", testHostname)

	// Create new generator
	generator := NewMessageGenerator()

	// Verify fields are set correctly
	if generator.jobID != testJobID {
		t.Errorf("Expected jobID to be %s, got %s", testJobID, generator.jobID)
	}

	if generator.executionID != testExecID {
		t.Errorf("Expected executionID to be %s, got %s", testExecID, generator.executionID)
	}

	if generator.hostname != testHostname {
		t.Errorf("Expected hostname to be %s, got %s", testHostname, generator.hostname)
	}

	if generator.counter != 0 {
		t.Errorf("Expected counter to start at 0, got %d", generator.counter)
	}
}

func TestGetMessage(t *testing.T) {
	// Set environment variables for testing
	originalJobID := os.Getenv("BACALHAU_JOB_ID")
	originalExecID := os.Getenv("BACALHAU_EXECUTION_ID")
	originalHostname := os.Getenv("HOSTNAME")

	defer func() {
		// Restore original environment variables
		os.Setenv("BACALHAU_JOB_ID", originalJobID)
		os.Setenv("BACALHAU_EXECUTION_ID", originalExecID)
		os.Setenv("HOSTNAME", originalHostname)
	}()

	// Set test values
	testJobID := "test-job-123"
	testExecID := "test-exec-456"
	testHostname := "test-host"

	os.Setenv("BACALHAU_JOB_ID", testJobID)
	os.Setenv("BACALHAU_EXECUTION_ID", testExecID)
	os.Setenv("HOSTNAME", testHostname)

	// Create config
	config := RuntimeConfig{
		Color:          "#ff0000",
		EmojiIdx:       5, // Corresponds to "🛠️"
		Region:         "us-west-1",
		SubmissionTime: time.Unix(1617234567, 0),
	}

	// Create generator and get message
	generator := NewMessageGenerator()

	// Verify sequence increments correctly over multiple calls
	for i := 1; i <= 3; i++ {
		message := generator.GetMessage(config)

		// Verify message fields
		if message.JobID != testJobID {
			t.Errorf("Expected JobID to be %s, got %s", testJobID, message.JobID)
		}

		if message.ExecutionID != testExecID {
			t.Errorf("Expected ExecutionID to be %s, got %s", testExecID, message.ExecutionID)
		}

		if message.IconName != supportedEmojis[5] {
			t.Errorf("Expected IconName to be %s, got %s", supportedEmojis[5], message.IconName)
		}

		if message.Color != "#ff0000" {
			t.Errorf("Expected Color to be #ff0000, got %s", message.Color)
		}

		if message.Sequence != i {
			t.Errorf("Expected Sequence to be %d, got %d", i, message.Sequence)
		}

		if message.Region != "us-west-1" {
			t.Errorf("Expected Region to be us-west-1, got %s", message.Region)
		}

		if message.JobSubmissionTime != 1617234567 {
			t.Errorf("Expected JobSubmissionTime to be 1617234567, got %d", message.JobSubmissionTime)
		}

		if message.Hostname != testHostname {
			t.Errorf("Expected Hostname to be %s, got %s", testHostname, message.Hostname)
		}

		// Check timestamp format (RFC3339)
		_, err := time.Parse(time.RFC3339, message.Timestamp)
		if err != nil {
			t.Errorf("Invalid timestamp format: %s", message.Timestamp)
		}
	}

	// Verify counter was incremented
	if generator.counter != 3 {
		t.Errorf("Expected counter to be 3 after 3 calls, got %d", generator.counter)
	}
}

func TestRandomEmojiDistribution(t *testing.T) {
	// Skip this test in short mode as it's more time-consuming
	if testing.Short() {
		t.Skip("Skipping emoji distribution test in short mode")
	}

	// Set up generator
	generator := NewMessageGenerator()

	// Create a map to track emoji occurrences
	emojiCounts := make(map[string]int)

	// Run a large number of iterations
	iterations := 1000

	for i := 0; i < iterations; i++ {
		// Create a config with random emoji index
		config := RuntimeConfig{
			Color:  "#ff0000",
			Region: "us-west-1",
		}

		// Set EmojiIdx to -1 to trigger random selection in Normalize
		config.EmojiIdx = -1
		config.Normalize()

		// Get message with normalized config
		message := generator.GetMessage(config)

		// Count emoji occurrences
		emojiCounts[message.IconName]++
	}

	// Verify all emojis were used
	if len(emojiCounts) < len(supportedEmojis) {
		t.Logf("Warning: Not all emojis were selected in %d iterations", iterations)
		t.Logf("Expected %d different emojis, got %d", len(supportedEmojis), len(emojiCounts))
	}

	// Check distribution is somewhat even (no emoji used more than 10% of expected average)
	expectedAvg := float64(iterations) / float64(len(supportedEmojis))
	maxDeviation := expectedAvg * 0.5 // Allow 50% deviation for statistical reasons

	for emoji, count := range emojiCounts {
		deviation := float64(count) - expectedAvg
		if deviation > maxDeviation || deviation < -maxDeviation {
			t.Logf("Warning: Emoji %s has count %d, which deviates by %.2f from expected average %.2f",
				emoji, count, deviation, expectedAvg)
		}
	}

	// Log emoji distribution
	t.Logf("Emoji distribution across %d runs:", iterations)
	for i, emoji := range supportedEmojis {
		count := emojiCounts[emoji]
		percentage := float64(count) / float64(iterations) * 100
		t.Logf("%s (index %d): %d occurrences (%.2f%%)", emoji, i, count, percentage)
	}
}

func TestMultipleGeneratorsIndependence(t *testing.T) {
	// Create multiple generators
	g1 := NewMessageGenerator()
	g2 := NewMessageGenerator()

	// Create config
	config := RuntimeConfig{
		Color:  "#ff0000",
		Region: "us-west-1",
	}

	// Generate messages with both generators
	msg1a := g1.GetMessage(config)
	msg1b := g1.GetMessage(config)
	msg2a := g2.GetMessage(config)
	msg2b := g2.GetMessage(config)

	// Check sequence counters are independent
	if msg1a.Sequence != 1 || msg1b.Sequence != 2 {
		t.Errorf("First generator sequences should be 1,2, got %d,%d", msg1a.Sequence, msg1b.Sequence)
	}

	if msg2a.Sequence != 1 || msg2b.Sequence != 2 {
		t.Errorf("Second generator sequences should be 1,2, got %d,%d", msg2a.Sequence, msg2b.Sequence)
	}
}
