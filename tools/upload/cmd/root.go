package cmd

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/bacalhau-project/examples/tools/upload/config"
	"github.com/otiai10/copy"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
	"github.com/spf13/cobra"
)

func NewRootCommand() *cobra.Command {
	var cmd = &cobra.Command{
		Use:   "upload",
		Short: "A tool to help uploading data to Filecoin via a Bacalhau job",
		Long: `A tool to help uploading data to Filecoin via a Bacalhau job.

By default it will upload all files located in the /inputs directory 
to the /outputs directory. Bacalhau will then upload all of the files 
in the /outputs directory to Filecoin, via Estuary.`,
		PersistentPreRunE: func(cmd *cobra.Command, args []string) error {
			// You can bind cobra and viper in a few locations, but PersistencePreRunE on the root command works well
			return initializeConfig(cmd)
		},
		RunE: executeRootCommand,
	}

	// Add flags to the root command
	cmd = config.AddGlobalFlags(cmd)

	// Affix commands to the root command
	// TODO
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
	finalConfig, err := config.ParseGlobalConfig(cmd)
	if err != nil {
		return err
	}

	// Set global log level
	zerolog.SetGlobalLevel(zerolog.Level(finalConfig.LogLevel))
	log.Logger = log.Output(zerolog.ConsoleWriter{Out: os.Stdout})

	return nil
}

func executeRootCommand(cmd *cobra.Command, args []string) error {
	conf, err := config.ParseGlobalConfig(cmd)
	if err != nil {
		return fmt.Errorf("parsing config: %w", err)
	}

	log.Info().Str("InputPath", conf.InputPath).Str("OutputPath", conf.OutputPath).Msg("Copying files")

	allObjects := []string{}
	allDirs := []string{}
	allFiles := []string{}

	walker := func(path string, d os.DirEntry, err error) error {
		if path == conf.InputPath {
			return nil
		}
		if d.IsDir() {
			log.Debug().Str("path", path).Msg("Found directory")
			allDirs = append(allDirs, path)
		} else {
			log.Debug().Str("path", path).Msg("Found file")
			allFiles = append(allFiles, path)
		}

		return nil
	}

	log.Debug().Str("InputPath", conf.InputPath).Msg("Walking input path")
	err = filepath.WalkDir(conf.InputPath, walker)
	if err != nil {
		fmt.Errorf("Error walking input path: %w", err)
	}

	// Putting the objects in order so all Dirs come before all Files
	allObjects = append(allObjects, allDirs...)
	allObjects = append(allObjects, allFiles...)

	for _, oo := range allObjects {
		if oo == conf.InputPath {
			continue
		}

		// See if oo still exists (its parent could have been moved)
		_, err := os.Stat(oo)
		if err != nil {
			return fmt.Errorf("stating object: %w", err)
		}
		dstPath := strings.Replace(oo, conf.InputPath, conf.OutputPath, 1)
		log.Info().Str("src", oo).Str("dst", dstPath).Msg("Copying object")
		err = copy.Copy(oo, dstPath)
		if err != nil {
			return fmt.Errorf("copying object: %w", err)
		}
	}

	fileList := []string{}
	err = filepath.WalkDir(conf.OutputPath,
		func(path string, d os.DirEntry, err error) error {
			if path == conf.InputPath {
				return nil
			}
			fileList = append(fileList, path)
			return nil
		})
	if err != nil {
		return fmt.Errorf("walking output path: %w", err)
	}
	log.Info().Strs("files", fileList).Msg("Done copying all objects")
	return nil
}
