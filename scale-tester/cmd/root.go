package cmd

import (
	"bufio"
	"context"
	"fmt"
	"os"
	"os/signal"
	"syscall"

	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/api/types/mount"
	"github.com/docker/docker/client"
	"github.com/spf13/cobra"
	"github.com/spf13/viper"
)

var (
	cfgFile string
	rootCmd = &cobra.Command{
		Use:   "many-node-runner",
		Short: "A tool for running multiple Bacalhau nodes",
		Long: `many-node-runner is a CLI tool that helps manage and run 
multiple Bacalhau nodes in a development or testing environment.`,
		RunE: runRoot,
	}
)

func Execute() error {
	return rootCmd.Execute()
}

func init() {
	cobra.OnInitialize(initConfig)

	// Global flags
	rootCmd.PersistentFlags().StringVar(&cfgFile, "config", "", "config file (default is $HOME/.many-node-runner.yaml)")

	// Local flags
	rootCmd.Flags().Int("node-count", 3, "number of nodes to run")
	rootCmd.Flags().String("image", "bacalhauproject/bacalhau-minimal", "docker image to use for nodes")
	rootCmd.Flags().String("bacalhau-config", "", "bacalhau config file to mount in containers")

	// Bind flags to viper
	viper.BindPFlag("node.count", rootCmd.Flags().Lookup("node-count"))
	viper.BindPFlag("docker.image", rootCmd.Flags().Lookup("image"))
	viper.BindPFlag("bacalhau.config", rootCmd.Flags().Lookup("bacalhau-config"))

	// Add validation
	rootCmd.PreRunE = func(cmd *cobra.Command, args []string) error {
		nodeCount := viper.GetInt("node.count")
		if nodeCount <= 0 {
			return fmt.Errorf("node count must be positive")
		}
		return nil
	}
}

func initConfig() {
	if cfgFile != "" {
		viper.SetConfigFile(cfgFile)
	} else {
		home, err := os.UserHomeDir()
		cobra.CheckErr(err)

		viper.AddConfigPath(home)
		viper.AddConfigPath(".")
		viper.SetConfigType("yaml")
		viper.SetConfigName(".many-node-runner")
	}

	viper.AutomaticEnv()

	if err := viper.ReadInConfig(); err == nil {
		fmt.Fprintln(os.Stderr, "Using config file:", viper.ConfigFileUsed())
	}
}

func runRoot(cmd *cobra.Command, args []string) error {
	nodeCount, err := cmd.Flags().GetInt("node-count")
	if err != nil {
		return fmt.Errorf("failed to get node count: %w", err)
	}

	dockerImage, err := cmd.Flags().GetString("image")
	if err != nil {
		return fmt.Errorf("failed to get docker image: %w", err)
	}

	bacalhauConfig, err := cmd.Flags().GetString("bacalhau-config")
	if err != nil || bacalhauConfig == "" {
		return fmt.Errorf("bacalhau config file must be specified")
	}

	if _, err := os.Stat(bacalhauConfig); os.IsNotExist(err) {
		return fmt.Errorf("bacalhau config file does not exist: %s", bacalhauConfig)
	}

	fmt.Printf("Starting %d nodes using image %s on host network with bacalhau config %s\n",
		nodeCount, dockerImage, bacalhauConfig)

	ctx := context.Background()
	cli, err := client.NewClientWithOpts(client.FromEnv)
	if err != nil {
		return fmt.Errorf("failed to create Docker client: %w", err)
	}

	// Start containers
	containers := make([]string, nodeCount)
	for i := 0; i < nodeCount; i++ {
		containerName := fmt.Sprintf("bacalhau-node-%d", i)
		apiPort := 1234 + i
		publisherPort := 6001 + i

		// Create mount for config file
		hostConfig := &container.HostConfig{
			NetworkMode: container.NetworkMode("host"),
			AutoRemove:  true,
			Mounts: []mount.Mount{
				{
					Type:   mount.TypeBind,
					Source: bacalhauConfig,
					Target: "/root/bacalhau-cloud-config.yaml",
				},
			},
		}

		resp, err := cli.ContainerCreate(ctx,
			&container.Config{
				Image:        dockerImage,
				Tty:          false,
				AttachStdout: true,
				AttachStderr: true,
				Env: []string{
					"BACALHAU_NODE_ID=" + containerName,
					fmt.Sprintf("BACALHAU_API_PORT=%d", apiPort),
					fmt.Sprintf("BACALHAU_PUBLISHER_PORT=%d", publisherPort),
				},
			},
			hostConfig,
			nil,
			nil,
			containerName,
		)
		if err != nil {
			return fmt.Errorf("failed to create container %s: %w", containerName, err)
		}

		// Start container
		if err := cli.ContainerStart(ctx, resp.ID, container.StartOptions{}); err != nil {
			return fmt.Errorf("failed to start container %s: %w", containerName, err)
		}

		containers[i] = resp.ID
		fmt.Printf("Started container: %s (ID: %s)\n", containerName, resp.ID[:12])

		// Stream logs in a goroutine
		go func(id, name string) {
			logOptions := container.LogsOptions{
				ShowStdout: true,
				ShowStderr: true,
				Follow:     true,
				Timestamps: true,
			}

			logs, err := cli.ContainerLogs(ctx, id, logOptions)
			if err != nil {
				fmt.Printf("Error getting logs for %s: %v\n", name, err)
				return
			}
			defer logs.Close()

			scanner := bufio.NewScanner(logs)
			for scanner.Scan() {
				fmt.Printf("[%s] %s\n", name, scanner.Text())
			}
			if err := scanner.Err(); err != nil {
				fmt.Printf("Error scanning logs for %s: %v\n", name, err)
			}
		}(resp.ID, containerName)
	}

	// Handle graceful shutdown
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	fmt.Println("\nPress Ctrl+C to stop the nodes...")
	<-sigChan

	fmt.Println("\nStopping containers...")
	for _, containerID := range containers {
		timeout := 0 // no timeout
		if err := cli.ContainerStop(ctx, containerID, container.StopOptions{Timeout: &timeout}); err != nil {
			fmt.Printf("Warning: failed to stop container %s: %v\n", containerID[:12], err)
		}
	}

	fmt.Println("All containers stopped")
	return nil
}
