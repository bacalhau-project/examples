// This file contains mock implementations for testing
package main

import (
	"encoding/json"
	"fmt"
	"strings"

	"github.com/bacalhau-project/examples/utility_containers/event-pusher/internal/messages"
)

// SQSConfig contains configuration for SQS messaging
type SQSConfig struct {
	Region    string
	AccessKey string
	SecretKey string
	QueueURL  string
	Simulate  bool
}

// SQSSender interface defines methods for sending SQS messages
type SQSSender interface {
	SendMessage(msg messages.Message) error
	GetLastMessages(count int) []messages.Message
}

// MockSQSSender implements SQSSender for testing purposes
type MockSQSSender struct {
	Config     messages.SQSConfig
	MessageLog []messages.Message
}

// NewSQSSender creates a new SQS message sender
func NewSQSSender(config messages.SQSConfig) *MockSQSSender {
	return &MockSQSSender{
		Config:     config,
		MessageLog: make([]messages.Message, 0),
	}
}

// SendMessage mocks sending a message to an SQS queue
func (s *MockSQSSender) SendMessage(msg messages.Message) error {
	// Add message to log
	s.MessageLog = append(s.MessageLog, msg)

	// Skip all HTTP work if in simulation mode
	if s.Config.Simulate {
		msgJSON, _ := json.Marshal(msg)
		fmt.Printf("Simulation: Would send message to %s: %s\n", s.Config.QueueURL, string(msgJSON))
		return nil
	}

	// Validate SQS config
	if strings.TrimSpace(s.Config.QueueURL) == "" {
		return fmt.Errorf("missing required SQS queue URL")
	}

	// In mock implementation, simply print the message that would be sent
	msgJSON, _ := json.Marshal(msg)
	fmt.Printf("Mock SQS: Sending message to %s: %s\n", s.Config.QueueURL, string(msgJSON))
	return nil
}

// GetLastMessages returns the last N messages sent (for testing)
func (s *MockSQSSender) GetLastMessages(count int) []messages.Message {
	if count <= 0 || count > len(s.MessageLog) {
		count = len(s.MessageLog)
	}
	result := make([]messages.Message, count)
	start := len(s.MessageLog) - count
	for i := 0; i < count; i++ {
		result[i] = s.MessageLog[start+i]
	}
	return result
}
