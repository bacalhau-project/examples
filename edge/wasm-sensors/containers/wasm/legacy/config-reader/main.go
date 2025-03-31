package main

import (
	"flag"
	"fmt"
	"os"
	"strings"
)

func main() {
	// Define command line flags
	configFile := flag.String("config", "/app/config.yaml", "Path to the configuration file")
	flag.Parse()

	// Read config file
	data, err := os.ReadFile(*configFile)
	if err != nil {
		fmt.Printf("Error reading config file: %v\n", err)
		os.Exit(1)
	}

	// Print raw content in a single line
	content := strings.ReplaceAll(string(data), "\n", " ")
	fmt.Println(content)
} 