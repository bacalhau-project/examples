#!/bin/bash

# AWS Operations
aws_directory="tf/aws"
cd $aws_directory || exit

# Load a list of zones from regions.md, as long as they are not commented out or blank
aws_regions=()
while IFS= read -r line; do
    if [[ $line != \#* ]] && [[ $line != "" ]]; then
        aws_regions+=("$line")
    fi
done < ../regions.md

if [[ "$1" == "create" && "$PWD" == "$aws_directory" ]]; then
    for r in "${aws_regions[@]}"
    do
        terraform workspace select -or-create "$r"
        terraform init -upgrade
        terraform apply -auto-approve -var "region=$r" -var-file=.env.json
    done
elif [[ "$1" == "destroy" && "$PWD" == "$aws_directory" ]]; then
    for r in "${aws_regions[@]}"
    do
        terraform workspace select -or-create "$r"
        terraform init -upgrade
        terraform destroy -auto-approve -var "region=$r" -var-file=.env.json
    done
else
    echo "Please specify create or destroy for AWS"
fi

# GCP Operations
gcp_directory="../gcp"
cd $gcp_directory || exit

# Assume the regions for GCP are also in regions.md

if [[ "$1" == "create" && "$PWD" == "$gcp_directory" ]]; then
    terraform init
    terraform plan -out plan.out
    terraform apply plan.out

elif [[ "$1" == "destroy" && "$PWD" == "$gcp_directory" ]]; then
    terraform destroy -plan=plan.out

else
    echo "Please specify create or destroy for GCP"
fi
