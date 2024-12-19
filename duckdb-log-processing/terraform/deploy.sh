#!/bin/bash
set -euo pipefail

# Function to check if required tools are installed
check_requirements() {
    local missing_tools=()
    
    if ! command -v terraform &> /dev/null; then
        missing_tools+=("terraform")
    fi
    
    if ! command -v gcloud &> /dev/null; then
        missing_tools+=("gcloud")
    fi
    
    if ! command -v yq &> /dev/null; then
        missing_tools+=("yq")
    fi
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        echo "Error: Required tools are missing:"
        printf '%s\n' "${missing_tools[@]}"
        echo "Please install yq with: brew install yq"
        exit 1
    fi
}

# Function to ensure GCP authentication
ensure_gcp_auth() {
    if ! gcloud auth application-default print-access-token &> /dev/null; then
        echo "Authenticating with Google Cloud..."
        gcloud auth application-default login
    fi
}

# Function to setup environment and merge orchestrator config
setup_env() {
    if [ ! -f .env.json ]; then
        echo "Please create and edit .env.json with your configuration values"
        exit 1
    fi

    # Get orchestrator config path from .env.json
    local config_path=$(jq -r '.orchestrator_config_path' .env.json)
    
    # Check if the config file exists
    if [ ! -f "$config_path" ]; then
        echo "CONFIG PATH is $config_path"
        echo "Error: orchestrator-config.yaml not found"
        exit 1
    fi

    # Check if bacalhau.service exists
    if [ ! -f "node_files/bacalhau.service" ]; then
        echo "Error: bacalhau.service not found in node_files/"
        pwd
        ls -la node_files/
        exit 1
    fi

    # Check if start_bacalhau.sh exists
    if [ ! -f "node_files/start_bacalhau.sh" ]; then
        echo "Error: start_bacalhau.sh not found in node_files/"
        exit 1
    fi

    # Ensure start_bacalhau.sh is executable
    if [ ! -x "node_files/start_bacalhau.sh" ]; then
        echo "Making start_bacalhau.sh executable"
        chmod +x "node_files/start_bacalhau.sh"
    fi

    # Verify file permissions
    if [ ! -r "$config_path" ] || [ ! -r "node_files/bacalhau.service" ] || [ ! -r "node_files/start_bacalhau.sh" ]; then
        echo "Error: Cannot read required files. Check permissions."
        exit 1
    fi
}

# Function to run terraform with .env.json variables
run_terraform() {
    local command=$1
    shift  # Remove first argument, leaving remaining args

    case "$command" in
        "plan")
            terraform plan -var-file=.env.json -out=tf.plan "$@"
            ;;
        "apply")
            if [ ! -f tf.plan ]; then
                echo "No plan file found. Running plan first..."
                terraform plan -var-file=.env.json -out=tf.plan "$@"
            fi
            terraform apply tf.plan
            rm -f tf.plan  # Clean up plan file after apply
            ;;
        "destroy")
            terraform plan -destroy -var-file=.env.json -out=tf.destroy.plan "$@"
            terraform apply tf.destroy.plan

            # Check if clean_up_nodes.py exists and a config file was provided
            if [ -f "clean_up_nodes.py" ] && [ $# -gt 0 ]; then
                local config_file=$1
                if [ -f "$config_file" ]; then
                    echo "Running node cleanup with config: $config_file"
                    python3 clean_up_nodes.py "$config_file"
                else
                    echo "Warning: Config file not found: $config_file"
                    echo "Skipping node cleanup."
                fi
            else
                echo "Note: No config file provided or clean_up_nodes.py not found. Skipping node cleanup."
            fi

            rm -f tf.destroy.plan  # Clean up destroy plan file
            ;;
        *)
            terraform "$command" -var-file=.env.json "$@"
            ;;
    esac
}

# Main script
main() {
    check_requirements
    setup_env
    ensure_gcp_auth

    case "$1" in
        "init")
            terraform init
            ;;
        "plan")
            run_terraform plan "${@:2}"
            ;;
        "apply")
            run_terraform apply "${@:2}"
            ;;
        "destroy")
            run_terraform destroy "${@:2}"
            ;;
        "recreate")
            run_terraform destroy -auto-approve "${@:2}" && \
            run_terraform apply -auto-approve "${@:2}"
            ;;
        *)
            echo "Usage: $0 {init|plan|apply|destroy|recreate}"
            exit 1
            ;;
    esac
}

# Run main if script is executed (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if [ $# -eq 0 ]; then
        echo "Usage: $0 {init|plan|apply|destroy|recreate}"
        exit 1
    fi
    main "$@"
fi 