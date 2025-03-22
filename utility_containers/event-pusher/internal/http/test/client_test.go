package test

import (
	"testing"

	"github.com/bacalhau-project/examples/utility_containers/event-pusher/internal/http"
	"github.com/stretchr/testify/assert"
)

// TestHTTPClientWithMocks demonstrates how to use mock responses in application tests
func TestHTTPClientWithMocks(t *testing.T) {
	// Create a set of mock responses
	responses := http.NewMockResponses()
	
	// Create a mock client for your application
	mockClient := http.NewMockClient()
	
	// 1. Set up success case
	t.Run("Successful Request", func(t *testing.T) {
		// Configure the mock client with a success response for a specific URL
		testURL := "https://api.example.com/success"
		mockClient.AddResponse(testURL, responses.SuccessJSON)
		
		// Make the request
		response, err := mockClient.Request(http.MethodGet, testURL, nil, "")
		
		// Verify the response
		assert.NoError(t, err)
		assert.Equal(t, 200, response.StatusCode)
		assert.Contains(t, response.Body, "success")
		
		// Verify request was logged
		requestLog := mockClient.GetRequestLog()
		assert.Equal(t, 1, len(requestLog))
		assert.Equal(t, testURL, requestLog[0].URL)
	})
	
	// 2. Test error handling for a 404 response
	t.Run("Not Found Response", func(t *testing.T) {
		// Create a fresh mock client
		mockClient := http.NewMockClient()
		
		// Configure the mock client with a 404 response
		testURL := "https://api.example.com/missing"
		mockClient.AddResponse(testURL, responses.NotFound)
		
		// Make the request
		response, err := mockClient.Request(http.MethodGet, testURL, nil, "")
		
		// Verify the response
		assert.NoError(t, err) // HTTP errors don't return Go errors
		assert.Equal(t, 404, response.StatusCode)
		assert.Contains(t, response.Body, "not_found")
	})
	
	// 3. Test server error handling
	t.Run("Server Error", func(t *testing.T) {
		// Create a fresh mock client
		mockClient := http.NewMockClient()
		
		// Configure all requests to return 500
		mockClient.SetDefaultStatus(500)
		
		// Configure specific response
		testURL := "https://api.example.com/error"
		mockClient.AddResponse(testURL, responses.InternalServerError)
		
		// Make the request
		response, err := mockClient.Request(http.MethodGet, testURL, nil, "")
		
		// Verify the response
		assert.NoError(t, err) // HTTP errors don't return Go errors
		assert.Equal(t, 500, response.StatusCode)
		assert.Contains(t, response.Body, "internal_error")
	})
	
	// 4. Test authentication error
	t.Run("Authentication Required", func(t *testing.T) {
		// Create a fresh mock client
		mockClient := http.NewMockClient()
		
		// Configure the mock client with a 401 response
		testURL := "https://api.example.com/protected"
		mockClient.AddResponse(testURL, responses.Unauthorized)
		
		// Make the request (without auth token)
		response, err := mockClient.Request(http.MethodGet, testURL, nil, "")
		
		// Verify the response
		assert.NoError(t, err)
		assert.Equal(t, 401, response.StatusCode)
		assert.Contains(t, response.Body, "unauthorized")
		
		// Get WWW-Authenticate header
		authHeader := response.Headers["WWW-Authenticate"]
		assert.Equal(t, []string{"Bearer"}, authHeader)
	})
	
	// 5. Test with factory pattern (integration with application code)
	t.Run("Using Factory Pattern", func(t *testing.T) {
		// Save original factory
		originalFactory := http.DefaultFactory
		defer func() {
			http.SetFactory(originalFactory)
		}()
		
		// Create a factory that returns a mock client
		testURL := "https://api.example.com/factory-test"
		http.SetFactory(http.CreateMockFactory(testURL, responses.SuccessWithCustomHeader))
		
		// Get a client using the factory (this would be done in your application code)
		client := http.New()
		
		// Make a request with the client
		response, err := client.Request(http.MethodGet, testURL, nil, "")
		
		// Verify response
		assert.NoError(t, err)
		assert.Equal(t, 200, response.StatusCode)
		assert.Contains(t, response.Body, "custom headers")
		
		// Check custom headers
		assert.Equal(t, []string{"custom-value"}, response.Headers["X-Custom-Header"])
	})
	
	// 6. Test rate limiting handling
	t.Run("Rate Limiting", func(t *testing.T) {
		// Create a fresh mock client
		mockClient := http.NewMockClient()
		
		// Configure the mock client with a rate limit response
		testURL := "https://api.example.com/rate-limited"
		mockClient.AddResponse(testURL, responses.TooManyRequests)
		
		// Make the request
		response, err := mockClient.Request(http.MethodGet, testURL, nil, "")
		
		// Verify the response
		assert.NoError(t, err)
		assert.Equal(t, 429, response.StatusCode)
		
		// Check rate limit headers
		assert.Equal(t, []string{"60"}, response.Headers["Retry-After"])
		assert.Equal(t, []string{"0"}, response.Headers["X-Rate-Limit-Remaining"])
	})
}

// TestWithMultipleEndpoints demonstrates testing with a client that handles multiple endpoints
func TestWithMultipleEndpoints(t *testing.T) {
	// Get mock responses
	mockClients := http.TestMockClients()
	
	// Test mixed client that handles different URLs differently
	mixedClient := mockClients["mixed"]
	
	// Test success endpoint
	successResponse, err := mixedClient.Request(http.MethodGet, "https://api.example.com/users", nil, "")
	assert.NoError(t, err)
	assert.Equal(t, 200, successResponse.StatusCode)
	
	// Test not found endpoint
	notFoundResponse, err := mixedClient.Request(http.MethodGet, "https://api.example.com/users/404", nil, "")
	assert.NoError(t, err)
	assert.Equal(t, 404, notFoundResponse.StatusCode)
	
	// Test error endpoint
	errorResponse, err := mixedClient.Request(http.MethodGet, "https://api.example.com/users/error", nil, "")
	assert.NoError(t, err)
	assert.Equal(t, 500, errorResponse.StatusCode)
}

// TestHTTPMethods demonstrates testing different HTTP methods
func TestHTTPMethods(t *testing.T) {
	// Create mock client
	mockClient := http.NewMockClient()
	responses := http.NewMockResponses()
	
	// Add a success response
	testURL := "https://api.example.com/resource"
	mockClient.AddResponse(testURL, responses.SuccessJSON)
	
	// Test different HTTP methods
	methods := []struct {
		name        string
		methodConst uint32
	}{
		{"GET", http.MethodGet},
		{"POST", http.MethodPost},
		{"PUT", http.MethodPut},
		{"DELETE", http.MethodDelete},
		{"PATCH", http.MethodPatch},
	}
	
	for _, m := range methods {
		t.Run(m.name, func(t *testing.T) {
			// Make the request
			response, err := mockClient.Request(m.methodConst, testURL, nil, "test body")
			
			// Verify the response
			assert.NoError(t, err)
			assert.Equal(t, 200, response.StatusCode)
			
			// Verify method was logged correctly
			requestLog := mockClient.GetRequestLog()
			lastRequest := requestLog[len(requestLog)-1]
			assert.Equal(t, m.methodConst, lastRequest.Method)
			assert.Equal(t, "test body", lastRequest.Body)
		})
	}
}