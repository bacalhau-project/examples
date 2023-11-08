import zipfile
import sys
import os
from os import path

DestinationDir = sys.argv.pop()
SourceDir = sys.argv.pop()

# We expect source dir to be flat and contain a number of zip files. Reading zip
# file archive information is fast (as opposed to extracting) and the update
# frequency of new zip files is slow, so we do not really need to keep a log of
# which files we have processed; we can just compare what is the destination dir
# to what should be there.


def relative_files(src: str):
    for root, _, files in os.walk(src):
        for file in files:
            yield path.join(path.relpath(root, src), file)


for file in os.listdir(SourceDir):
    filepath = path.join(SourceDir, file)
    if not path.isfile(filepath):
        print("Not a file", filepath, file=sys.stderr)
        continue

    try:
        with zipfile.ZipFile(filepath, "r") as zip:
            existing_files = set(
                path.normpath(p) for p in relative_files(DestinationDir)
            )
            to_extract = set()
            for info in zip.filelist:
                if info.is_dir():
                    continue

                name = info.filename
                if path.normpath(name) in existing_files:
                    print(
                        "Already extracted", path.join(filepath, name), file=sys.stderr
                    )
                    continue

                to_extract.add(name)

            for name in to_extract:
                print("Extracting", path.join(DestinationDir, name), file=sys.stdout)
                zip.extract(name, DestinationDir)

    except Exception as e:
        print(e, filepath, file=sys.stderr)
        continue
