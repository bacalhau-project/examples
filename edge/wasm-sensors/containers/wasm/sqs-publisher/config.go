package main

import (
	"fmt"
	"math/rand"
	"time"
)

// RuntimeConfig holds the runtime configuration
type RuntimeConfig struct {
	ProxyURL       string
	MaxMessages    int
	Color          string
	EmojiIdx       int
	Interval       int
	Region         string
	SubmissionTime time.Time
}

// Supported emojis
var supportedEmojis = []string{
	"🚀", "📡", "💡", "⚡", "🔋", "🛠️", "⚙️", "📱", "🖱️", "⌨️",
	"🎮", "🎲", "🎯", "🎪", "🎭", "🎨", "🧩", "🎸", "🎹", "🎺",
}

// NewRuntimeConfig creates a new RuntimeConfig with default values
func NewRuntimeConfig() *RuntimeConfig {
	return &RuntimeConfig{
		MaxMessages:    0,
		Color:          "#000000",
		EmojiIdx:       -1,
		Interval:       5,
		SubmissionTime: time.Now(),
	}
}

// Normalize sets default values and normalizes the configuration
func (c *RuntimeConfig) Normalize() {
	// Handle color selection
	if c.Color == "-1" {
		c.Color = generateRandomColor()
	}

	// Handle emoji selection
	if c.EmojiIdx < 0 || c.EmojiIdx >= len(supportedEmojis) {
		c.EmojiIdx = rand.Intn(len(supportedEmojis))
	}
}

// Validate checks if the configuration is valid
func (c *RuntimeConfig) Validate() error {
	// Validate required fields
	if c.ProxyURL == "" {
		return fmt.Errorf("proxy URL is required")
	}
	if c.Region == "" {
		return fmt.Errorf("edge region is required")
	}

	// Validate numeric fields
	if c.MaxMessages < 0 {
		return fmt.Errorf("max messages must be greater than or equal to 0")
	}
	if c.Interval <= 0 {
		return fmt.Errorf("interval must be greater than 0")
	}

	// Validate color format
	if !isValidHexColor(c.Color) {
		return fmt.Errorf("invalid hex color code '%s'", c.Color)
	}

	return nil
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

// generateRandomColor generates a random hex color code
func generateRandomColor() string {
	// Generate random RGB values
	r := rand.Intn(256)
	g := rand.Intn(256)
	b := rand.Intn(256)
	return fmt.Sprintf("#%02x%02x%02x", r, g, b)
}
