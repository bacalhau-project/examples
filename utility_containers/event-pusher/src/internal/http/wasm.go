//go:build wasm
// +build wasm

package http

import (
	"fmt"
	"strings"

	"github.com/bacalhau-project/bacalhau/pkg/executor/wasm/funcs/http/client"
)

// WASMClient implements Client for WASM environment
type WASMClient struct {
	headers client.Headers
}

// GetMethodConstant converts a string method to its uint32 constant
func (c *WASMClient) GetMethodConstant(method string) (uint32, error) {
	switch strings.ToUpper(method) {
	case "GET":
		return client.MethodGet, nil
	case "POST":
		return client.MethodPost, nil
	case "PUT":
		return client.MethodPut, nil
	case "DELETE":
		return client.MethodDelete, nil
	case "HEAD":
		return client.MethodHead, nil
	case "OPTIONS":
		return client.MethodOptions, nil
	case "PATCH":
		return client.MethodPatch, nil
	default:
		return 0, fmt.Errorf("unsupported HTTP method: %s", method)
	}
}

// GetHeaders returns the HTTP headers
func (c *WASMClient) GetHeaders() map[string]string {
	if c.headers == nil {
		c.headers = make(client.Headers)
	}
	// Convert client.Headers to map[string]string
	result := make(map[string]string)
	for k, v := range c.headers {
		if len(v) > 0 {
			result[k] = v[0]
		}
	}
	return result
}

// Request makes an HTTP request using the WASM client
func (c *WASMClient) Request(method uint32, url string, headers map[string]string, body string) (*Response, error) {
	// Convert headers to client.Headers
	wasmHeaders := make(client.Headers)
	for k, v := range headers {
		wasmHeaders[k] = []string{v}
	}

	// Create WASM client
	wasmClient := client.NewClient()

	// Make the request
	response, err := wasmClient.Request(method, url, wasmHeaders, body)
	if err != nil {
		return nil, err
	}

	// Convert response to our Response type
	return &Response{
		StatusCode: int(response.StatusCode),
		Headers:    response.Headers,
		Body:       response.Body,
	}, nil
}

// NewWASMClient creates a new WASM HTTP client
func NewWASMClient() Client {
	return &WASMClient{}
}

// init overrides the default factory for WASM builds
func init() {
	SetFactory(func() Client {
		return NewWASMClient()
	})
}