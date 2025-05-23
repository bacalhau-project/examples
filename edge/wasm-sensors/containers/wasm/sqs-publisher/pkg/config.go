package pkg

import (
	"flag"
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

func ParseArgs() (*RuntimeConfig, error) {
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
	// For WebAssembly environments, we need a better random seed
	// Use a combination of values to get better entropy
	seed := time.Now().UnixNano()

	// Create a dedicated random generator for this configuration
	source := rand.NewSource(seed)
	rng := rand.New(source)

	// Handle color selection - once per config
	if c.Color == "-1" {
		// Generate random RGB values with our dedicated random source
		r := rng.Intn(256)
		g := rng.Intn(256)
		b := rng.Intn(256)
		c.Color = fmt.Sprintf("#%02x%02x%02x", r, g, b)
	}

	// Handle emoji selection - once per config
	if c.EmojiIdx < 0 || c.EmojiIdx >= len(supportedEmojis) {
		c.EmojiIdx = rng.Intn(len(supportedEmojis))
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
