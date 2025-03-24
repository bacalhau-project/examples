// HTTP Test Module for Bacalhau
package main

import (
	crand "crypto/rand"
	"encoding/json"
	"fmt"
	mrand "math/rand"
	"os"
	"path/filepath"
	"time"

	"github.com/bacalhau-project/examples/utility_containers/event-pusher/internal/http"
	"github.com/bacalhau-project/examples/utility_containers/event-pusher/internal/messages"
	"github.com/bacalhau-project/examples/utility_containers/event-pusher/internal/utils"
	"gopkg.in/yaml.v3"
)

// Configuration for the application
type Config struct {
	// HTTP mode config
	Method  string `yaml:"method"`
	URL     string `yaml:"url"`
	Headers string `yaml:"headers"`
	Body    string `yaml:"body"`

	// Event pusher config
	Region      string `yaml:"region"`
	AccessKey   string `yaml:"access_key"`
	SecretKey   string `yaml:"secret_key"`
	QueueURL    string `yaml:"queue_url"`
	Color       string `yaml:"color"`
	MaxInterval int    `yaml:"max_interval_seconds"`
	RandomOff   bool   `yaml:"random_off"`
	MaxMessages int    `yaml:"max_messages"`
	Simulate    bool   `yaml:"simulate"`
	Mode        string `yaml:"mode"`
	VMName      string `yaml:"vm_name"`
}

// ConfigState tracks the current config and its last modification time
type ConfigState struct {
	Config      Config
	LastModTime time.Time
	ConfigPath  string
}

// loadConfig loads configuration from config.yaml file
// If configPath is provided (as in tests), it will load from that path
// Also supports environment variables for backward compatibility
func loadConfig(configPath ...string) Config {
	// Default configuration
	config := Config{
		// HTTP mode config
		Method: "GET",

		// Event pusher config
		Region:      "us-west-2",
		Color:       "#000000",
		MaxInterval: 5,
		Mode:        "auto",
		VMName:      "default",
	}

	// Determine which config path to use
	var configPaths []string
	if len(configPath) > 0 && configPath[0] != "" {
		// Use the provided path (useful for testing)
		configPaths = []string{configPath[0]}
	} else {
		// Look for config.yaml in the current directory, and if not found,
		// check in the directory where the executable is located
		configPaths = []string{
			"config.yaml",
			filepath.Join(filepath.Dir(os.Args[0]), "config.yaml"),
		}
	}

	var configData []byte
	var err error
	var loadedPath string
	var usingConfigFile bool

	for _, path := range configPaths {
		configData, err = os.ReadFile(path)
		if err == nil {
			loadedPath = path
			usingConfigFile = true
			break
		}
	}

	if err == nil {
		// Parse YAML configuration
		err = yaml.Unmarshal(configData, &config)
		if err != nil {
			fmt.Printf("Error parsing config.yaml: %v\n", err)
			fmt.Printf("Falling back to default configuration and environment variables.\n")
		} else {
			fmt.Printf("Configuration loaded from: %s\n", loadedPath)
		}
	} else {
		fmt.Printf("No config file found. Checking environment variables.\n")
		fmt.Printf("Tried paths: %v\n", configPaths)
	}

	// Check environment variables for backward compatibility
	// HTTP mode config
	if envVal := os.Getenv("HTTP_METHOD"); envVal != "" && !usingConfigFile {
		config.Method = envVal
		fmt.Println("Using HTTP_METHOD from environment variable")
	}
	if envVal := os.Getenv("HTTP_URL"); envVal != "" && !usingConfigFile {
		config.URL = envVal
		fmt.Println("Using HTTP_URL from environment variable")
	}
	if envVal := os.Getenv("HTTP_HEADERS"); envVal != "" && !usingConfigFile {
		config.Headers = envVal
		fmt.Println("Using HTTP_HEADERS from environment variable")
	}
	if envVal := os.Getenv("HTTP_BODY"); envVal != "" && !usingConfigFile {
		config.Body = envVal
		fmt.Println("Using HTTP_BODY from environment variable")
	}

	// Event pusher config
	if envVal := os.Getenv("AWS_REGION"); envVal != "" && !usingConfigFile {
		config.Region = envVal
		fmt.Println("Using AWS_REGION from environment variable")
	}
	if envVal := os.Getenv("AWS_ACCESS_KEY_ID"); envVal != "" && !usingConfigFile {
		config.AccessKey = envVal
		fmt.Println("Using AWS_ACCESS_KEY_ID from environment variable")
	}
	if envVal := os.Getenv("AWS_SECRET_ACCESS_KEY"); envVal != "" && !usingConfigFile {
		config.SecretKey = envVal
		fmt.Println("Using AWS_SECRET_ACCESS_KEY from environment variable")
	}
	if envVal := os.Getenv("SQS_QUEUE_URL"); envVal != "" && !usingConfigFile {
		config.QueueURL = envVal
		fmt.Println("Using SQS_QUEUE_URL from environment variable")
	}
	if envVal := os.Getenv("COLOR"); envVal != "" && !usingConfigFile {
		config.Color = envVal
		fmt.Println("Using COLOR from environment variable")
	}
	if envVal := os.Getenv("VM_NAME"); envVal != "" {
		config.VMName = envVal
	} else {
		// Generate a random 6-character hex string for the VM name
		hexBytes := make([]byte, 3)
		crand.Read(hexBytes)
		config.VMName = fmt.Sprintf("vm-%x", hexBytes)
	}
	if envVal := os.Getenv("MODE"); envVal != "" && !usingConfigFile {
		config.Mode = envVal
		fmt.Println("Using MODE from environment variable")
	}
	if envVal := os.Getenv("MAX_INTERVAL_SECONDS"); envVal != "" && !usingConfigFile {
		fmt.Sscanf(envVal, "%d", &config.MaxInterval)
		fmt.Println("Using MAX_INTERVAL_SECONDS from environment variable")
	}
	if envVal := os.Getenv("MAX_MESSAGES"); envVal != "" && !usingConfigFile {
		fmt.Sscanf(envVal, "%d", &config.MaxMessages)
		fmt.Println("Using MAX_MESSAGES from environment variable")
	}
	if envVal := os.Getenv("RANDOM_OFF"); envVal != "" && !usingConfigFile {
		config.RandomOff = utils.ParseBool(envVal)
		fmt.Println("Using RANDOM_OFF from environment variable")
	}
	if envVal := os.Getenv("SIMULATE"); envVal != "" && !usingConfigFile {
		config.Simulate = utils.ParseBool(envVal)
		fmt.Println("Using SIMULATE from environment variable")
	}

	// Validate and set defaults for numeric values
	if config.MaxInterval < 1 {
		config.MaxInterval = 5
	}

	return config
}

// loadConfigState loads or updates the configuration state
func loadConfigState(state *ConfigState) error {
	// Get current file info
	fileInfo, err := os.Stat(state.ConfigPath)
	if err != nil {
		return fmt.Errorf("error checking config file: %v", err)
	}

	// If this is the first load or the file has been modified
	if state.LastModTime.IsZero() || fileInfo.ModTime().After(state.LastModTime) {
		// Load new config
		config := loadConfig(state.ConfigPath)
		state.Config = config
		state.LastModTime = fileInfo.ModTime()
		fmt.Println("Configuration reloaded from file")
	}

	return nil
}

// These functions are now implemented in internal/utils
// Using utils package functions instead

// runHTTPMode executes a single HTTP request
func runHTTPMode(config Config) error {
	// Validate URL
	if config.URL == "" {
		return fmt.Errorf("HTTP_URL environment variable is required")
	}

	// Create HTTP client
	httpClient := http.New()

	// Convert method string to constant
	methodCode, err := httpClient.GetMethodConstant(config.Method)
	if err != nil {
		return err
	}

	// Parse headers
	headers := utils.ParseHeaders(config.Headers)

	// Make the request
	fmt.Printf("Making %s request to %s\n", config.Method, config.URL)
	response, err := httpClient.Request(methodCode, config.URL, headers, config.Body)
	if err != nil {
		return fmt.Errorf("error making request: %v", err)
	}

	// Print response
	fmt.Printf("Status Code: %d\n", response.StatusCode)
	fmt.Println("Headers:")
	for key, values := range response.Headers {
		for _, value := range values {
			fmt.Printf("%s: %s\n", key, value)
		}
	}
	fmt.Printf("\nBody:\n%s\n", response.Body)

	return nil
}

// This function is now implemented in internal/utils
// Using utils.ParseHeaders instead

// runEventPusherMode sends events to SQS queue
func runEventPusherMode(config Config) error {
	// Validate required environment variables (if not in simulate mode)
	if !config.Simulate && (config.AccessKey == "" || config.SecretKey == "" || config.QueueURL == "") {
		return fmt.Errorf("missing required environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, SQS_QUEUE_URL")
	}

	// Validate color format
	if !messages.IsValidHexColor(config.Color) {
		return fmt.Errorf("invalid color format. Must be a 6-digit hex code with leading #")
	}

	fmt.Println("Event pusher started")
	if config.Simulate {
		fmt.Println("Running in SIMULATION mode (no actual SQS messages will be sent)")
	} else {
		fmt.Printf("Pushing events to SQS queue: %s\n", config.QueueURL)
	}

	if config.RandomOff {
		fmt.Printf("Randomization: OFF (fixed interval of %d seconds)\n", config.MaxInterval)
	} else {
		fmt.Printf("Randomization: ON (random interval between 0.1 and %d seconds)\n", config.MaxInterval)
	}

	if config.MaxMessages > 0 {
		fmt.Printf("Will send %d messages and then exit\n", config.MaxMessages)
	} else {
		fmt.Println("Will send messages indefinitely until stopped")
	}

	// Create message generator
	generator := messages.NewDefaultGenerator()

	// Initialize config state
	configState := &ConfigState{
		Config:     config,
		ConfigPath: "config.yaml", // Default config path
	}

	// Create SQS sender with initial config
	sqsConfig := messages.SQSConfig{
		Region:    config.Region,
		AccessKey: config.AccessKey,
		SecretKey: config.SecretKey,
		QueueURL:  config.QueueURL,
		Simulate:  config.Simulate,
	}
	sender := messages.NewSQSSender(sqsConfig)

	messageCount := 0
	for {
		// Check and reload config if needed
		if err := loadConfigState(configState); err != nil {
			fmt.Printf("Warning: Error checking config: %v\n", err)
		} else {
			// Update SQS sender with new config if needed
			sender.UpdateConfig(messages.SQSConfig{
				Region:    configState.Config.Region,
				AccessKey: configState.Config.AccessKey,
				SecretKey: configState.Config.SecretKey,
				QueueURL:  configState.Config.QueueURL,
				Simulate:  configState.Config.Simulate,
			})
		}

		// Create message with current config
		message := messages.Message{
			VMName:      configState.Config.VMName,
			IconName:    generator.GetRandomIcon(configState.Config.RandomOff),
			Timestamp:   generator.GetCurrentTimestamp(),
			Color:       configState.Config.Color,
			ContainerID: generator.GenerateContainerID(configState.Config.RandomOff),
		}

		// Send to SQS
		err := sender.SendMessage(message)
		if err != nil {
			fmt.Printf("❌ Error sending message: %v\n", err)
		} else {
			messageCount++
			messageJSON, _ := json.Marshal(message)
			fmt.Printf("✅ Successfully sent message %d: %s\n", messageCount, string(messageJSON))
		}

		// Check if we've reached the maximum number of messages
		if configState.Config.MaxMessages > 0 && messageCount >= configState.Config.MaxMessages {
			fmt.Printf("Sent %d messages. Exiting.\n", messageCount)
			break
		}

		// Calculate sleep duration based on randomization settings
		var sleepDuration time.Duration
		if configState.Config.RandomOff {
			// Fixed interval when randomness is off
			sleepDuration = time.Duration(configState.Config.MaxInterval) * time.Second
		} else {
			// Random interval between 0.1 and max_interval_seconds
			minDuration := 100 * time.Millisecond // 0.1 seconds
			maxDuration := time.Duration(configState.Config.MaxInterval) * time.Second

			// Calculate random duration between min and max
			randomMillis := mrand.Int63n(int64(maxDuration-minDuration)) + int64(minDuration)
			sleepDuration = time.Duration(randomMillis)
		}

		// Sleep before next message
		time.Sleep(sleepDuration)
	}

	return nil
}

// This function is now implemented in internal/utils
// Using utils.DetectModeFromEnv instead

// Run the application with the given configuration
func Run(config Config) error {
	// Determine mode to run in
	mode := config.Mode
	if mode == "auto" {
		mode = utils.DetectModeFromConfig(config.URL, config.QueueURL, config.Simulate)
	}

	// Execute the appropriate mode
	switch mode {
	case "http":
		return runHTTPMode(config)
	case "event-pusher":
		return runEventPusherMode(config)
	default:
		return fmt.Errorf("unknown mode: %s", mode)
	}
}

// main is the entry point for the WebAssembly application
func main() {
	// Load configuration
	config := loadConfig()

	// Run the application
	err := Run(config)
	if err != nil {
		fmt.Printf("Error: %v\n", err)
		os.Exit(1)
	}

	os.Exit(0)
}
