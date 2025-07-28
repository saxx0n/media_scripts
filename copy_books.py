#!/usr/bin/env python3

import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Tuple

from shared_libs.argparse_utils import SortingHelpFormatter
from shared_libs.debug_utils import Debugger
from shared_libs.sentry_bootstrap import init as sentry_init

debugger = Debugger()


def check_encryption(book: Path) -> Tuple[str, str]:
    """
    Check if a book is encrypted.

    :param book: Path to the book file.
    :return: Tuple of ('Encrypted' or 'Not Encrypted', book name).
    """
    try:
        result = subprocess.run(
            ["file", "--brief", str(book)],
            capture_output=True, text=True, check=True
        )
        book_data = result.stdout
        debugger.log(f"Raw book data: {book_data}", 3)

        name = Path(book).stem
        if "encrypted" in book_data.lower():
            debugger.log(f"Book is encrypted: {book}", 2)
            return "Encrypted", name
        else:
            debugger.log(f"Book is not encrypted: {book}", 2)
            return "Not Encrypted", name
    except subprocess.CalledProcessError as e:
        print(f"Error processing {book}: {e}")
        return "Unknown", Path(book).stem


def download_files(tmp_directory: Path) -> None:
    """
    Download files from an Android tablet to the local filesystem.

    :param tmp_directory: Temporary directory for downloaded files.
    """
    debugger.log(f"Using tmp folder: {tmp_directory}", 2)

    try:
        run_command = [
            "/usr/local/bin/adb", "pull",
            "/sdcard/Android/data/com.amazon.kindle/files/",
            str(tmp_directory)
        ]
        debugger.log(f"Will run command: {' '.join(run_command)}", 2)
        print("Pulling books from tablet")

        result = subprocess.run(run_command, capture_output=True, text=True, check=True)
        debugger.log(f"adb output: {result.stdout}", 3)
    except subprocess.CalledProcessError as e:
        print(f"adb command failed with error: {e}")
        raise


def process_books(in_dir: Path, out_dir: Path) -> None:
    """
    Process books in the input directory and copy them to the output directory.

    :param in_dir: Directory with the downloaded books.
    :param out_dir: Directory to copy PRC files into.
    """
    try:
        debugger.log(f"Will write books to: {out_dir}")

        if not out_dir.is_dir():
            debugger.log(f"Creating output directory: {out_dir}", 2)
            out_dir.mkdir(parents=True, exist_ok=True)

        for foldername, _, filenames in os.walk(in_dir):
            for filename in filenames:
                if filename.endswith(".prc"):
                    full_path = Path(foldername).joinpath(filename)
                    debugger.log(f"Found file: {filename}", 2)
                    _, name = check_encryption(full_path)

                    target = out_dir.joinpath(filename)
                    if not target.is_file():
                        print(f"{name}")
                        shutil.copy(full_path, out_dir)
                    else:
                        debugger.log(f"File {filename} already exists, skipping", 2)

    except Exception as e:
        print(f"Error moving books: {e}")
        debugger.log(f"Error moving books: {e}", 1)


def parse_args():
    parser = argparse.ArgumentParser(
        formatter_class=SortingHelpFormatter,
        description="Pull Kindle books from an Android device and copy PRC files."
    )
    parser.add_argument(
        "-l", "--debug_level", type=int, choices=[1, 2, 3], required=False,
        help="Set debug level (enables debugging)"
    )
    parser.add_argument(
        "-t", "--temp_dir", required=False,
        default=f"{Path(tempfile.gettempdir()) / 'tmp_books'}",
        help="Temporary folder to use when copying books"
    )
    parser.add_argument(
        "-o", "--output_dir", required=False,
        default=f"{Path('~').expanduser()}",
        help="Folder to output PRC files to"
    )
    return parser.parse_args()


if __name__ == "__main__":
    try:
        sentry_init(debug_hook=debugger.log)

        args = parse_args()

        if args.debug_level:
            debugger.set_level(args.debug_level)
            debugger.log(f"Set debug level to: {args.debug_level}")

        tmp_dir = Path(args.temp_dir).expanduser()
        out_dir = Path(args.output_dir).expanduser()

        debugger.log(f"Using tmp dir: {tmp_dir}")
        download_files(tmp_dir)
        process_books(tmp_dir, out_dir)

    except Exception as e:
        debugger.log(f"Unhandled exception: {e}", 1)
        raise
