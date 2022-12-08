package config

import (
	"fmt"
	"path/filepath"

	"github.com/spf13/cobra"
)

// Define all global flag names
const (
	LogLevelFlag   = "log-level"
	InputPathFlag  = "input"
	OutputPathFlag = "output"
)

type GlobalConfig struct {
	LogLevel   int    `yaml:"log-level"`
	InputPath  string `yaml:"input-path"`
	OutputPath string `yaml:"output-path"`
}

func ParseGlobalConfig(cmd *cobra.Command) (*GlobalConfig, error) {
	number, err := cmd.Flags().GetInt(LogLevelFlag)
	if err != nil {
		return nil, fmt.Errorf("parsing log level: %w", err)
	}
	return &GlobalConfig{
		LogLevel:   number,
		InputPath:  filepath.Clean(cmd.Flag(InputPathFlag).Value.String()),
		OutputPath: filepath.Clean(cmd.Flag(OutputPathFlag).Value.String()),
	}, nil
}

func AddGlobalFlags(cmd *cobra.Command) *cobra.Command {
	cmd.PersistentFlags().IntP(LogLevelFlag, "l", 1, "Logging level (-1= trace, 0=debug, 1=info, 2=warning, 3=error, ...")
	cmd.PersistentFlags().StringP(InputPathFlag, "i", "/inputs", "Input path")
	cmd.PersistentFlags().StringP(OutputPathFlag, "o", "/outputs", "Output path")
	return cmd
}
