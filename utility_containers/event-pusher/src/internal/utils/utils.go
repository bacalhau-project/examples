package utils

import (
	"os"
	"strings"
)

// GetEnvWithDefault gets an environment variable or returns the default value
func GetEnvWithDefault(key, defaultValue string) string {
	value := os.Getenv(key)
	if value == "" {
		return defaultValue
	}
	return value
}

// ParseBool parses a string to a boolean value
func ParseBool(value string) bool {
	return value == "true" || value == "1" || value == "yes"
}

// DetectModeFromConfig detects which mode to run based on configuration
func DetectModeFromConfig(url, queueURL string, simulate bool) string {
	// If URL is set, we're in HTTP mode
	if url != "" {
		return "http"
	}
	
	// If QueueURL is set, we're in event pusher mode
	if queueURL != "" || simulate {
		return "event-pusher"
	}
	
	// Default to HTTP mode
	return "http"
}

// ParseHeaders converts a header string to Headers map
func ParseHeaders(headerStr string) map[string]string {
	headers := make(map[string]string)
	if headerStr == "" {
		return headers
	}

	// Split headers by newline
	lines := strings.Split(headerStr, "\n")
	for _, line := range lines {
		parts := strings.SplitN(line, ":", 2)
		if len(parts) == 2 {
			key := strings.TrimSpace(parts[0])
			value := strings.TrimSpace(parts[1])
			headers[key] = value
		}
	}
	return headers
}