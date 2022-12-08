package config

import (
	"os"
	"path/filepath"

	"github.com/sirupsen/logrus"
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

func ParseGlobalConfig(cmd *cobra.Command) *GlobalConfig {
	number, err := cmd.Flags().GetInt(LogLevelFlag)
	if err != nil {
		logrus.Errorf("error parsing log level: %s", err)
		os.Exit(1)
	}
	return &GlobalConfig{
		LogLevel:   number,
		InputPath:  filepath.Clean(cmd.Flag(InputPathFlag).Value.String()),
		OutputPath: filepath.Clean(cmd.Flag(OutputPathFlag).Value.String()),
	}
}

func AddGlobalFlags(cmd *cobra.Command) *cobra.Command {
	cmd.PersistentFlags().IntP(LogLevelFlag, "l", 4, "Logging level (5=debug, 4=info, 3=warning, 2=error")
	cmd.PersistentFlags().StringP(InputPathFlag, "i", "/inputs", "Input path")
	cmd.PersistentFlags().StringP(OutputPathFlag, "o", "/outputs", "Output path")
	return cmd
}
