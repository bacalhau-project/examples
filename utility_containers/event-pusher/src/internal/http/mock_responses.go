package http

import (
	"encoding/json"
	"fmt"
	"net/http"
)

// MockResponses contains various mock HTTP responses for testing
type MockResponses struct {
	// Success cases
	SuccessJSON            *Response
	SuccessText            *Response
	SuccessEmpty           *Response
	SuccessRedirect        *Response
	SuccessWithCustomHeader *Response
	
	// Client error cases
	BadRequest             *Response
	Unauthorized           *Response
	Forbidden              *Response
	NotFound               *Response
	MethodNotAllowed       *Response
	RequestTimeout         *Response
	Conflict               *Response
	TooManyRequests        *Response
	
	// Server error cases
	InternalServerError    *Response
	ServiceUnavailable     *Response
	GatewayTimeout         *Response
	
	// Edge cases
	MalformedJSON          *Response
	LargePayload           *Response
	EmptyHeaders           *Response
	BinaryData             *Response
	SlowResponse           *Response
	UnicodeResponse        *Response
}

// CreateMockFactory returns a factory function that creates a MockClient with predefined responses
func CreateMockFactory(url string, mockResponse *Response) Factory {
	return func() Client {
		mockClient := NewMockClient()
		mockClient.AddResponse(url, mockResponse)
		return mockClient
	}
}

// NewMockResponses creates a new set of mock responses for testing
func NewMockResponses() *MockResponses {
	return &MockResponses{
		// Success cases
		SuccessJSON: &Response{
			StatusCode: http.StatusOK,
			Headers: map[string][]string{
				"Content-Type": {"application/json"},
			},
			Body: `{"status":"success","message":"Operation completed successfully","data":{"id":"123456","name":"Test Item","created_at":"2023-03-20T12:34:56Z"}}`,
		},
		
		SuccessText: &Response{
			StatusCode: http.StatusOK,
			Headers: map[string][]string{
				"Content-Type": {"text/plain"},
			},
			Body: "Operation completed successfully",
		},
		
		SuccessEmpty: &Response{
			StatusCode: http.StatusNoContent,
			Headers: map[string][]string{
				"Content-Type": {"text/plain"},
			},
			Body: "",
		},
		
		SuccessRedirect: &Response{
			StatusCode: http.StatusFound,
			Headers: map[string][]string{
				"Location": {"https://example.com/new-location"},
			},
			Body: "",
		},
		
		SuccessWithCustomHeader: &Response{
			StatusCode: http.StatusOK,
			Headers: map[string][]string{
				"Content-Type":     {"application/json"},
				"X-Custom-Header":  {"custom-value"},
				"X-Request-ID":     {"req-123456"},
				"X-Rate-Limit":     {"100"},
				"X-Rate-Remaining": {"99"},
			},
			Body: `{"status":"success","message":"Operation completed with custom headers"}`,
		},
		
		// Client error cases
		BadRequest: &Response{
			StatusCode: http.StatusBadRequest,
			Headers: map[string][]string{
				"Content-Type": {"application/json"},
			},
			Body: `{"status":"error","code":"bad_request","message":"Invalid request parameters","details":{"field":"user_id","error":"Must be a valid UUID"}}`,
		},
		
		Unauthorized: &Response{
			StatusCode: http.StatusUnauthorized,
			Headers: map[string][]string{
				"Content-Type":     {"application/json"},
				"WWW-Authenticate": {"Bearer"},
			},
			Body: `{"status":"error","code":"unauthorized","message":"Authentication required","details":{"error":"Invalid or expired token"}}`,
		},
		
		Forbidden: &Response{
			StatusCode: http.StatusForbidden,
			Headers: map[string][]string{
				"Content-Type": {"application/json"},
			},
			Body: `{"status":"error","code":"forbidden","message":"Access denied","details":{"error":"Insufficient permissions to access this resource"}}`,
		},
		
		NotFound: &Response{
			StatusCode: http.StatusNotFound,
			Headers: map[string][]string{
				"Content-Type": {"application/json"},
			},
			Body: `{"status":"error","code":"not_found","message":"Resource not found","details":{"resource":"item","id":"999"}}`,
		},
		
		MethodNotAllowed: &Response{
			StatusCode: http.StatusMethodNotAllowed,
			Headers: map[string][]string{
				"Content-Type": {"application/json"},
				"Allow":        {"GET, POST"},
			},
			Body: `{"status":"error","code":"method_not_allowed","message":"Method not allowed","details":{"allowed_methods":["GET","POST"]}}`,
		},
		
		RequestTimeout: &Response{
			StatusCode: http.StatusRequestTimeout,
			Headers: map[string][]string{
				"Content-Type": {"application/json"},
			},
			Body: `{"status":"error","code":"request_timeout","message":"Request timed out","details":{"timeout_seconds":30}}`,
		},
		
		Conflict: &Response{
			StatusCode: http.StatusConflict,
			Headers: map[string][]string{
				"Content-Type": {"application/json"},
			},
			Body: `{"status":"error","code":"conflict","message":"Resource conflict","details":{"error":"A resource with this ID already exists"}}`,
		},
		
		TooManyRequests: &Response{
			StatusCode: http.StatusTooManyRequests,
			Headers: map[string][]string{
				"Content-Type":          {"application/json"},
				"Retry-After":           {"60"},
				"X-Rate-Limit-Reset":    {"1679323476"},
				"X-Rate-Limit-Limit":    {"100"},
				"X-Rate-Limit-Remaining": {"0"},
			},
			Body: `{"status":"error","code":"rate_limited","message":"Too many requests","details":{"retry_after_seconds":60}}`,
		},
		
		// Server error cases
		InternalServerError: &Response{
			StatusCode: http.StatusInternalServerError,
			Headers: map[string][]string{
				"Content-Type": {"application/json"},
			},
			Body: `{"status":"error","code":"internal_error","message":"An internal server error occurred","details":{"request_id":"err-789012"}}`,
		},
		
		ServiceUnavailable: &Response{
			StatusCode: http.StatusServiceUnavailable,
			Headers: map[string][]string{
				"Content-Type": {"application/json"},
				"Retry-After":  {"120"},
			},
			Body: `{"status":"error","code":"service_unavailable","message":"Service temporarily unavailable","details":{"maintenance_window":"2023-03-20T14:00:00Z to 2023-03-20T16:00:00Z"}}`,
		},
		
		GatewayTimeout: &Response{
			StatusCode: http.StatusGatewayTimeout,
			Headers: map[string][]string{
				"Content-Type": {"application/json"},
			},
			Body: `{"status":"error","code":"gateway_timeout","message":"Gateway timeout","details":{"upstream_service":"database"}}`,
		},
		
		// Edge cases
		MalformedJSON: &Response{
			StatusCode: http.StatusOK,
			Headers: map[string][]string{
				"Content-Type": {"application/json"},
			},
			Body: `{"status":"success","message":"This JSON is malformed"`, // Missing closing brace
		},
		
		LargePayload: &Response{
			StatusCode: http.StatusOK,
			Headers: map[string][]string{
				"Content-Type": {"application/json"},
			},
			Body: generateLargeJSON(50), // Generate a smaller JSON payload for tests
		},
		
		EmptyHeaders: &Response{
			StatusCode: http.StatusOK,
			Headers:    map[string][]string{},
			Body:       `{"status":"success","message":"Response with empty headers"}`,
		},
		
		BinaryData: &Response{
			StatusCode: http.StatusOK,
			Headers: map[string][]string{
				"Content-Type": {"application/octet-stream"},
			},
			Body: "\x00\x01\x02\x03\x04\xFF\xFE\xFD",
		},
		
		SlowResponse: &Response{
			StatusCode: http.StatusOK,
			Headers: map[string][]string{
				"Content-Type": {"application/json"},
			},
			Body: `{"status":"success","message":"This response was slow","latency_ms":5000}`,
		},
		
		UnicodeResponse: &Response{
			StatusCode: http.StatusOK,
			Headers: map[string][]string{
				"Content-Type": {"application/json; charset=utf-8"},
			},
			Body: `{"status":"success","message":"Unicode test: こんにちは世界 🌍🚀🔥","emoji":"😀🙂🤔🤯😱"}`,
		},
	}
}

// TestMockClients creates a set of mock clients with pre-configured responses
func TestMockClients() map[string]Client {
	responses := NewMockResponses()
	
	clients := make(map[string]Client)
	
	// Success cases
	successJSON := NewMockClient()
	successJSON.AddResponse("https://api.example.com/success", responses.SuccessJSON)
	clients["successJSON"] = successJSON
	
	// Error cases
	notFound := NewMockClient()
	notFound.AddResponse("https://api.example.com/item/999", responses.NotFound)
	clients["notFound"] = notFound
	
	serverError := NewMockClient()
	serverError.AddResponse("https://api.example.com/error", responses.InternalServerError)
	clients["serverError"] = serverError
	
	// Rate limiting
	rateLimited := NewMockClient()
	rateLimited.AddResponse("https://api.example.com/limited", responses.TooManyRequests)
	clients["rateLimited"] = rateLimited
	
	// Auth errors
	auth := NewMockClient()
	auth.AddResponse("https://api.example.com/auth/invalid", responses.Unauthorized)
	auth.AddResponse("https://api.example.com/auth/forbidden", responses.Forbidden)
	clients["auth"] = auth
	
	// Mixed responses (different URLs, same client)
	mixed := NewMockClient()
	mixed.AddResponse("https://api.example.com/users", responses.SuccessJSON)
	mixed.AddResponse("https://api.example.com/users/404", responses.NotFound)
	mixed.AddResponse("https://api.example.com/users/error", responses.InternalServerError)
	clients["mixed"] = mixed
	
	// Client that always returns server error
	alwaysError := NewMockClient()
	alwaysError.SetDefaultStatus(500)
	clients["alwaysError"] = alwaysError
	
	return clients
}

// generateLargeJSON generates a large JSON payload with the specified number of items
func generateLargeJSON(count int) string {
	type Item struct {
		ID          int      `json:"id"`
		Name        string   `json:"name"`
		Description string   `json:"description"`
		Category    string   `json:"category"`
		Tags        []string `json:"tags"`
		CreatedAt   string   `json:"created_at"`
		UpdatedAt   string   `json:"updated_at"`
	}
	
	items := make([]Item, count)
	for i := 0; i < count; i++ {
		items[i] = Item{
			ID:          i + 1,
			Name:        fmt.Sprintf("Item %d", i+1),
			Description: fmt.Sprintf("This is a description for item %d with some extra text to make it longer", i+1),
			Category:    fmt.Sprintf("Category %d", (i % 10) + 1),
			Tags:        []string{fmt.Sprintf("tag-%d", i%5), fmt.Sprintf("tag-%d", (i+1)%5), fmt.Sprintf("tag-%d", (i+2)%5)},
			CreatedAt:   "2023-03-20T12:34:56Z",
			UpdatedAt:   "2023-03-20T13:45:67Z",
		}
	}
	
	response := struct {
		Status  string `json:"status"`
		Message string `json:"message"`
		Count   int    `json:"count"`
		Data    []Item `json:"data"`
	}{
		Status:  "success",
		Message: "Large dataset retrieved successfully",
		Count:   count,
		Data:    items,
	}
	
	jsonBytes, _ := json.Marshal(response)
	return string(jsonBytes)
}