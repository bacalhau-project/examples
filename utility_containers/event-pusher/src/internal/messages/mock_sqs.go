package messages

import (
	"encoding/json"
	"fmt"
	"strings"
	"sync"
)

// MockSQSClient implements SQS functionality for testing
type MockSQSClient struct {
	messages []Message     // Storage for sent messages
	config   SQSConfig     // Configuration
	mu       sync.Mutex    // For thread safety
}

// NewMockSQSClient creates a new MockSQSClient
func NewMockSQSClient(config SQSConfig) *MockSQSClient {
	return &MockSQSClient{
		messages: []Message{},
		config:   config,
	}
}

// SendMessage mocks sending a message to SQS
func (c *MockSQSClient) SendMessage(msg Message) error {
	// If in simulation mode, just log
	if c.config.Simulate {
		msgJSON, _ := json.Marshal(msg)
		fmt.Printf("Simulation: Would send message to %s: %s\n", c.config.QueueURL, string(msgJSON))
		return nil
	}
	
	// Store the message
	c.mu.Lock()
	defer c.mu.Unlock()
	c.messages = append(c.messages, msg)
	
	// Return success
	return nil
}

// GetLastMessages returns the last N messages sent
func (c *MockSQSClient) GetLastMessages(count int) []Message {
	c.mu.Lock()
	defer c.mu.Unlock()
	
	// If no messages, return empty slice
	if len(c.messages) == 0 {
		return []Message{}
	}
	
	// If count is zero or negative, return all messages
	if count <= 0 {
		return c.messages
	}
	
	// If requesting more than we have, return all
	if count >= len(c.messages) {
		return c.messages
	}
	
	// Return the last 'count' messages
	return c.messages[len(c.messages)-count:]
}

// ClearMessages clears all stored messages
func (c *MockSQSClient) ClearMessages() {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.messages = []Message{}
}

// GetConfig returns the SQS configuration
func (c *MockSQSClient) GetConfig() SQSConfig {
	return c.config
}

// UpdateConfig updates the SQS configuration
func (c *MockSQSClient) UpdateConfig(config SQSConfig) {
	c.config = config
}

// GetQueueName extracts the queue name from the queue URL
func (c *MockSQSClient) GetQueueName() string {
	// Simple extraction of the last part of the URL
	urlParts := strings.Split(c.config.QueueURL, "/")
	if len(urlParts) > 0 {
		return urlParts[len(urlParts)-1]
	}
	return "unknown-queue"
}