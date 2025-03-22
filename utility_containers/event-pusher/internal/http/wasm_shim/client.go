//go:build !wasm
// +build !wasm

// Package client provides a shim for the WASM HTTP client
package client

// No imports needed

// Headers is a map of strings to string arrays
type Headers map[string][]string

// Set sets a header in the map
func (h Headers) Set(key, value string) {
	h[key] = []string{value}
}

// Const values for HTTP methods
const (
	MethodGet     uint32 = 0
	MethodPost    uint32 = 1
	MethodPut     uint32 = 2
	MethodDelete  uint32 = 3
	MethodHead    uint32 = 4
	MethodOptions uint32 = 5
	MethodPatch   uint32 = 6
)

// Response is a response from an HTTP request
type Response struct {
	StatusCode uint32
	Headers    map[string][]string
	Body       string
}

// Client is an HTTP client interface
type Client interface {
	Request(method uint32, url string, headers Headers, body string) (*Response, error)
}

// clientImpl implements the Client interface
type clientImpl struct{}

// Request makes an HTTP request (implementation for non-WASM builds)
func (c *clientImpl) Request(method uint32, url string, headers Headers, body string) (*Response, error) {
	return &Response{
		StatusCode: 200,
		Headers: map[string][]string{
			"Content-Type": {"application/json"},
		},
		Body: `{"message": "Mock response from shim"}`,
	}, nil
}

// NewClient creates a new HTTP client
func NewClient() Client {
	return &clientImpl{}
}