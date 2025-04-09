package pkg

import (
	"flag"
	"os"
	"strings"
	"testing"
	"time"
)

func TestParseArgs(t *testing.T) {
	// Save original command-line arguments and flags
	originalArgs := os.Args
	originalFlagCommandLine := flag.CommandLine
	defer func() {
		os.Args = originalArgs
		flag.CommandLine = originalFlagCommandLine
	}()

	tests := []struct {
		name      string
		args      []string
		wantError bool
		check     func(*RuntimeConfig) bool
		errMsg    string
	}{
		{
			name: "Valid arguments",
			args: []string{"cmd", "-proxy", "http://example.com", "-region", "us-west-1",
				"-max-messages", "10", "-color", "#123abc", "-emoji", "5", "-interval", "3"},
			wantError: false,
			check: func(c *RuntimeConfig) bool {
				return c.ProxyURL == "http://example.com" &&
					c.Region == "us-west-1" &&
					c.MaxMessages == 10 &&
					c.Color == "#123abc" &&
					c.EmojiIdx == 5 &&
					c.Interval == 3
			},
		},
		{
			name:      "Missing proxy URL",
			args:      []string{"cmd", "-region", "us-west-1"},
			wantError: true,
			errMsg:    "proxy URL is required",
		},
		{
			name:      "Missing region",
			args:      []string{"cmd", "-proxy", "http://example.com"},
			wantError: true,
			errMsg:    "edge region is required",
		},
		{
			name:      "Random emoji",
			args:      []string{"cmd", "-proxy", "http://example.com", "-region", "us-west-1", "-emoji", "-1"},
			wantError: false,
			check: func(c *RuntimeConfig) bool {
				return c.EmojiIdx >= 0 && c.EmojiIdx < len(supportedEmojis)
			},
		},
		{
			name:      "Random color",
			args:      []string{"cmd", "-proxy", "http://example.com", "-region", "us-west-1", "-color", "-1"},
			wantError: false,
			check: func(c *RuntimeConfig) bool {
				return isValidHexColor(c.Color)
			},
		},
		{
			name:      "Custom submission time",
			args:      []string{"cmd", "-proxy", "http://example.com", "-region", "us-west-1", "-submission-time", "1617234567"},
			wantError: false,
			check: func(c *RuntimeConfig) bool {
				expectedTime := time.Unix(1617234567, 0)
				return c.SubmissionTime.Equal(expectedTime)
			},
		},
		{
			name:      "Negative interval",
			args:      []string{"cmd", "-proxy", "http://example.com", "-region", "us-west-1", "-interval", "-5"},
			wantError: true,
			errMsg:    "interval must be greater than 0",
		},
		{
			name:      "Invalid color format",
			args:      []string{"cmd", "-proxy", "http://example.com", "-region", "us-west-1", "-color", "FF00FF"},
			wantError: true,
			errMsg:    "invalid hex color code",
		},
		{
			name:      "Negative max messages",
			args:      []string{"cmd", "-proxy", "http://example.com", "-region", "us-west-1", "-max-messages", "-10"},
			wantError: true,
			errMsg:    "max messages must be greater than or equal to 0",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Reset flags for each test
			flag.CommandLine = flag.NewFlagSet(os.Args[0], flag.ExitOnError)
			os.Args = tt.args

			// Call the function
			config, err := ParseArgs()

			// Check error status
			if (err != nil) != tt.wantError {
				t.Errorf("ParseArgs() error = %v, wantError %v", err, tt.wantError)
				return
			}

			// Check error message if applicable
			if tt.wantError && err != nil && tt.errMsg != "" && !strings.Contains(err.Error(), tt.errMsg) {
				t.Errorf("ParseArgs() error = %v, want error containing %v", err, tt.errMsg)
				return
			}

			// Check the resulting config if no error
			if !tt.wantError && tt.check != nil && !tt.check(config) {
				t.Errorf("ParseArgs() produced config that failed validation: %+v", config)
			}
		})
	}
}

// Test that random emoji selection works consistently across multiple runs
func TestRandomEmojiSelection(t *testing.T) {
	// Save original command-line arguments and flags
	originalArgs := os.Args
	originalFlagCommandLine := flag.CommandLine
	defer func() {
		os.Args = originalArgs
		flag.CommandLine = originalFlagCommandLine
	}()

	// Map to track emoji indices chosen
	results := make(map[int]int)
	iterations := 10

	// Standard args for testing random emoji selection
	args := []string{"cmd", "-proxy", "http://example.com", "-region", "us-west-1", "-emoji", "-1"}

	for i := 0; i < iterations; i++ {
		// Reset flag parsing for each iteration
		flag.CommandLine = flag.NewFlagSet(os.Args[0], flag.ExitOnError)
		os.Args = args

		// Call ParseArgs to get a config with random emoji
		config, err := ParseArgs()
		if err != nil {
			t.Fatalf("ParseArgs() failed: %v", err)
		}

		// Track which emoji was selected
		results[config.EmojiIdx]++

		t.Logf("Iteration %d: Selected emoji index %d (%s)",
			i, config.EmojiIdx, supportedEmojis[config.EmojiIdx])
	}

	// Check if we got a reasonable distribution of emojis
	uniqueCount := len(results)
	t.Logf("Selected %d unique emojis out of %d iterations", uniqueCount, iterations)

	// With 10 iterations, we should get at least 3 different emojis
	// (this is a relatively loose requirement to prevent flaky tests)
	if uniqueCount < 3 {
		t.Errorf("Poor randomization: only %d different emojis in %d iterations",
			uniqueCount, iterations)
	}
}

// TestBenchmarkRandomization tests how quickly time changes in the WebAssembly environment
func TestTimeAdvancement(t *testing.T) {
	// Check if time is advancing properly in this environment
	times := make([]int64, 5)

	for i := 0; i < 5; i++ {
		times[i] = time.Now().UnixNano()
		if i > 0 {
			delta := times[i] - times[i-1]
			t.Logf("Time delta %d: %d nanoseconds", i, delta)
		}
		time.Sleep(1 * time.Millisecond)
	}

	// Check if time advanced at all
	if times[4] == times[0] {
		t.Errorf("Time did not advance at all over 5 measurements")
	}
}

// TestSimpleValidation tests basic config validation functions
func TestSimpleValidation(t *testing.T) {
	// Test isValidHexColor
	validColors := []string{"#000000", "#FFFFFF", "#123abc", "#123ABC"}
	invalidColors := []string{"#000", "000000", "#12345z", "#12345", "#1234567"}

	for _, color := range validColors {
		if !isValidHexColor(color) {
			t.Errorf("isValidHexColor(%s) should return true", color)
		}
	}

	for _, color := range invalidColors {
		if isValidHexColor(color) {
			t.Errorf("isValidHexColor(%s) should return false", color)
		}
	}

	// Test default config values
	config := NewRuntimeConfig()
	if config.MaxMessages != 0 || config.Color != "#000000" || config.EmojiIdx != -1 || config.Interval != 5 {
		t.Errorf("NewRuntimeConfig() returned unexpected values: %+v", config)
	}
}
