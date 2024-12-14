package cmd

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"syscall"

	"github.com/docker/docker/api/types"
	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/api/types/network"
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

func Execute() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func init() {
	cobra.OnInitialize(initConfig)

	// Global flags
	rootCmd.PersistentFlags().StringVar(&cfgFile, "config", "", "config file (default is $HOME/.many-node-runner.yaml)")

	// Local flags
	rootCmd.Flags().Int("node-count", 3, "number of nodes to run")
	rootCmd.Flags().String("docker-image", "bacalhau-minimal", "docker image to use for nodes")
	rootCmd.Flags().String("network", "bacalhau-network", "docker network name")

	// Bind flags to viper
	viper.BindPFlag("node.count", rootCmd.Flags().Lookup("node-count"))
	viper.BindPFlag("docker.image", rootCmd.Flags().Lookup("image"))

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
	nodeCount := viper.GetInt("node.count")
	dockerImage := viper.GetString("docker.image")
	networkName := viper.GetString("docker.network")

	fmt.Printf("Starting %d nodes using image %s on network %s\n",
		nodeCount, dockerImage, networkName)

	ctx := context.Background()
	cli, err := client.NewClientWithOpts(client.FromEnv)
	if err != nil {
		return fmt.Errorf("failed to create Docker client: %w", err)
	}

	// Create network if it doesn't exist
	networks, err := cli.NetworkList(ctx, types.NetworkListOptions{})
	if err != nil {
		return fmt.Errorf("failed to list networks: %w", err)
	}

	networkExists := false
	for _, nw := range networks {
		if nw.Name == networkName {
			networkExists = true
			break
		}
	}

	if !networkExists {
		_, err = cli.NetworkCreate(ctx, networkName, types.NetworkCreate{})
		if err != nil {
			return fmt.Errorf("failed to create network: %w", err)
		}
		fmt.Printf("Created network: %s\n", networkName)
	}

	// Start containers
	containers := make([]string, nodeCount)
	for i := 0; i < nodeCount; i++ {
		containerName := fmt.Sprintf("bacalhau-node-%d", i)

		resp, err := cli.ContainerCreate(ctx,
			&container.Config{
				Image: dockerImage,
				Tty:   true,
			},
			&container.HostConfig{},
			&network.NetworkingConfig{
				EndpointsConfig: map[string]*network.EndpointSettings{
					networkName: {},
				},
			},
			nil,
			containerName,
		)
		if err != nil {
			return fmt.Errorf("failed to create container %s: %w", containerName, err)
		}

		containerStartOptions := container.StartOptions{}

		if err := cli.ContainerStart(ctx, resp.ID, containerStartOptions); err != nil {
			return fmt.Errorf("failed to start container %s: %w", containerName, err)
		}

		containers[i] = resp.ID
		fmt.Printf("Started container: %s (ID: %s)\n", containerName, resp.ID[:12])
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

		containerRemoveOptions := container.RemoveOptions{}
		containerRemoveOptions.Force = true
		if err := cli.ContainerRemove(ctx, containerID, containerRemoveOptions); err != nil {
			fmt.Printf("Warning: failed to remove container %s: %v\n", containerID[:12], err)
		}
	}

	fmt.Println("All containers stopped and removed")
	return nil
}
