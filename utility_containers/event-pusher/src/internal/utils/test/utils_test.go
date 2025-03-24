package test

import (
	"os"
	"testing"

	"github.com/bacalhau-project/examples/utility_containers/event-pusher/internal/utils"
	"github.com/stretchr/testify/assert"
)

func TestParseBool(t *testing.T) {
	tests := []struct {
		input    string
		expected bool
	}{
		{"true", true},
		{"1", true},
		{"yes", true},
		{"false", false},
		{"0", false},
		{"no", false},
		{"", false},
		{"anything", false},
	}

	for _, test := range tests {
		t.Run(test.input, func(t *testing.T) {
			result := utils.ParseBool(test.input)
			assert.Equal(t, test.expected, result)
		})
	}
}

func TestGetEnvWithDefault(t *testing.T) {
	// Save original environment and restore after test
	origEnv := os.Environ()
	defer func() {
		os.Clearenv()
		for _, e := range origEnv {
			pair := os.Getenv(e)
			os.Setenv(e, pair)
		}
	}()

	// Test with no environment variable set
	result := utils.GetEnvWithDefault("TEST_ENV_VAR", "default-value")
	assert.Equal(t, "default-value", result)

	// Test with environment variable set
	os.Setenv("TEST_ENV_VAR", "set-value")
	result = utils.GetEnvWithDefault("TEST_ENV_VAR", "default-value")
	assert.Equal(t, "set-value", result)

	// Test with empty environment variable
	os.Setenv("TEST_ENV_VAR", "")
	result = utils.GetEnvWithDefault("TEST_ENV_VAR", "default-value")
	assert.Equal(t, "default-value", result)
}

func TestDetectModeFromConfig(t *testing.T) {
	// Test with no configuration
	result := utils.DetectModeFromConfig("", "", false)
	assert.Equal(t, "http", result)

	// Test with URL set
	result = utils.DetectModeFromConfig("https://example.com", "", false)
	assert.Equal(t, "http", result)

	// Test with QueueURL set
	result = utils.DetectModeFromConfig("", "https://sqs.example.com/queue", false)
	assert.Equal(t, "event-pusher", result)

	// Test with Simulate set
	result = utils.DetectModeFromConfig("", "", true)
	assert.Equal(t, "event-pusher", result)

	// Test with both URL and QueueURL set
	result = utils.DetectModeFromConfig("https://example.com", "https://sqs.example.com/queue", false)
	assert.Equal(t, "http", result) // HTTP takes precedence
}

func TestParseHeaders(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		expected map[string]string
	}{
		{
			name:     "Empty string",
			input:    "",
			expected: map[string]string{},
		},
		{
			name:  "Single header",
			input: "Content-Type: application/json",
			expected: map[string]string{
				"Content-Type": "application/json",
			},
		},
		{
			name:  "Multiple headers",
			input: "Content-Type: application/json\nAuthorization: Bearer token123\nAccept: */*",
			expected: map[string]string{
				"Content-Type":  "application/json",
				"Authorization": "Bearer token123",
				"Accept":        "*/*",
			},
		},
		{
			name:  "Whitespace handling",
			input: "  Content-Type:  application/json  \n  Authorization:Bearer token123",
			expected: map[string]string{
				"Content-Type":  "application/json",
				"Authorization": "Bearer token123",
			},
		},
		{
			name:  "Invalid format",
			input: "InvalidLine\nContent-Type: application/json",
			expected: map[string]string{
				"Content-Type": "application/json",
			},
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			result := utils.ParseHeaders(test.input)
			assert.Equal(t, test.expected, result)
		})
	}
}