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

func NewURLCommand() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "url",
		Short: "Downloads a file from a URL and uploads to Filecoin",
		Run:   executeURLCommand,
	}
	return cmd
}

func executeURLCommand(cmd *cobra.Command, args []string) {
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
