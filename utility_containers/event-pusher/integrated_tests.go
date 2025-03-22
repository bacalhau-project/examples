package main

import (
	"fmt"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/bacalhau-project/examples/utility_containers/event-pusher/internal/http"
	"github.com/bacalhau-project/examples/utility_containers/event-pusher/internal/messages"
	"github.com/bacalhau-project/examples/utility_containers/event-pusher/internal/utils"
	"github.com/stretchr/testify/assert"
)

// TestBasicHTTPIntegration tests HTTP integration with environment configuration
func TestBasicHTTPIntegration(t *testing.T) {
	// Save original environment
	oldEnv := os.Environ()
	defer func() {
		os.Clearenv()
		for _, env := range oldEnv {
			parts := strings.SplitN(env, "=", 2)
			if len(parts) == 2 {
				os.Setenv(parts[0], parts[1])
			}
		}
	}()

	// Check if integration testing is enabled
	integrationEnabled := os.Getenv("ENABLE_HTTP_INTEGRATION_TEST")
	if integrationEnabled == "" {
		t.Skip("Skipping HTTP integration test. Set ENABLE_HTTP_INTEGRATION_TEST=true to enable.")
	}

	// Check required environment variables
	httpURL := os.Getenv("HTTP_URL")
	if httpURL == "" {
		t.Skip("Skipping HTTP integration test. HTTP_URL environment variable is required.")
	}

	// Load configuration
	config := loadTestConfig()

	// Create HTTP client
	httpClient := http.New()

	// Parse headers
	headers := utils.ParseHeaders(config.Headers)

	// Convert method string to constant
	methodCode, err := httpClient.GetMethodConstant(config.Method)
	assert.NoError(t, err)

	// Test multiple requests if requested
	requestCount := 1
	requestCountStr := os.Getenv("HTTP_TEST_REQUEST_COUNT")
	if requestCountStr != "" {
		_, err := fmt.Sscanf(requestCountStr, "%d", &requestCount)
		if err != nil || requestCount < 1 {
			requestCount = 1
		}
	}

	// Track response times
	var responseTimes []time.Duration

	// Make the requests
	for i := 0; i < requestCount; i++ {
		startTime := time.Now()
		response, err := httpClient.Request(methodCode, config.URL, headers, config.Body)
		elapsed := time.Since(startTime)
		responseTimes = append(responseTimes, elapsed)

		// Assert on response
		assert.NoError(t, err, "HTTP request %d should not error", i+1)
		assert.NotNil(t, response, "Response %d should not be nil", i+1)
		assert.True(t, response.StatusCode >= 200 && response.StatusCode < 300,
			"Expected successful status code for request %d, got: %d", i+1, response.StatusCode)

		// Log response details
		t.Logf("Request %d - Status: %d, Time: %v", i+1, response.StatusCode, elapsed)

		// Sleep between requests if multiple
		if i < requestCount-1 && requestCount > 1 {
			time.Sleep(100 * time.Millisecond)
		}
	}

	// Calculate and log statistics if multiple requests
	if requestCount > 1 {
		var totalTime time.Duration
		minTime := responseTimes[0]
		maxTime := responseTimes[0]

		for _, respTime := range responseTimes {
			totalTime += respTime
			if respTime < minTime {
				minTime = respTime
			}
			if respTime > maxTime {
				maxTime = respTime
			}
		}

		avgTime := totalTime / time.Duration(requestCount)
		t.Logf("HTTP Performance - Min: %v, Max: %v, Avg: %v, Total: %v",
			minTime, maxTime, avgTime, totalTime)
	}
}

// loadTestConfig loads configuration from environment variables for testing
func loadTestConfig() TestConfig {
	config := TestConfig{
		Method:  utils.GetEnvWithDefault("HTTP_METHOD", "GET"),
		URL:     os.Getenv("HTTP_URL"),
		Headers: os.Getenv("HTTP_HEADERS"),
		Body:    os.Getenv("HTTP_BODY"),
		Mode:    utils.GetEnvWithDefault("MODE", "auto"),
	}
	return config
}

// TestConfig for the test - simplified version of the main application's Config
type TestConfig struct {
	// HTTP mode config
	Method  string
	URL     string
	Headers string
	Body    string
	Mode    string
}

// TestLiveHTTPEndpoint tests that we can connect to an actual HTTP endpoint
// This is controlled by the TEST_LIVE_HTTP_ENDPOINT environment variable
func TestLiveHTTPEndpoint(t *testing.T) {
	// Get endpoint from environment
	endpoint := os.Getenv("TEST_LIVE_HTTP_ENDPOINT")
	if endpoint == "" {
		t.Skip("Skipping live HTTP test. Set TEST_LIVE_HTTP_ENDPOINT environment variable to enable.")
	}

	// Create HTTP client
	client := http.New()

	// Get method constant
	method, err := client.GetMethodConstant("GET")
	assert.NoError(t, err)

	// Make the request
	response, err := client.Request(method, endpoint, nil, "")

	// Check for errors
	assert.NoError(t, err, "HTTP request should not fail")

	// Validate response
	assert.NotNil(t, response, "Response should not be nil")
	assert.Equal(t, 200, response.StatusCode, "Expected status code 200")
	assert.NotEmpty(t, response.Body, "Response body should not be empty")

	// Log response for debugging
	t.Logf("Successfully received response: Status: %d, Body length: %d",
		response.StatusCode, len(response.Body))
}

// TestLiveHTTPWithJSON tests POST with JSON data to an actual HTTP endpoint
// This is controlled by the TEST_LIVE_HTTP_POST_ENDPOINT environment variable
func TestLiveHTTPWithJSON(t *testing.T) {
	// Get endpoint from environment
	endpoint := os.Getenv("TEST_LIVE_HTTP_POST_ENDPOINT")
	if endpoint == "" {
		t.Skip("Skipping live HTTP POST test. Set TEST_LIVE_HTTP_POST_ENDPOINT environment variable to enable.")
	}

	// Create HTTP client
	client := http.New()

	// Get method constant
	method, err := client.GetMethodConstant("POST")
	assert.NoError(t, err)

	// Create headers for JSON
	headers := map[string]string{
		"Content-Type": "application/json",
		"Accept":       "application/json",
	}

	// JSON payload
	jsonBody := `{
		"name": "Test User",
		"email": "test@example.com",
		"message": "This is a test message"
	}`

	// Make the request
	response, err := client.Request(method, endpoint, headers, jsonBody)

	// Check for errors
	assert.NoError(t, err, "HTTP request should not fail")

	// Validate response
	assert.NotNil(t, response, "Response should not be nil")
	assert.Equal(t, 200, response.StatusCode, "Expected status code 200")
	assert.NotEmpty(t, response.Body, "Response body should not be empty")

	// Check for JSON content type in response
	contentType := ""
	if ctHeaders, ok := response.Headers["Content-Type"]; ok && len(ctHeaders) > 0 {
		contentType = ctHeaders[0]
	}
	assert.Contains(t, contentType, "application/json", "Expected JSON response")

	// Log response for debugging
	t.Logf("Successfully received response: Status: %d, Content-Type: %s, Body length: %d",
		response.StatusCode, contentType, len(response.Body))
}

// TestSQSMessageSending tests sending messages to SQS
func TestSQSMessageSending(t *testing.T) {
	// Check if SQS testing is enabled
	if os.Getenv("ENABLE_SQS_TEST") != "true" {
		t.Skip("Skipping SQS test. Set ENABLE_SQS_TEST=true to enable.")
	}

	// Create SQS configuration from environment variables
	sqsConfig := messages.SQSConfig{
		Region:    os.Getenv("AWS_REGION"),
		AccessKey: os.Getenv("AWS_ACCESS_KEY_ID"),
		SecretKey: os.Getenv("AWS_SECRET_ACCESS_KEY"),
		QueueURL:  os.Getenv("SQS_QUEUE_URL"),
		Simulate:  os.Getenv("SIMULATE") == "true",
	}

	// Create SQS client
	sqsClient := messages.NewSQSSender(sqsConfig)

	// Create message generator
	generator := messages.NewDefaultGenerator()

	// Determine number of test messages
	messageCount := 3
	if os.Getenv("SQS_TEST_MESSAGE_COUNT") != "" {
		t.Logf("Using SQS_TEST_MESSAGE_COUNT=%s", os.Getenv("SQS_TEST_MESSAGE_COUNT"))
		fmt.Sscanf(os.Getenv("SQS_TEST_MESSAGE_COUNT"), "%d", &messageCount)
	}

	// Use fixed values for testing
	randomOff := os.Getenv("RANDOM_OFF") == "true"
	vmName := os.Getenv("VM_NAME")
	if vmName == "" {
		vmName = "test-vm"
	}

	color := os.Getenv("COLOR")
	if color == "" || !messages.IsValidHexColor(color) {
		color = "#FF0000"
	}

	// Send test messages
	for i := 0; i < messageCount; i++ {
		// Create message
		message := messages.Message{
			VMName:      vmName,
			IconName:    generator.GetRandomIcon(randomOff),
			Timestamp:   generator.GetCurrentTimestamp(),
			Color:       color,
			ContainerID: generator.GenerateContainerID(randomOff),
		}

		// Send message to SQS
		err := sqsClient.SendMessage(message)
		assert.NoError(t, err, "Failed to send message %d to SQS", i+1)
	}
}
