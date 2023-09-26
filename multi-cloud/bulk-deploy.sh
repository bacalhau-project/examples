#!/bin/bash

# AWS Operations
aws_directory="tf/aws"
aws_directory_path=$(realpath "$aws_directory")
cd $aws_directory_path || exit

# Load a list of zones from regions-aws.md, as long as they are not commented out or blank
aws_regions=()
while IFS= read -r line; do
    if [[ $line != \#* ]] && [[ $line != "" ]]; then
        aws_regions+=("$line")
    fi
done < ../../regions-aws.md

if [[ "$1" == "create" && "$PWD" == "$aws_directory_path" ]]; then
    for r in "${aws_regions[@]}"
    do
        echo $PWD
        terraform workspace select -or-create "$r"
        terraform init -upgrade
        terraform apply -auto-approve -var "region=$r" -var-file=.env.json
    done
elif [[ "$1" == "destroy" && "$PWD" == "$aws_directory_path" ]]; then
    for r in "${aws_regions[@]}"
    do
        echo $PWD
        terraform workspace select -or-create "$r"
        terraform init -upgrade
        terraform destroy -auto-approve -var "region=$r" -var-file=.env.json
    done
else
    echo "Please specify create or destroy for AWS"
fi

# GCP Operations
gcp_directory="../gcp"
gcp_directory_path=$(realpath "$gcp_directory")
cd $gcp_directory_path || exit

# Load a list of zones from regions-gcp.md, as long as they are not commented out or blank
# gcp_regions=()
# while IFS= read -r line; do
#     if [[ $line != \#* ]] && [[ $line != "" ]]; then
#         gcp_regions+=("$line")
#     fi
# done < ../../regions-gcp.md

if [[ "$1" == "create" && "$PWD" == "$gcp_directory_path" ]]; then
    echo $PWD
    terraform init -upgrade
    terraform apply -auto-approve -var-file=.env.json

elif [[ "$1" == "destroy" && "$PWD" == "$gcp_directory_path" ]]; then
    echo $PWD
    terraform init -upgrade
    terraform destroy -auto-approve -var-file=.env.json
else
    echo "Please specify create or destroy for GCP"
fi
