package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"sync"
	"time"

	"github.com/bacalhau-project/bacalhau/pkg/executor/wasm/funcs/http/client"
)

const (
	// MessageSendTimeout is the maximum time allowed for sending a message
	MessageSendTimeout = 5 * time.Second
)

// Publisher handles message publishing to the SQS proxy
type Publisher struct {
	config           *RuntimeConfig
	client           *client.Client
	messageGenerator *MessageGenerator
	messageCount     int
	mu               sync.Mutex
}

// NewPublisher creates a new publisher instance
func NewPublisher(config *RuntimeConfig) (*Publisher, error) {
	client := client.NewClient()
	if client == nil {
		return nil, fmt.Errorf("failed to create HTTP client")
	}

	return &Publisher{
		config:           config,
		client:           client,
		messageGenerator: NewMessageGenerator(),
	}, nil
}

// shouldContinue checks if we should continue sending messages
func (p *Publisher) shouldContinue() bool {
	p.mu.Lock()
	defer p.mu.Unlock()
	if p.config.MaxMessages > 0 && p.messageCount >= p.config.MaxMessages {
		fmt.Printf("Reached maximum message count (%d)\n", p.config.MaxMessages)
		return false
	}
	return true
}

// sendMessage sends a single message to the proxy
func (p *Publisher) sendMessage(config *RuntimeConfig) error {
	p.mu.Lock()
	p.messageCount++
	count := p.messageCount
	p.mu.Unlock()

	message := p.messageGenerator.GetMessage(*config)
	fmt.Printf("[%d] Sending message to %s\n", count, p.config.ProxyURL)

	// Marshal the message to JSON
	messageJSON, err := json.Marshal(message)
	if err != nil {
		return fmt.Errorf("error marshaling message: %v", err)
	}

	// Create a channel for the response
	done := make(chan error)
	go func() {
		headers := map[string][]string{"Content-Type": {"application/json"}}
		response, err := p.client.Post(p.config.ProxyURL+"/send", headers, string(messageJSON))
		if err != nil {
			done <- fmt.Errorf("error sending message: %v", err)
			return
		}

		fmt.Printf("Response Status: %d\n", response.StatusCode)
		fmt.Printf("Response Body: %s\n", response.Body)
		done <- nil
	}()

	// Wait for either completion or timeout
	select {
	case err := <-done:
		return err
	case <-time.After(MessageSendTimeout):
		return fmt.Errorf("timeout after %v while sending message", MessageSendTimeout)
	}
}

// Run starts the publisher and sends messages until stopped
func (p *Publisher) Run() error {
	err := p.checkProxyHealth()
	if err != nil {
		return err
	}

	fmt.Printf("Starting publisher to %s with %d second interval and max-messages %d\n",
		p.config.ProxyURL, p.config.Interval, p.config.MaxMessages)

	for {
		if !p.shouldContinue() {
			return nil
		}
		fmt.Printf("Attempting to send message...\n")
		if err := p.sendMessage(p.config); err != nil {
			fmt.Printf("Warning: %v\n", err)
		} else {
			fmt.Printf("Message sent successfully, sleeping for %d seconds...\n", p.config.Interval)
		}
		time.Sleep(time.Duration(p.config.Interval) * time.Second)
	}
}

func (p *Publisher) checkProxyHealth() error {
	// test we can reach the proxy by calling /health endpoint
	healthEndpoint := fmt.Sprintf("%s/health", p.config.ProxyURL)
	response, err := p.client.Get(healthEndpoint, nil)
	if err != nil {
		return fmt.Errorf("error reaching proxy's health endpoint %s : %v", healthEndpoint, err)
	}
	if response == nil {
		return fmt.Errorf("error reaching proxy's health endpoint %s : response is nil", healthEndpoint)
	}
	if response.StatusCode != 200 {
		return fmt.Errorf("error reaching proxy's health endpoint %s : %+v", healthEndpoint, response)
	}
	return nil
}

// parseArgs parses and validates command line arguments
func parseArgs() (*RuntimeConfig, error) {
	config := NewRuntimeConfig()

	// Define command line flags
	flag.StringVar(&config.ProxyURL, "proxy", "", "URL of the SQS proxy (required)")
	flag.IntVar(&config.MaxMessages, "max-messages", 0, "Maximum number of messages to send (0 for unlimited)")
	flag.StringVar(&config.Color, "color", "#000000", "Color for the message (hex format) or -1 for random")
	flag.IntVar(&config.EmojiIdx, "emoji", -1, "Index of emoji to use (-1 for random)")
	flag.IntVar(&config.Interval, "interval", 5, "Interval between messages in seconds")
	flag.StringVar(&config.Region, "region", "", "Edge region (required)")
	
	// Parse submission time
	var submissionTimeUnix int64
	flag.Int64Var(&submissionTimeUnix, "submission-time", 0, "Job submission time (Unix timestamp)")
	
	flag.Parse()

	// Set submission time from Unix timestamp
	if submissionTimeUnix > 0 {
		config.SubmissionTime = time.Unix(submissionTimeUnix, 0)
	}

	// Normalize the configuration
	config.Normalize()

	// Validate the configuration
	if err := config.Validate(); err != nil {
		flag.Usage()
		return nil, err
	}

	return config, nil
}

// main is the entry point for the WebAssembly application
func main() {
	config, err := parseArgs()
	if err != nil {
		fmt.Printf("Error: %v\n", err)
		os.Exit(1)
	}

	publisher, err := NewPublisher(config)
	if err != nil {
		fmt.Printf("Error: %v\n", err)
		os.Exit(1)
	}

	if err := publisher.Run(); err != nil {
		fmt.Printf("Error: %v\n", err)
		os.Exit(1)
	}
}
