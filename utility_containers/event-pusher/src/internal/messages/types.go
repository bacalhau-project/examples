// Package messages provides structures and functions for event messaging
package messages

import (
	"math/rand"
	"time"
)

// Initialize random seed
func init() {
	rand.Seed(time.Now().UnixNano())
}

// Message structure for events
type Message struct {
	VMName      string `json:"vm_name"`
	IconName    string `json:"icon_name"`
	Timestamp   string `json:"timestamp"`
	Color       string `json:"color"`
	ContainerID string `json:"container_id"`
}

// DefaultEmojis returns the standard set of emojis used for events
func DefaultEmojis() []string {
	return []string{
		"🚀", "💻", "🖥️", "💾", "📡", "🌐", "🔌", "⚡", "🔋", "💡",
		"🛠️", "🔧", "⚙️", "🔨", "📱", "📲", "🖱️", "⌨️", "🖨️", "🧮",
		"🎮", "🎲", "🎯", "🎪", "🎭", "🎨", "🧩", "🎸", "🎹", "🎺",
	}
}

// IsValidHexColor checks if the given string is a valid hex color code
func IsValidHexColor(color string) bool {
	if len(color) != 7 || color[0] != '#' {
		return false
	}
	for i := 1; i < 7; i++ {
		c := color[i]
		if !((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F')) {
			return false
		}
	}
	return true
}

// Generator provides methods for generating message components
type Generator interface {
	// GenerateContainerID creates a container ID
	GenerateContainerID(randomOff bool) string
	// GetRandomIcon selects an emoji from the list
	GetRandomIcon(randomOff bool) string
	// GetCurrentTimestamp returns the current time in ISO format
	GetCurrentTimestamp() string
}

// DefaultGenerator is the standard implementation of Generator
type DefaultGenerator struct {
	Emojis []string
}

// NewDefaultGenerator creates a new DefaultGenerator with default emojis
func NewDefaultGenerator() *DefaultGenerator {
	return &DefaultGenerator{
		Emojis: DefaultEmojis(),
	}
}

// GenerateContainerID creates a container ID (random or fixed based on randomOff)
func (g *DefaultGenerator) GenerateContainerID(randomOff bool) string {
	const chars = "0123456789abcdef"
	result := make([]byte, 8)

	if randomOff {
		// Use a fixed pattern when randomness is off
		for i := range result {
			result[i] = chars[i%len(chars)]
		}
	} else {
		// Use deterministic pattern for testing
		for i := range result {
			result[i] = chars[(i+5)%len(chars)]
		}
	}

	return string(result)
}

// GetRandomIcon selects an emoji from the list (random or fixed based on randomOff)
func (g *DefaultGenerator) GetRandomIcon(randomOff bool) string {
	emojis := g.Emojis
	if len(emojis) == 0 {
		emojis = DefaultEmojis()
	}

	if randomOff {
		// Always return the first emoji when randomness is off
		return emojis[0]
	}

	// Use true random selection when randomOff is false
	return emojis[rand.Intn(len(emojis))]
}

// GetCurrentTimestamp returns the current time in ISO format
func (g *DefaultGenerator) GetCurrentTimestamp() string {
	return time.Now().UTC().Format(time.RFC3339)
}
