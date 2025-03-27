package main

import (
	"fmt"
	"os"
	"sync"
	"time"

	"gopkg.in/yaml.v3"
)

type RuntimeConfig struct {
	Color     string
	RandomOff bool
	Interval  int
}

// RuntimeConfigWatcher handles loading and watching configuration changes
type RuntimeConfigWatcher struct {
	config     RuntimeConfig
	configPath string
	mu         sync.RWMutex
	stopChan   chan struct{}
}

// NewRuntimeConfigWatcher creates a new runtime config watcher instance
func NewRuntimeConfigWatcher(configPath string) (*RuntimeConfigWatcher, error) {
	cm := &RuntimeConfigWatcher{
		configPath: configPath,
		stopChan:   make(chan struct{}),
	}

	// Set default values from environment variables or use hardcoded defaults
	defaultColor := os.Getenv("DEFAULT_COLOR")
	if defaultColor == "" {
		defaultColor = "#000000"
	}

	defaultInterval := 5
	if interval := os.Getenv("DEFAULT_INTERVAL"); interval != "" {
		if intervalVal, err := fmt.Sscanf(interval, "%d", &defaultInterval); err == nil && intervalVal > 0 {
			defaultInterval = intervalVal
		}
	}

	defaultRandomOff := false
	if randomOff := os.Getenv("DEFAULT_RANDOM_OFF"); randomOff != "" {
		defaultRandomOff = randomOff == "true" || randomOff == "1"
	}

	cm.config = RuntimeConfig{
		Color:     defaultColor,
		RandomOff: defaultRandomOff,
		Interval:  defaultInterval,
	}

	// Load initial config
	cm.loadConfig()

	// Start watching for config changes
	go cm.watchConfig()

	return cm, nil
}

// GetConfig returns the current configuration
func (cm *RuntimeConfigWatcher) GetConfig() RuntimeConfig {
	cm.mu.RLock()
	defer cm.mu.RUnlock()
	return cm.config
}

// isValidHexColor checks if a string is a valid hex color code
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

// loadConfig loads configuration from file and returns true if a new configuration was loaded
func (cm *RuntimeConfigWatcher) loadConfig() bool {
	cm.mu.Lock()
	defer cm.mu.Unlock()

	// Try to load from config file if it exists
	if _, err := os.Stat(cm.configPath); err == nil {
		data, err := os.ReadFile(cm.configPath)
		if err != nil {
			fmt.Printf("Warning: Failed to read config file: %v, keeping previous configuration\n", err)
			return false
		}

		var fileConfig RuntimeConfig
		if err := yaml.Unmarshal(data, &fileConfig); err != nil {
			fmt.Printf("Warning: Failed to parse config file: %v, keeping previous configuration\n", err)
			return false
		}

		// Merge file config with defaults
		if fileConfig.Color != "" {
			if !isValidHexColor(fileConfig.Color) {
				fmt.Printf("Warning: Invalid hex color code '%s', keeping previous color\n", fileConfig.Color)
				return false
			}
			cm.config.Color = fileConfig.Color
		}
		if fileConfig.Interval > 0 {
			cm.config.Interval = fileConfig.Interval
		}
		cm.config.RandomOff = fileConfig.RandomOff
		return true
	} else {
		// File doesn't exist, keep previous configuration
		fmt.Printf("Warning: Config file %s does not exist, keeping previous configuration\n", cm.configPath)
		return false
	}
}

// watchConfig continuously monitors the config file for changes
func (cm *RuntimeConfigWatcher) watchConfig() {
	ticker := time.NewTicker(1 * time.Second)
	defer ticker.Stop()

	var lastModTime time.Time
	if info, err := os.Stat(cm.configPath); err == nil {
		lastModTime = info.ModTime()
	}

	for {
		select {
		case <-cm.stopChan:
			return
		case <-ticker.C:
			info, err := os.Stat(cm.configPath)
			if err != nil {
				continue
			}

			if info.ModTime().After(lastModTime) {
				if cm.loadConfig() {
					fmt.Printf("Config reloaded successfully\n")
				}
				lastModTime = info.ModTime()
			}
		}
	}
}

// Stop stops the runtime config watcher
func (cm *RuntimeConfigWatcher) Stop() {
	close(cm.stopChan)
}
