# Bacalhau Shared Files Security Explorer

This project demonstrates how to explore the functionality of Bacalhau for shared files with security features. It includes a set of Python scripts and Bacalhau job configurations to help you understand and test various aspects of file sharing and security in a Bacalhau environment.

## Common Security Issues Today

One of the biggest challenges with particularly large data sources today is that the ability to interact with the data, even in a lightweight way, can result in significant security or bandwidth concerns. Ideally, there would be a way to provide a way for folks to interact from all over the world, without requiring significant increased exposure. That's what this solution provides.

## Directory Structure

- `scripts/`: Contains Python scripts for different Bacalhau operations
- `jobs/`: Contains YAML files defining Bacalhau job configurations
- `deploy_bacalhau.py`: Script for deploying Bacalhau (in root directory)

## Scripts

The `scripts/` directory contains the following Python scripts:

1. `python_1_hello_world.py`: A simple "Hello World" script to test basic Bacalhau execution.
2. `python_2_guessing_game.py`: A number guessing game to demonstrate interactive Bacalhau jobs.
3. `python_3_bad_stuff.py`: An example of potentially harmful operations, useful for testing security measures.
4. `python_4_list_directory.py`: Script to list contents of a directory, demonstrating file system access in Bacalhau.
5. `python_5_initial_analysis.py`: Performs initial analysis on data, showing how to process shared files.
6. `python_6_analyze_single_file.py`: Analyzes a single file, useful for testing granular file access permissions.

## Job Configurations

The `jobs/` directory contains YAML files that define different Bacalhau job configurations:

1. `simple_job.yaml`: A basic job configuration to run a simple task.
2. `readwrite_job.yaml`: Demonstrates a job with both read and write permissions to shared files.
3. `template_job.yaml`: A template for creating new job configurations.
4. `default_job.yaml`: Default job configuration with standard security settings.

## Exploring Bacalhau Functionality

To explore Bacalhau's functionality for shared files with security:

1. **Setup**: Ensure Bacalhau is deployed using the `deploy_bacalhau.py` script in the root directory.

2. **Basic Execution**: Start with running the `python_1_hello_world.py` script using the `simple_job.yaml` configuration to test basic execution.

3. **File Access**: Use `python_4_list_directory.py` with different job configurations to understand how file access permissions work in Bacalhau.

4. **Data Processing**: Experiment with `python_5_initial_analysis.py` and `python_6_analyze_single_file.py` to see how Bacalhau handles data processing tasks on shared files.

5. **Security Testing**: Try running `python_3_bad_stuff.py` with various job configurations to test how Bacalhau's security measures prevent potentially harmful operations.

6. **Read/Write Operations**: Use the `readwrite_job.yaml` configuration with scripts that require both read and write access to understand how Bacalhau manages these permissions.

7. **Custom Jobs**: Create your own job configurations based on `template_job.yaml` to explore specific security scenarios or file sharing requirements.

## Best Practices

- Always start with the most restrictive permissions and gradually increase access as needed.
- Use the `default_job.yaml` as a starting point for new job configurations to ensure basic security measures are in place.
- Regularly review and update job configurations to maintain security as your project evolves.

By working through these scripts and job configurations, you'll gain a comprehensive understanding of how Bacalhau manages shared files with security, allowing you to implement secure and efficient distributed computing workflows.
