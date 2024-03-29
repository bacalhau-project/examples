# Read the file all-icons.txt and just output icon names in classes that are of the structure:
# class="fa-solid fa-icon-name"

import re

# Read the file all-icons.txt
with open('all-icons.txt', 'r') as file:
    data = file.read()
    
# Find all the icon names in the file
icon_names = re.findall(r'(fa-[a-z-]+)', data)

# Output the icon names
for icon_name in icon_names:
    print(icon_name)