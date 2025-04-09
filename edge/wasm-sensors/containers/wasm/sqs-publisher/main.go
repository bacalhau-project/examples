package main

import (
	"fmt"
	"os"
	"sqs-publisher/pkg"
	"time"
)

const (
	// MessageSendTimeout is the maximum time allowed for sending a message
	MessageSendTimeout = 5 * time.Second
)

// main is the entry point for the WebAssembly application
func main() {
	config, err := pkg.ParseArgs()
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
