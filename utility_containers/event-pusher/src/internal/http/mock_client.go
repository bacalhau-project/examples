package http

import "fmt"

// MockClient implements Client for testing
type MockClient struct {
	headers       map[string]string
	responses     map[string]*Response // Responses keyed by URL
	requestLog    []MockRequest        // Log of requests made
	defaultStatus int                  // Default status code for responses
}

// MockRequest represents a recorded HTTP request
type MockRequest struct {
	Method  uint32
	URL     string
	Headers map[string]string
	Body    string
}

// NewMockClient creates a new mock HTTP client
func NewMockClient() *MockClient {
	return &MockClient{
		headers:       make(map[string]string),
		responses:     make(map[string]*Response),
		requestLog:    make([]MockRequest, 0),
		defaultStatus: 200,
	}
}

// SetDefaultStatus sets the default status code for mock responses
func (c *MockClient) SetDefaultStatus(status int) {
	c.defaultStatus = status
}

// AddResponse adds a mock response for a specific URL
func (c *MockClient) AddResponse(url string, response *Response) {
	c.responses[url] = response
}

// GetRequestLog returns the log of requests made
func (c *MockClient) GetRequestLog() []MockRequest {
	return c.requestLog
}

// GetMethodConstant converts a string method to its uint32 constant
func (c *MockClient) GetMethodConstant(method string) (uint32, error) {
	switch method {
	case "GET":
		return MethodGet, nil
	case "POST":
		return MethodPost, nil
	case "PUT":
		return MethodPut, nil
	case "DELETE":
		return MethodDelete, nil
	case "HEAD":
		return MethodHead, nil
	case "OPTIONS":
		return MethodOptions, nil
	case "PATCH":
		return MethodPatch, nil
	default:
		return 0, fmt.Errorf("unsupported HTTP method: %s", method)
	}
}

// GetHeaders returns the HTTP headers
func (c *MockClient) GetHeaders() map[string]string {
	if c.headers == nil {
		c.headers = make(map[string]string)
	}
	return c.headers
}

// Request logs the request and returns a mock response
func (c *MockClient) Request(method uint32, url string, headers map[string]string, body string) (*Response, error) {
	// Log the request
	c.requestLog = append(c.requestLog, MockRequest{
		Method:  method,
		URL:     url,
		Headers: headers,
		Body:    body,
	})

	// Return a predefined response if one exists for this URL
	if response, exists := c.responses[url]; exists {
		return response, nil
	}

	// Otherwise return a default response
	return &Response{
		StatusCode: c.defaultStatus,
		Headers: map[string][]string{
			"Content-Type": {"application/json"},
		},
		Body: `{"status": "success", "message": "This is a mock response"}`,
	}, nil
}