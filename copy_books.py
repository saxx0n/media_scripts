#!/usr/bin/env python3

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

from argparse import HelpFormatter
from operator import attrgetter
from pathlib import Path
from typing import Tuple

enable_debug = False
debug_level = 1


class SortingHelpFormatter(HelpFormatter):
    def add_arguments(self, actions):
        actions = sorted(actions, key=attrgetter('option_strings'))
        super(SortingHelpFormatter, self).add_arguments(actions)


def check_encryption(book: Path) -> tuple[str, str]:
    """
    Check if a book is encrypted.

    :param book: The path to the book file.
    :return: A tuple containing the encryption status ('Encrypted' or 'Not Encrypted') and the name of the book.
    """
    try:
        book_data = subprocess.check_output(['file', '--brief', book])
        debug(f"Raw book data: {book_data}")

        name = book_data.decode('utf-8').split('"')[1]
        debug(f"Book name: {name}", 2)

        if 'encrypted' in book_data.decode('utf-8'):
            debug(f"Book is encrypted: {book}", 2)
            return 'Encrypted', name
        else:
            debug(f"Book is not encrypted: {book}", 2)
            return 'Not Encrypted', name
    except subprocess.CalledProcessError as e:
        print(f"Error processing {book}: {e}")


def debug(msg: str = '', debug_msg_level: int = 1, output=sys.stdout) -> None:
    """
    Prints the debug message if debug mode is enabled and the debug level is less than or equal to the debug level.

    :param msg: A string that represents the message to be printed. Default is an empty string.
    :param debug_msg_level: An integer that represents the debug message level. Default is 1.
    :param output: The output stream where the debug message will be printed. Default is sys.stdout.

    :return: None
    """
    if enable_debug and debug_msg_level <= debug_level:
        if debug_level == 1:
            message = msg
        else:
            message = f"DEBUG[{debug_msg_level}]: {msg}"
        output.write(f"{message}\n")


def download_files(tmp_directory: str) -> None:
    """
    Download files from an android tablet to the local filesystem

    :param tmp_directory: The temporary directory where the files will be downloaded to.
    :return: None
    """
    debug(f"Using tmp folder: {tmp_directory}", 2)

    try:
        run_command = list(
            f"/usr/local/bin/adb pull /sdcard/Android/data/com.amazon.kindle/files/ {tmp_directory}".split(' '))
        debug(f"Will run command: {' '.join(run_command)}", 2)
        print('Pulling books from tablet')
        file_copy = subprocess.check_output(run_command)

        debug(f"adb output: {file_copy.decode('utf-8')}", 3)

    except subprocess.CalledProcessError as e:
        print(f"adb command failed with error: {e}")
        raise


def parse_args():
    """
    Parses command line arguments for the program.

    :return: An instance of the argparse.Namespace class containing the parsed arguments.
    """
    parser = argparse.ArgumentParser(formatter_class=SortingHelpFormatter)
    parser.add_argument('-l', '--debug_level', type=int, choices=[1, 2, 3], required=False,
                        help='Set debug level (enabled debugging)')
    parser.add_argument('-t', '--temp_dir', required=False,
                        default=f"{Path(tempfile.gettempdir()).joinpath('tmp_books')}",
                        help='Temporary folder to use when copying books')
    parser.add_argument('-o', '--output_dir', required=False,
                        default=f"{Path('~').expanduser()}", help='Folder to output prc files to')
    return parser.parse_args()


def process_books(in_dir: Path, out_dir: Path) -> None:
    """
    Process books in the input directory and move them to the output directory.

    :param in_dir: The input directory where the books are located.
    :param out_dir: The output directory where the books will be moved.
    :return: None
    """
    try:
        debug(f"Will write books to: {out_dir}")

        if not out_dir.is_dir():
            debug(f"Creating output directory: {out_dir}", 2)
            os.makedirs(out_dir)

        for foldername, subfolders, filenames in os.walk(in_dir):
            for filename in filenames:
                if filename.endswith('.prc'):
                    debug(f"Found file: {filename}", 2)
                    _, name = check_encryption(Path(foldername).joinpath(filename))
                    if not out_dir.joinpath(filename).is_file():
                        if not out_dir.is_dir():
                            debug(f"Creating output directory: {out_dir}/", 2)
                            os.makedirs(out_dir)
                        print(f"{name}")
                        shutil.copy(os.path.join(foldername, filename), out_dir)
                    else:
                        debug('File already exists, skipping move', 2)

    except Exception as e:
        print(f"Error moving books: {e}")


if __name__ == "__main__":
    args = parse_args()

    if args.debug_level:
        enable_debug = True
        debug_level = args.debug_level
        debug(f"Set debug level to: {debug_level}")

    debug(f"Using tmp dir: {args.temp_dir}")

    download_files(args.temp_dir)
    process_books(Path(args.temp_dir).expanduser(), Path(args.output_dir).expanduser())
