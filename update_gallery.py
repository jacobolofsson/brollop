#!/usr/bin/env python3
import argparse
import logging
import pathlib
import shutil
import subprocess
import sys
import typing
import yaml

CONVERT_EXE = "convert"
INSTALL_CONVERT_CMD = "brew install imagemagick"
THUMBNAIL_SUFFIX = ".thumb"
THUMBNAIL_WIDTH = 400
THUMBNAIL_HEIGHT = 400

_logger = logging.getLogger(__name__)


def _filter_thumbnails(
    files: typing.Iterable[pathlib.Path],
) -> typing.Generator[pathlib.Path, None, None]:
    for file in files:
        if THUMBNAIL_SUFFIX not in file.suffixes:
            yield file


def _thumbnail_path(file: pathlib.Path) -> pathlib.Path:
    return file.with_suffix(THUMBNAIL_SUFFIX + file.suffix)


def _update_thumbnail(file: pathlib.Path, dry_run: bool) -> None:
    thumbnail_file = _thumbnail_path(file)

    if thumbnail_file.exists():
        return

    thumbnail_dimensions = str(THUMBNAIL_WIDTH) if THUMBNAIL_WIDTH else ""
    thumbnail_dimensions += f"x{THUMBNAIL_HEIGHT}" if THUMBNAIL_HEIGHT else ""
    cmd = [
        CONVERT_EXE,
        "-thumbnail",
        thumbnail_dimensions + "^",  # add ^ to crop (instead of pad)
        "-gravity",
        "center",
        "-extent",
        thumbnail_dimensions,
        str(file),
        str(thumbnail_file),
    ]

    cmd_string = " ".join(cmd)
    if dry_run:
        print("Executing: ", cmd_string)
    else:
        _logger.info("Executing: '%s'", cmd_string)
        subprocess.run(cmd, check=True)


def _add(frontmatter: typing.Dict, file: pathlib.Path) -> bool:
    gallery_name = f"gallery_{file.parent.name}"
    _logger.debug("Adding %s to '%s'", file, gallery_name)
    entry = {
        "image_path": str(_thumbnail_path(file)),
        "url": str(file),
    }
    gallery = frontmatter.setdefault(gallery_name, [])
    if entry in gallery:
        return False

    _logger.warning("Missing %s in gallery", file)

    gallery.append(entry)

    return True


def main(dry_run: bool = False, reset: bool = False) -> int:
    if not shutil.which(CONVERT_EXE):
        _logger.error(
            "Could not find '%s'. You can install it with:\n    $ %s",
            CONVERT_EXE,
            INSTALL_CONVERT_CMD,
        )

    root_dir = pathlib.Path(__name__).parent

    gallery_file = root_dir / "_pages" / "gallery.md"
    gallery_file_parts = gallery_file.read_text().split("---")
    gallery_frontmatter = yaml.safe_load(gallery_file_parts[1])
    if reset:
        gallery_frontmatter = {
            k: v for k, v in gallery_frontmatter.items() if not k.startswith("gallery")
        }

    _logger.debug("Loaded frontmatter:\n%s", gallery_frontmatter)

    gallery_dir = root_dir / "assets" / "images" / "gallery"
    all_files = gallery_dir.rglob("*")
    all_images = [
        file for file in all_files if file.suffix.lower() in {".jpeg", ".jpg", ".png"}
    ]

    _logger.debug("Filtering thumbnails from: %s", all_images)

    missing = 0

    for file in _filter_thumbnails(all_images):
        _update_thumbnail(file, dry_run)
        missing += _add(gallery_frontmatter, file)

    if missing > 0:
        _logger.warning("Missing %u images in gallery", missing)

    frontmatter_string = "\n" + yaml.safe_dump(
        gallery_frontmatter, allow_unicode=True, sort_keys=False
    )
    gallery_file_parts[1] = frontmatter_string
    gallery_file_text = "---".join(gallery_file_parts)

    if dry_run:
        print(gallery_file_text)
    else:
        gallery_file.write_text(gallery_file_text)

    return missing


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-n", "--dry-run", action="store_true")
    parser.add_argument("-r", "--reset", action="store_true")

    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    try:
        sys.exit(main(args.dry_run, args.reset))
    except Exception as ex:
        _logger.critical("Unchaught exception: %s", ex)
        _logger.debug("Backtrace:", exc_info=True)
        sys.exit(-1)
