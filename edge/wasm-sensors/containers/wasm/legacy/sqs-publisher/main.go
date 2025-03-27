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

// PublisherParams holds the publisher configuration
type PublisherParams struct {
	ProxyURL             string
	MaxMessages          int
	ConfigPath           string
	RuntimeConfigWatcher *RuntimeConfigWatcher
}

// Publisher handles message publishing to the SQS proxy
type Publisher struct {
	params           PublisherParams
	client           *client.Client
	messageGenerator *MessageGenerator
	messageCount     int
	mu               sync.Mutex
}

// NewPublisher creates a new publisher instance
func NewPublisher(params PublisherParams) (*Publisher, error) {
	client := client.NewClient()
	if client == nil {
		return nil, fmt.Errorf("failed to create HTTP client")
	}

	return &Publisher{
		params:           params,
		client:           client,
		messageGenerator: NewMessageGenerator(),
	}, nil
}

// shouldContinue checks if we should continue sending messages
func (p *Publisher) shouldContinue() bool {
	p.mu.Lock()
	defer p.mu.Unlock()
	if p.params.MaxMessages > 0 && p.messageCount >= p.params.MaxMessages {
		fmt.Printf("Reached maximum message count (%d)\n", p.params.MaxMessages)
		return false
	}
	return true
}

// sendMessage sends a single message to the proxy
func (p *Publisher) sendMessage(config RuntimeConfig) error {
	p.mu.Lock()
	p.messageCount++
	count := p.messageCount
	p.mu.Unlock()

	message := p.messageGenerator.GetMessage(config)
	fmt.Printf("[%d] Sending message to %s\n", count, p.params.ProxyURL)

	// Marshal the message to JSON
	messageJSON, err := json.Marshal(message)
	if err != nil {
		return fmt.Errorf("error marshaling message: %v", err)
	}

	// Create a channel for the response
	done := make(chan error)
	go func() {
		headers := map[string][]string{"Content-Type": {"application/json"}}
		response, err := p.client.Post(p.params.ProxyURL+"/send", headers, string(messageJSON))
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

	initialConfig := p.params.RuntimeConfigWatcher.GetConfig()
	fmt.Printf("Starting publisher to %s with %d second interval and max-messages %d\n",
		p.params.ProxyURL, initialConfig.Interval, p.params.MaxMessages)

	for {
		config := p.params.RuntimeConfigWatcher.GetConfig()
		if !p.shouldContinue() {
			return nil
		}
		fmt.Printf("Attempting to send message...\n")
		if err := p.sendMessage(config); err != nil {
			fmt.Printf("Warning: %v\n", err)
		} else {
			fmt.Printf("Message sent successfully, sleeping for %d seconds...\n", config.Interval)
		}
		time.Sleep(time.Duration(config.Interval) * time.Second)
	}
}

func (p *Publisher) checkProxyHealth() error {
	// test we can reach the proxy by calling /health endpoint
	healthEndpoint := fmt.Sprintf("%s/health", p.params.ProxyURL)
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
func parseArgs() (*PublisherParams, error) {
	config := &PublisherParams{}

	// Define command line flags
	flag.StringVar(&config.ProxyURL, "proxy", "", "URL of the SQS proxy (required)")
	flag.IntVar(&config.MaxMessages, "max-messages", 0, "Maximum number of messages to send (0 for unlimited)")
	flag.StringVar(&config.ConfigPath, "config", "/app/config.yaml", "Path to the configuration file")
	flag.Parse()

	// Validate required flags
	if config.ProxyURL == "" {
		flag.Usage()
		return nil, fmt.Errorf("proxy URL is required")
	}

	if config.MaxMessages < 0 {
		flag.Usage()
		return nil, fmt.Errorf("max messages must be greater than or equal to 0")
	}

	// Create the runtime config watcher
	watcher, err := NewRuntimeConfigWatcher(config.ConfigPath)
	if err != nil {
		return nil, fmt.Errorf("failed to create runtime config watcher: %w", err)
	}
	config.RuntimeConfigWatcher = watcher

	return config, nil
}

// main is the entry point for the WebAssembly application
func main() {
	params, err := parseArgs()
	if err != nil {
		fmt.Printf("Error: %v\n", err)
		os.Exit(1)
	}

	publisher, err := NewPublisher(*params)
	if err != nil {
		fmt.Printf("Error: %v\n", err)
		os.Exit(1)
	}

	if err := publisher.Run(); err != nil {
		fmt.Printf("Error: %v\n", err)
		os.Exit(1)
	}
}
