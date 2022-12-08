package cmd

import (
	"os"

	"github.com/bacalhau-project/examples/tools/upload/config"
	"github.com/sirupsen/logrus"
	"github.com/spf13/cobra"
)

func NewRootCommand() *cobra.Command {
	var cmd = &cobra.Command{
		Use:   "upload",
		Short: "A tool to help uploading data to Filecoin via a Bacalhau job",
		PersistentPreRunE: func(cmd *cobra.Command, args []string) error {
			// You can bind cobra and viper in a few locations, but PersistencePreRunE on the root command works well
			return initializeConfig(cmd)
		},
		Run: func(cmd *cobra.Command, args []string) {
			// Command does nothing
			cmd.Help()
			os.Exit(1)
		},
	}

	// Add flags to the root command
	cmd = config.AddGlobalFlags(cmd)

	// Affix commands to the root command
	cmd.AddCommand(NewURLCommand())
	return cmd
}
func Execute() {
	cmd := NewRootCommand()
	if err := cmd.Execute(); err != nil {
		os.Exit(1)
	}
}

func initializeConfig(cmd *cobra.Command) error {
	// Parse final config for log level settings
	finalConfig := config.ParseGlobalConfig(cmd)

	// Set log level
	logrus.SetLevel(logrus.Level(finalConfig.LogLevel))

	return nil
}
