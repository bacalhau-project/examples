package cmd

import (
	"os"
	"path/filepath"
	"strings"

	"github.com/bacalhau-project/examples/tools/upload/config"
	"github.com/otiai10/copy"
	"github.com/sirupsen/logrus"
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
		Run: executeRootCommand,
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
	finalConfig := config.ParseGlobalConfig(cmd)

	// Set log level
	logrus.SetLevel(logrus.Level(finalConfig.LogLevel))

	return nil
}

func executeRootCommand(cmd *cobra.Command, args []string) {
	conf := config.ParseGlobalConfig(cmd)
	logrus.Infof("Copying %s to %s", conf.InputPath, conf.OutputPath)

	allObjects := []string{}
	allDirs := []string{}
	allFiles := []string{}

	walker := func(path string, d os.DirEntry, err error) error {
		if path == conf.InputPath {
			return nil
		}
		if d.IsDir() {
			logrus.Debugf("Found directory: %s\n", path)
			allDirs = append(allDirs, path)
		} else {
			logrus.Debugf("Found file: %s\n", path)
			allFiles = append(allFiles, path)
		}

		return nil
	}

	logrus.Debugf("Walking input path: %s\n", conf.InputPath)
	err := filepath.WalkDir(conf.InputPath, walker)
	if err != nil {
		logrus.Errorf("Error walking input path: %v", err)
		return
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
			logrus.Errorf("Error stating object %v:", err)
			continue
		}
		logrus.Debugf("Destination path calculation %s from %s to %s\n", oo, conf.InputPath, conf.OutputPath)
		dstPath := strings.Replace(oo, conf.InputPath, conf.OutputPath, 1)
		logrus.Infof("Copying %s to %s\n", oo, dstPath)
		err = copy.Copy(oo, dstPath)
		if err != nil {
			logrus.Errorf("Error moving %s to %s: %v", oo, dstPath, err)
			return
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
		logrus.Errorf("Error walking output path: %v", err)
	}
	logrus.Infof("Done copying all objects. Final contents: %s\n", fileList)
}
