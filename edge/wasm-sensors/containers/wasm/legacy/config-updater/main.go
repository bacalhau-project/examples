package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"gopkg.in/yaml.v3"
)

type RuntimeConfig struct {
	Color     *string `yaml:"color,omitempty"`
	RandomOff *bool   `yaml:"randomOff,omitempty"`
	Interval  *int    `yaml:"interval,omitempty"`
}

func main() {
	// Define command line flags without defaults
	configFile := flag.String("config", "config.yaml", "Path to the configuration file")
	color := flag.String("color", "", "Hex color code (e.g., #FF0000)")
	randomOff := flag.Bool("random-off", false, "Whether to disable random color generation")
	interval := flag.Int("interval", 0, "Interval in seconds between updates")
	flag.Parse()

	// Create config directory if it doesn't exist
	configDir := filepath.Dir(*configFile)
	if configDir != "." {
		if err := os.MkdirAll(configDir, 0755); err != nil {
			fmt.Printf("Error creating config directory: %v\n", err)
			os.Exit(1)
		}
	}

	// Create empty file if it doesn't exist
	if _, err := os.Stat(*configFile); os.IsNotExist(err) {
		// Create an empty config
		emptyConfig := RuntimeConfig{}
		data, err := yaml.Marshal(emptyConfig)
		if err != nil {
			fmt.Printf("Error creating empty config: %v\n", err)
			os.Exit(1)
		}
		if err := os.WriteFile(*configFile, data, 0644); err != nil {
			fmt.Printf("Error creating config file: %v\n", err)
			os.Exit(1)
		}
	}

	// Read existing config if file exists
	var config RuntimeConfig
	if _, err := os.Stat(*configFile); err == nil {
		data, err := os.ReadFile(*configFile)
		if err != nil {
			fmt.Printf("Error reading config file: %v\n", err)
			os.Exit(1)
		}
		if err := yaml.Unmarshal(data, &config); err != nil {
			fmt.Printf("Error parsing config file: %v\n", err)
			os.Exit(1)
		}
	}

	// Update only the fields that were explicitly set
	if flag.Lookup("color").Value.String() != "" {
		if !isValidHexColor(*color) {
			fmt.Printf("Error: invalid color format '%s'. Must be a hex color code (e.g., #FF0000)\n", *color)
			os.Exit(1)
		}
		config.Color = color
	}

	if flag.Lookup("interval").Value.String() != "0" {
		if *interval <= 0 {
			fmt.Println("Error: interval must be greater than 0")
			os.Exit(1)
		}
		config.Interval = interval
	}

	config.RandomOff = randomOff

	// Marshal to YAML
	data, err := yaml.Marshal(config)
	if err != nil {
		fmt.Printf("Error marshaling config: %v\n", err)
		os.Exit(1)
	}

	// Write to file
	err = os.WriteFile(*configFile, data, 0644)
	if err != nil {
		fmt.Printf("Error writing config file: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("Successfully updated config file: %s\n", *configFile)
}

func isValidHexColor(color string) bool {
	if len(color) != 7 || color[0] != '#' {
		return false
	}
	for i := 1; i < 7; i++ {
		if !((color[i] >= '0' && color[i] <= '9') || (color[i] >= 'a' && color[i] <= 'f') || (color[i] >= 'A' && color[i] <= 'F')) {
			return false
		}
	}
	return true
}
