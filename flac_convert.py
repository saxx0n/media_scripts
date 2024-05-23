#!/usr/bin/env python3

import argparse
import os.path

from operator import attrgetter
from pathlib import Path
from subprocess import Popen, PIPE, STDOUT
from sys import stdout

DEBUG = False


class SortingHelpFormatter(argparse.HelpFormatter):
    def add_arguments(self, actions):
        actions = sorted(actions, key=attrgetter('option_strings'))
        super(SortingHelpFormatter, self).add_arguments(actions)


def debug(msg='', debug_msg_level=1, out=stdout):
    if DEBUG and debug_msg_level <= debug_level:
        if msg != '':
            if debug_level > 1:
                out.write(f"DEBUG[{debug_msg_level}]: {msg}")
            else:
                out.write(f"DEBUG: {msg}")
        out.write('\n')


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SortingHelpFormatter)

    parser.add_argument('-r', '--root', required=True, help='Folder with files to convert, or file to convert')
    parser.add_argument('--dry-run', action='store_true', help='Only show what would be done')
    parser.add_argument('-l', '--debug_level', type=int, choices=[1, 2, 3], help='Set debug level (enabled debugging)')

    return parser.parse_args()


def run_convert(flac_file):
    print(f"Starting processing on: {flac_file}")
    base_name = Path(flac_file).stem
    raw_path = Path(flac_file).parent
    debug(f"Looking at file: {raw_path}/{base_name}")
    if os.path.exists(Path(raw_path).joinpath(f"{base_name}.m4a")):
        print('m4a already exists')
        return True

    break_command = f'ffmpeg -loglevel panic -i "{Path(flac_file)}" ' \
                    f'-vn -c copy -acodec alac "{Path(raw_path).joinpath(f"{base_name}.m4a")}"'
    debug(f"Command: {break_command}", 3)
    q = Popen(break_command, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT)
    _, _ = q.communicate()
    q.wait()

    if q.returncode != 0:
        print('Error converting')
        return False
    else:
        os.remove(Path(flac_file))

    return True


if __name__ == '__main__':
    args = parse_args()

    if args.debug_level:
        DEBUG = True
        debug_level = args.debug_level
        debug(f"Set debug level to: {debug_level}")

    if args.dry_run:
        dry_run = args.dry_run
        debug(f"Set dry run to: {dry_run}")

    if '.flac' in args.root:
        debug('Running in single file mode')
        if os.path.isfile(Path(args.root)):
            run_convert(args.root)
        else:
            print(f'Unable to find: {args.root}')

    else:
        debug('Running in multiple file mode')
        file_list = list(Path(args.root).rglob("*.flac"))
        if len(file_list) > 0:
            for in_file in sorted(file_list):
                run_convert(in_file)
