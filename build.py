import glob
import os
from pathlib import Path

import nbconvert

src_dir = Path(".")
dst_dir = Path("rendered")

all_notebooks = set(glob.glob("**/*.ipynb", recursive=True))

notebook_exclude_directories = ("templates", "todo")
notebooks_to_render = list(filter(lambda x: not x.startswith(notebook_exclude_directories), all_notebooks))

image_suffixes = (".png", ".jpg", ".jpeg", ".gif", ".svg")
image_exclude_directories = ("templates", "todo", "rendered")
image_files_to_copy = []
for image_suffix in image_suffixes:
    image_files = glob.glob(f"images/**/*{image_suffix}", recursive=True)
    for i in image_files:
        if not i.startswith(image_exclude_directories):
            image_files_to_copy.append(i)

for f in notebooks_to_render:
    markdown_string = nbconvert.markdown.MarkdownExporter(
        config={
            "TagRemovePreprocessor": {
                "enabled": True,
                "remove_cell_tags": ("remove_cell",),
                "remove_all_outputs_tags": ("remove_output",),
                "remove_input_tags": ("remove_input",),
            }
        },
    ).from_filename(
        f,
        output_file=Path(dst_dir) / Path(os.path.splitext(f)[0] + ".md"),
    )
    stripped_markdown_string = markdown_string[0].replace("%%bash", "")

    notebook_destination_dir = Path(dst_dir) / os.path.dirname(f)
    Path.exists(notebook_destination_dir) or Path(notebook_destination_dir).mkdir(parents=True)
    Path.write_text(Path(os.path.join(dst_dir, os.path.splitext(f)[0] + ".md")), stripped_markdown_string)
