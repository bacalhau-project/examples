#!/bin/bash

cd tf || exit

# Load a list of zones from regions.md, as long as they are not commented out or blank
regions=()
while IFS= read -r line; do
    if [[ $line != \#* ]] && [[ $line != "" ]]; then
        regions+=("$line")
    fi
done < ../regions.md

# If aurgument is create, then execute first statement, else execute second statement
if [ "$1" == "create" ]; then
    for r in "${regions[@]}"
    do
        terraform workspace select -or-create "$r"
        terraform init -upgrade
        terraform apply -auto-approve -var "region=$r" -var-file=.env.json
    done
elif [ "$1" == "destroy" ]; then
    for r in "${regions[@]}"
    do
        terraform workspace select -or-create "$r"
        terraform init -upgrade
        terraform destroy -auto-approve -var "region=$r" -var-file=.env.json
    done
else
    echo "Please specify create or destroy"
fi

