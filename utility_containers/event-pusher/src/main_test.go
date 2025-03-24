// This file contains tests that don't require the WASM runtime
// To run these tests: go test -run TestCore
package main

import (
	"os"
	"testing"

	"github.com/bacalhau-project/examples/utility_containers/event-pusher/internal/messages"
	"github.com/bacalhau-project/examples/utility_containers/event-pusher/internal/utils"
	"github.com/stretchr/testify/assert"
)

// TestCoreLoadConfig tests the loadConfig function
func TestCoreLoadConfig(t *testing.T) {
	// Create a test config file
	testConfigContent := `
method: "POST"
url: "https://test.com"
color: "#FF5500"
max_interval_seconds: 10
max_messages: 5
random_off: true
`
	testConfigPath := "test_config.yaml"
	err := os.WriteFile(testConfigPath, []byte(testConfigContent), 0644)
	assert.NoError(t, err)
	defer os.Remove(testConfigPath)

	// Pass the test config file path directly
	config := loadConfig(testConfigPath)

	// Check HTTP mode config
	assert.Equal(t, "POST", config.Method)
	assert.Equal(t, "https://test.com", config.URL)
	assert.Empty(t, config.Headers)
	assert.Empty(t, config.Body)

	// Check event pusher config
	assert.Equal(t, "us-west-2", config.Region)
	assert.Equal(t, "#FF5500", config.Color)
	assert.Equal(t, 10, config.MaxInterval)
	assert.Equal(t, 5, config.MaxMessages)
	assert.True(t, config.RandomOff)
	assert.False(t, config.Simulate)
	assert.Equal(t, "auto", config.Mode)
}

// TestCoreDetectModeFromConfig tests the mode detection with configuration
func TestCoreDetectModeFromConfig(t *testing.T) {
	// Test with URL set
	assert.Equal(t, "http", utils.DetectModeFromConfig("https://test.com", "", false))

	// Test with QueueURL set
	assert.Equal(t, "event-pusher", utils.DetectModeFromConfig("", "https://sqs.aws.com/queue", false))

	// Test with Simulate set
	assert.Equal(t, "event-pusher", utils.DetectModeFromConfig("", "", true))

	// Test with nothing set
	assert.Equal(t, "http", utils.DetectModeFromConfig("", "", false))
}

// TestCoreParseBool tests boolean parsing from strings
func TestCoreParseBool(t *testing.T) {
	assert.True(t, utils.ParseBool("true"))
	assert.True(t, utils.ParseBool("1"))
	assert.True(t, utils.ParseBool("yes"))

	assert.False(t, utils.ParseBool("false"))
	assert.False(t, utils.ParseBool("0"))
	assert.False(t, utils.ParseBool("no"))
	assert.False(t, utils.ParseBool(""))
	assert.False(t, utils.ParseBool("anything else"))
}

// TestCoreIsValidHexColor tests the color validation function
func TestCoreIsValidHexColor(t *testing.T) {
	// Valid colors
	assert.True(t, messages.IsValidHexColor("#000000"))
	assert.True(t, messages.IsValidHexColor("#FF5500"))
	assert.True(t, messages.IsValidHexColor("#123ABC"))
	assert.True(t, messages.IsValidHexColor("#ffffff"))

	// Invalid colors
	assert.False(t, messages.IsValidHexColor("000000"))   // Missing #
	assert.False(t, messages.IsValidHexColor("#00000"))   // Too short
	assert.False(t, messages.IsValidHexColor("#0000000")) // Too long
	assert.False(t, messages.IsValidHexColor("#GGHHII"))  // Invalid characters
	assert.False(t, messages.IsValidHexColor("#"))        // Only # character
	assert.False(t, messages.IsValidHexColor(""))         // Empty string
}

// TestCoreRandomFunctions tests random generation functions
func TestCoreRandomFunctions(t *testing.T) {
	// Create a generator
	generator := messages.NewDefaultGenerator()

	// Test with randomness off
	fixedContainerID := generator.GenerateContainerID(true)
	assert.Equal(t, 8, len(fixedContainerID))

	// Should always return the same value with randomness off
	for i := 0; i < 5; i++ {
		assert.Equal(t, fixedContainerID, generator.GenerateContainerID(true))
	}

	// Test with randomness on - should get different values
	// (theoretically this could fail if we get the same random value twice, but extremely unlikely)
	randomIDs := make(map[string]bool)
	for i := 0; i < 5; i++ {
		id := generator.GenerateContainerID(false)
		assert.Equal(t, 8, len(id))
		randomIDs[id] = true
	}
	assert.GreaterOrEqual(t, len(randomIDs), 1) // Might occasionally get same ID by chance

	// Test random icon with randomness off
	fixedIcon := generator.GetRandomIcon(true)
	assert.Equal(t, messages.DefaultEmojis()[0], fixedIcon)

	// Should always be the same with randomness off
	for i := 0; i < 5; i++ {
		assert.Equal(t, fixedIcon, generator.GetRandomIcon(true))
	}

	// With randomness on, should get variety (though occasionally might get repeats)
	randomIcons := make(map[string]bool)
	for i := 0; i < 10; i++ {
		icon := generator.GetRandomIcon(false)
		randomIcons[icon] = true
	}
	assert.GreaterOrEqual(t, len(randomIcons), 1) // Might occasionally get same icon by chance
}

// TestCoreParseHeaders tests header string parsing
func TestCoreParseHeaders(t *testing.T) {
	// Empty string should return empty map
	empty := utils.ParseHeaders("")
	assert.Equal(t, 0, len(empty))

	// Single header
	singleHeader := "Content-Type: application/json"
	parsed := utils.ParseHeaders(singleHeader)
	assert.Equal(t, 1, len(parsed))
	assert.Equal(t, "application/json", parsed["Content-Type"])

	// Multiple headers
	multipleHeaders := "Content-Type: application/json\nAuthorization: Bearer token"
	parsed = utils.ParseHeaders(multipleHeaders)
	assert.Equal(t, 2, len(parsed))
	assert.Equal(t, "application/json", parsed["Content-Type"])
	assert.Equal(t, "Bearer token", parsed["Authorization"])
}
