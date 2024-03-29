import re


def extract_fa_icons(css_file_path):
    """Extracts Font Awesome icon class names from a CSS file.

    Args:
        css_file_path (str): The path to the CSS file.

    Returns:
        list: A list of unique Font Awesome icon class names.
    """

    fa_icon_pattern = r"\.fa-[a-z0-9\-]+"  # Regex to match 'fa-' class names

    icon_classes = []
    with open(css_file_path, "r") as file:
        css_content = file.read()
        matches = re.findall(fa_icon_pattern, css_content)

        # Add unique matches to the list - but remove leading period
        icon_classes = list(set(matches))

    return icon_classes


def remove_leading_period_and_alphabetize(data):
    """Removes leading periods and alphabetizes a list of strings.

    Args:
        data (list): A list of strings.

    Returns:
        list: A sorted list of strings with leading periods removed.
    """

    cleaned_data = [item.lstrip(".") for item in data]  # Remove leading periods
    cleaned_data.sort()  # Alphabetize the list
    return cleaned_data


# Example usage
css_file = "static/css/fontawesome.css"  # Replace with your CSS file name
font_awesome_icons = extract_fa_icons(css_file)
font_awesome_icons = remove_leading_period_and_alphabetize(font_awesome_icons)

print(font_awesome_icons)
