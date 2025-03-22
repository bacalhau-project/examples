// Package http provides HTTP client implementations and interfaces
package http

import (
	"bytes"
	"fmt"
	"io"
	"net/http"
	"strings"
)

// Method constants
const (
	MethodGet     uint32 = 0
	MethodPost    uint32 = 1
	MethodPut     uint32 = 2
	MethodDelete  uint32 = 3
	MethodHead    uint32 = 4
	MethodOptions uint32 = 5
	MethodPatch   uint32 = 6
)

// Response represents an HTTP response
type Response struct {
	StatusCode int
	Headers    map[string][]string
	Body       string
}

// Client defines the interface for HTTP operations
type Client interface {
	// GetMethodConstant converts a string method to its uint32 constant
	GetMethodConstant(method string) (uint32, error)
	// GetHeaders returns the HTTP headers
	GetHeaders() map[string]string
	// Request makes an HTTP request
	Request(method uint32, url string, headers map[string]string, body string) (*Response, error)
}

// DefaultClient implements Client for standard Go
type DefaultClient struct {
	headers map[string]string
}

// GetMethodConstant converts a string method to its uint32 constant
func (c *DefaultClient) GetMethodConstant(method string) (uint32, error) {
	switch strings.ToUpper(method) {
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
func (c *DefaultClient) GetHeaders() map[string]string {
	if c.headers == nil {
		c.headers = make(map[string]string)
	}
	return c.headers
}

// Request makes an HTTP request
func (c *DefaultClient) Request(method uint32, url string, headers map[string]string, body string) (*Response, error) {
	// Convert method code to string
	var methodStr string
	switch method {
	case MethodGet:
		methodStr = "GET"
	case MethodPost:
		methodStr = "POST"
	case MethodPut:
		methodStr = "PUT"
	case MethodDelete:
		methodStr = "DELETE"
	case MethodHead:
		methodStr = "HEAD"
	case MethodOptions:
		methodStr = "OPTIONS"
	case MethodPatch:
		methodStr = "PATCH"
	default:
		return nil, fmt.Errorf("unsupported HTTP method code: %d", method)
	}

	// Create request
	var reqBody io.Reader
	if body != "" {
		reqBody = bytes.NewBufferString(body)
	}
	
	req, err := http.NewRequest(methodStr, url, reqBody)
	if err != nil {
		return nil, fmt.Errorf("error creating request: %v", err)
	}

	// Add headers
	for key, value := range headers {
		req.Header.Add(key, value)
	}

	// Make the request
	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("error making request: %v", err)
	}
	defer resp.Body.Close()

	// Read response body
	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("error reading response body: %v", err)
	}

	// Convert response
	response := &Response{
		StatusCode: resp.StatusCode,
		Headers:    resp.Header,
		Body:       string(bodyBytes),
	}

	return response, nil
}

// Factory is a function that creates a new Client
type Factory func() Client

// DefaultFactory is the default implementation of the client factory
var DefaultFactory Factory = func() Client {
	return &DefaultClient{}
}

// SetFactory allows changing the factory function for creating HTTP clients
func SetFactory(factory Factory) {
	DefaultFactory = factory
}

// New creates a new HTTP client using the factory
func New() Client {
	return DefaultFactory()
}