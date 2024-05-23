#!/usr/bin/env python3

import argparse
import datetime
import hashlib
import json
import os
import re
import requests
import shutil
import sys
import zipfile

from argparse import HelpFormatter
from datetime import date, datetime
from operator import attrgetter
from pathlib import Path
from requests.auth import HTTPBasicAuth
from subprocess import Popen, PIPE, STDOUT

calibre_db = '/Applications/calibre.app/Contents/MacOS/calibredb'
library_path = '/Users/saxx0n/Documents/Calibre/Calibre Manga Library v2'

DEBUG = False
temp_folder = './temp/'

info_name = 'ComicInfo.xml'

force_png = False

skip_komga = False
skip_local = False

komga_server = 'komga.local'

series_replacements = {}


class SortingHelpFormatter(HelpFormatter):
    def add_arguments(self, actions):
        actions = sorted(actions, key=attrgetter('option_strings'))
        super(SortingHelpFormatter, self).add_arguments(actions)


def call_api(remote_url, user, pw):
    debug(f" Checking url: {remote_url}", 3)
    r = requests.get(remote_url,
                     auth=HTTPBasicAuth(user, pw.strip("'")))
    if r.status_code == 200:
        debug('API Returned 200', 3)
        return r.text
    else:
        print('Error calling API')
        exit(2)


def check_cover(working_folder_path, image_extension):
    debug(f"Checking for covers at: {working_folder_path} with extension: {image_extension}", 3)
    debug(f"Looking for cover at: {Path(working_folder_path).joinpath(f'cover{image_extension}')}", 3)
    if os.path.isfile(Path(working_folder_path).joinpath(f'cover{image_extension}')):
        debug('Named cover found', 2)
        cover_name = 'cover'
    else:
        debug('No named cover, looking for backup', 2)

        if os.path.isfile(Path(working_folder_path.parents[0]).joinpath(f"cover{image_extension}")):
            debug('Found backup image file, moving into place', 2)
            shutil.copyfile(Path(working_folder_path.parents[0]).joinpath(f"cover{image_extension}"),
                            Path(working_folder_path).joinpath(f'cover{image_extension}'))
            cover_name = 'cover'
        elif os.path.isfile(Path(working_folder_path).joinpath(f"page_cover{image_extension}")):
            debug('Found page_cover, moving into place', 2)
            shutil.copyfile(Path(working_folder_path).joinpath(f"page_cover{image_extension}"),
                            Path(working_folder_path).joinpath(f'cover{image_extension}'))
            cover_name = 'cover'
        else:
            debug('Unable to find cover, setting first image as cover', 3)
            cover_name = sorted(os.listdir(Path(working_folder_path)))[0].replace(image_extension, '')

    debug(f"Cover: \"{Path(working_folder_path).joinpath(f'{cover_name}{image_extension}')}\"", 2)

    try:
        first_file = sorted(os.listdir(Path(working_folder_path)))[0]
        if first_file == f'{cover_name}{image_extension}':
            debug(' First file is cover, incrementing', 3)
            first_file = sorted(os.listdir(Path(working_folder_path)))[1]
        debug(f" First non-cover file: {first_file}", 3)

        if Path(Path(working_folder_path).joinpath(f'{cover_name}{image_extension}')) > \
                Path(working_folder_path).joinpath(first_file):
            debug('File names are non-ordered for cover, reorder needed', 2)
            first_file = reorder(Path(Path(working_folder_path)), f'{cover_name}{image_extension}')
            if not first_file:
                print(' Unable to fix image naming')
                debug(' Unable to fix image naming')
                return False

        hash_cover = get_hash(Path(working_folder_path).joinpath(f'{cover_name}{image_extension}'))
        hash_first = get_hash(Path(working_folder_path).joinpath(first_file))
        if hash_cover == hash_first:
            debug(" Cover matches first file, removing cover", 2)
            os.remove(Path(working_folder_path).joinpath(f'{cover_name}{image_extension}'))
        return True
    except UnboundLocalError:
        debug(' Unable to verify cover, YMMV')
        return True


def check_komga(series, volume, username, password):
    if series in series_replacements.keys():
        series_id = series_replacements[series]
    else:
        series_string = series.replace(' ', '%20')
        series_id = find_series(series_string, series, username, password)
        if not series_id:
            debug(" Found no matches, not in komga")
            return False

    debug(f" Series ID: {series_id}", 3)
    volume_exists = find_volume(series_id, volume, username, password)
    debug(f"Volume exists: {volume_exists}", 3)
    return volume_exists


def check_match(var, var_val, var_name):
    if var != 'all' and var != var_val:
        debug(f"Wrong {var_name}")
        print(f" {var_name} does not match ({var_val})")
        return False
    return True


def check_path(purchase_source, name, vol, create):
    path = Path(purchase_source).joinpath(name.replace('/', '_')).joinpath(f"Volume {vol}.cbz")
    debug(f"Checking for file/path: '{path}'", 3)
    if os.path.isdir(path.parents[0]):
        if os.path.isfile(Path(path)):
            return False
        else:
            return True
    else:
        if not create:
            debug('Folder not found, creating', 3)
            os.makedirs(path.parents[0])
            return True


def clean_folder(folder):
    debug(f" Cleaning up {folder}")
    if os.path.basename(__file__) in os.listdir(folder):
        print('!!! Would purge self, skipping cleanup !!!')
        debug(' ERROR: Directory to cleanup includes self.')
        sys.exit(-1)
    else:
        shutil.rmtree(folder)


def clean_summary(temp_item):
    temp_item = temp_item.replace('<div>', '').replace('</div>', '')
    temp_item = temp_item.replace('<strong>', '').replace('</strong>', '')
    temp_item = temp_item.replace('<h3>', '').replace('</h3>', '')
    temp_item = temp_item.replace('<em>', '').replace('</em>', '')
    temp_item = re.sub('<p .*">', '', temp_item, flags=re.DOTALL).replace('<p>', '').replace('</p>', '')
    temp_item = re.sub('<span .*">', '', temp_item,
                       flags=re.DOTALL).replace('<span>', '').replace('</span>', '')

    temp_item = temp_item.replace('&lsquo;', "'").replace('&rsquo;', "'")
    temp_item = temp_item.replace('&ldquo;', '"').replace('&rdquo;', '"')
    temp_item = temp_item.replace('&hellip;', '...')
    temp_item = temp_item.replace('&mdash;', '---').replace('&ndash;', '-')
    temp_item = temp_item.replace('<br>', '\n')

    return temp_item


def convert_calibre_data(data):
    new_index = {}
    for item in data:
        tmp_id = item['id']
        new_index[str(tmp_id)] = {}
        debug(f"Building key for item with ID: {tmp_id}", 3)

        for element in item:
            debug(f"Looking at sub-element: {element}", 3)
            if element != 'id':
                new_index[str(tmp_id)][element] = item[element]

    debug(f"Rebuilt index: {new_index}", 3)
    return new_index


def convert_manga(epub, calibre_data, publisher, purchase, user=False, password=False, dry_run_inner=False):
    debug(f"Dry run mode: {dry_run_inner}")
    debug(f"Looking at file: {epub}", 3)
    book_id = Path(epub).parents[0].name.rsplit(' (')[-1].rsplit(')')[0]
    debug('Extracting name/volume')
    debug(f"Book ID: {book_id}", 2)
    book_data = calibre_data[book_id]
    debug(f"Book data: {book_data}", 3)

    try:
        manga_series = book_data['series'].replace(' Omnibus', '').replace(' & ', ' and ')
    except KeyError:
        manga_series = book_data['title']

    debug(f"Name: {book_data['title']}", 2)
    debug(f"Series: {manga_series}", 2)
    debug(f"ID: {book_data['series_index']}", 2)

    if not DEBUG:
        print(f"Looking at {manga_series}, Vol. {int(book_data['series_index'])} ({book_data['authors']})")

    if not check_match(publisher, book_data['publisher'], 'Publisher'):
        return

    if not check_match(purchase, book_data['*purchase_location'], 'Purchase Location'):
        return

    debug('Checking for already in komga')
    if not skip_komga:
        if check_komga(manga_series, book_data['series_index'], user, password):
            debug('Manga already exists in Komga')
            print(' Manga already exists in Komga')
            return

    debug('Checking for existing extraction')
    if not skip_local:
        if not check_path(book_data['publisher'], manga_series, book_data['series_index'], dry_run_inner):
            debug('Manga already exists locally')
            print(' Manga already exists locally')
            return

    debug("Starting manga extraction")
    with zipfile.ZipFile(epub, 'r') as zip_ref:
        zip_ref.extractall(temp_folder)

    debug('Determining folder structure')
    root_folder, image_folder = get_folder(temp_folder)
    debug(f"Main folder: '{root_folder}', images_folder: '{image_folder}'", 2)

    debug('Determining image extension')
    extension = get_extension(Path(temp_folder).joinpath(root_folder).joinpath(image_folder))
    if not extension:
        print('Unable to find extension')
        clean_folder(temp_folder)
        return
    debug(f" Image format: '{extension}'", 2)

    debug('Checking for Redundant cover')
    if not check_cover(Path(temp_folder).joinpath(root_folder).joinpath(image_folder), extension):
        print('Unable to process cover data')
        debug(' Unable to process cover data')
        clean_folder(temp_folder)
        return

    debug('Building Comic Info')
    if not generate_comix(book_data):
        print('Unable to build ComicInfo.xml')
        debug(' Unable to build ComicInfo.xml')
        clean_folder(temp_folder)
        return

    debug("Generating new cbz volume")
    if not dry_run_inner:
        generate_cbz(book_data, manga_series, temp_folder, root_folder, image_folder, extension)

    debug('Cleaning up temp folder')
    clean_folder(temp_folder)

    print(' Build complete')


def dump_calibre(limited=False):
    debug('Dumping calibre data to local variable', 3)
    command = f"{calibre_db} --library-path='{library_path}' list " \
              '-f all ' \
              '--for-machine'
    if limited:
        command += f" -s id:{limited}"
    debug(f"Calibre Command: {command}", 3)
    p = Popen(command, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT)
    tmp_calibre_data = json.loads(p.stdout.read().decode())
    debug(f"Calibre data: {tmp_calibre_data}", 3)

    tmp_calibre_data = convert_calibre_data(tmp_calibre_data)
    return tmp_calibre_data


def debug(msg='', debug_msg_level=1, out=sys.stdout):
    if DEBUG and debug_msg_level <= debug_level:
        if msg != '':
            if debug_level > 1:
                out.write(f"DEBUG[{debug_msg_level}]: {msg}")
            else:
                out.write(f"DEBUG: {msg}")
        out.write('\n')


def find_series(series_string, series, username, password):
    url = f"https://{komga_server}/api/v1/series?search_regex={series_string}%2CTITLE"
    id_full = json.loads(call_api(url, username, password))
    debug(f" API returned: {id_full}", 3)
    debug(f" Found {len(id_full['content'])} matching series", 3)
    if len(id_full['content']) == 0:
        return False
    series_id = False
    if len(id_full['content']) > 1:
        debug(" Fount multiple matches, looping through", 2)
        for sub_search in id_full['content']:
            debug(f"  Looking at series: {sub_search['name']}", 3)
            if sub_search['name'] == series:
                debug('   Found match!', 3)
                series_id = sub_search['id']
                break
            else:
                debug('   Not a match!', 3)
    else:
        series_id = id_full['content'][0]['id']
    return series_id


def find_volume(series_id, volume, username, password):
    url = f"https://{komga_server}/api/v1/series/{series_id}/books?size=400"
    series_full = json.loads(call_api(url, username, password))
    debug(f" API returned: {series_full}", 3)
    debug(f" Found {len(series_full['content'])} volumes", 3)
    for key in series_full['content']:
        debug(f" Looking at key: {key}", 3)
        debug(f"   Name: {key['metadata']['title']}", 3)
        debug(f"   Number: {key['metadata']['number']}", 3)
        if ',' in key['metadata']['number']:
            debug("    Combo volume detected ','", 3)
            check_number = key['metadata']['number'].split(',')
        elif '-' in key['metadata']['number']:
            debug(f"     Combo volume detected '-' '{key['metadata']['number']}'", 3)
            start, end = key['metadata']['number'].split('-')
            debug(f"     Start: {start}, end: {int(end) + 1}")
            check_number = [str(i) for i in range(int(start), int(end) + 1, 1)]
        else:
            debug("     Single volume detected", 3)
            check_number = key['metadata']['number']
        debug(f"      Checking against: {check_number}", 3)
        if str(int(volume)) in check_number:
            debug(' Found a match!', 3)
            return True
    debug(f'Looped all volumes and didnt find volume: {volume}')
    return False


def generate_cbz(book_data, manga_series, temp_folder_int, root_folder, image_folder, extension):
    cbz_location = Path(book_data['publisher']).joinpath(
        manga_series.replace('/', '_')).joinpath(f"Volume {book_data['series_index']}.cbz")
    debug(f" CBZ file: '{cbz_location}", 2)
    with zipfile.ZipFile(cbz_location, 'w') as zip_ref:
        for image in os.listdir(Path(temp_folder_int).joinpath(root_folder).joinpath(image_folder)):
            if Path(image).suffix == extension:
                # debug(f" Adding {image} to zip", 3)
                # noinspection PyTypeChecker
                zip_ref.write(Path(temp_folder_int).joinpath(root_folder).joinpath(image_folder).joinpath(image),
                              arcname=image)
        zip_ref.write(Path(temp_folder_int).joinpath(info_name), arcname=info_name)


def generate_comix(book_record):
    common_data = {
        'Volume': 'series_index',
        'Writer': 'authors',
        'Publisher': 'publisher',
        'Tags': 'tags',
        'Count': '*total_volumes',
        'AgeRating': '*age_rating',
        'Penciller': '*penciller',
        'Inker': '*inker',
        'Imprint': '*imprint',
        'Colorist': '*colorist',
        'Letterer': '*letterer',
        'CommunityRating': '*rating_cust',
        'CoverArtist': '*cover_artist',
        'Editor': '*editor',
        'Translator': '*translator',
        'Genre': '*genre',
        'Web': '*web',
        'ISBN': '*isbn'
    }

    year = book_record['pubdate'].split('-')[0]
    month = book_record['pubdate'].split('-')[1]
    day = book_record['pubdate'].split('-')[2].split('T')[0]

    debug(f"y: {year}, m: {month}, y: {day}", 3)

    debug(f"Building {info_name}", 3)
    xml = '<ComicInfo xmlns:xsd="http://www.w3.org/2001/XMLSchema" ' \
          'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
    for item in common_data:
        if common_data[item] in book_record.keys() and book_record[common_data[item]]:
            if item == 'Volume':
                xml += f"   <{item}>{int(book_record[common_data[item]])}</{item}>\n"
            elif isinstance(book_record[common_data[item]], list):
                xml += f"   <{item}>{','.join(book_record[common_data[item]])}</{item}>\n"
            elif item == 'Writer':
                xml += f"   <{item}>{book_record[common_data[item]].split('&')[0].rstrip()}</{item}>\n"
            else:
                xml += f"   <{item}>{book_record[common_data[item]]}</{item}>\n"
    xml += f"   <Year>{year}</Year>\n   <Month>{month}</Month>\n   <Day>{day}</Day>\n"

    xml += f"   <Summary>{clean_summary(book_record['comments'])}</Summary>\n"

    if book_record['*manga']:
        xml += '   <Manga>YesAndRightToLeft</Manga>\n'
        xml += '   <LanguageISO>ja</LanguageISO>\n'

    try:
        book_num = book_record['title'].split(' Vol.')[1].split(' (Manga)')[0]
        debug(f"book_num: {book_num}", 3)
    except IndexError:
        book_num = 'NONE'

    number = get_number(book_num, book_record)
    debug(f"Vol number is: {number}")
    xml += f"   <Number>{number}</Number>\n"

    title, series = get_series(book_record, number)
    xml += f"   <Title>{title}</Title>\n"
    xml += f"   <Series>{series}</Series>\n"

    xml += '</ComicInfo>'

    debug(f"XML:\n{xml}", 3)

    with open(Path(temp_folder).joinpath(info_name), 'w') as outfile:
        outfile.write(xml)

    return True


def get_extension(basename):
    debug(f" Looking at folder: {basename}", 3)
    extension_list = []
    for image in os.listdir(basename):
        suffix = Path(image).suffix
        if suffix not in extension_list:
            extension_list.append(suffix)

    debug(' Cleaning potential bad entries off list', 2)
    for extension in ['', '.css', '.ncx', '.html', '.opf', '.xhtml']:
        if extension in extension_list:
            debug(f" Cleaning bad entry: {extension}", 3)
            extension_list.remove(extension)

    if force_png:
        extension_list.remove('.jpeg')
        extension_list.remove('.gif')

    debug(f"Extension: {extension_list}")

    if len(extension_list) == 1:
        debug(f" All extensions match, type: {extension_list[0]}", 3)
        return extension_list[0]
    else:
        return False


def get_folder(manga_file):
    if os.path.isdir(Path(manga_file).joinpath('OEBPS')):
        root_dir = 'OEBPS'
    elif os.path.isdir(Path(manga_file).joinpath('OPS')):
        root_dir = 'OPS'
    elif os.path.isdir(Path(manga_file).joinpath('item')):
        root_dir = "item"
    elif os.path.isdir(Path(manga_file).joinpath('EPUB')):
        root_dir = 'EPUB'
    elif os.path.isdir(Path(manga_file).joinpath('images')) or os.path.isdir(Path(manga_file).joinpath('image')):
        root_dir = '.'
    elif len(list(Path(manga_file).rglob("*.jpg"))) > 30:
        return '.', '.'
    elif len(list(Path(manga_file).rglob("*.png"))) > 30:
        return '.', '.'
    else:
        debug('Unable to determine main-folder layout')
        return False, False

    debug(f"Root folder: {root_dir}", 3)

    if os.path.isdir(Path(manga_file).joinpath(root_dir).joinpath('images')):
        images_dir = 'images'
    elif os.path.isdir(Path(manga_file).joinpath(root_dir).joinpath('Images')):
        images_dir = 'Images'
    elif os.path.isdir(Path(manga_file).joinpath(root_dir).joinpath('image')):
        images_dir = 'image'
    elif os.path.isdir(Path(manga_file).joinpath(root_dir).joinpath('Image')):
        images_dir = 'Image'
    else:
        debug('Unable to determine sub-folder layout')
        return False, False

    debug(f"Image Folder: {images_dir}", 3)
    return root_dir, images_dir


def get_hash(filename):
    debug(f" Generating Hash for: {filename}", 3)
    hasher = hashlib.sha512()
    with open(filename, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
        a = hasher.hexdigest()
        debug(f"  Hash computed as: {a}", 3)
        return a


def get_number(in_number, record):
    number = ''
    for seperator in ['-', ',']:
        if seperator in in_number:
            end = in_number.split(seperator)[-1].strip()
            start = in_number.split(seperator)[-2].strip()

            debug(f"s: {start}, e: {end}", 3)
            number = f"{start}-{end}"

            break

    if not number:
        debug('Number not a combo number, using volume number')
        number = int(record['series_index'])

    return number


def get_series(record, in_number):
    if 'series' in record.keys():
        debug('Series name', 3)
        if record['series'].lower() in record['title'].lower():
            debug('Found name == series', 3)
            title = f"Volume {in_number}"
            series = record['series']
        else:
            debug('Found name != series', 3)
            title = record['title']
            series = record['series']
    else:
        debug('Non-series name', 3)
        title = f"Volume {in_number}"
        series = record['title']

    return title, series


def get_today_list(raw_calibre):
    tmp_list = []

    today = date.today()
    debug(f"Today's date: {today}", 2)
    for item in raw_calibre:
        debug(f"Checking {raw_calibre[item]['title']}", 3)
        debug(f"Timestamp: {raw_calibre[item]['timestamp']}", 3)
        timestamp = datetime.strptime(raw_calibre[item]['timestamp'], "%Y-%m-%dT%H:%M:%S+00:00").date()
        debug(f"Conversion timestamp: {timestamp}", 3)
        if timestamp >= today:
            debug(f"Found {raw_calibre[item]['title']}", 2)
            for format in raw_calibre[item]['formats']:
                if ".epub" in format:
                    tmp_list.append(format)

    debug(f"Found {len(tmp_list)} mangas", 1)
    debug(f"Item list: {tmp_list}", 3)
    return tmp_list


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=SortingHelpFormatter)
    parser.add_argument('-d', '--dry_run', action='store_true', required=False,
                        help='Dry run only, don\'t actually create anything')
    parser.add_argument('-l', '--debug_level', type=int, choices=[1, 2, 3], help='Set debug level (enabled debugging)')
    parser.add_argument('-t', '--temp_dir', required=False, help='Temporary folder to use when extracting manga')
    parser.add_argument('-k', '--skip_komga', required=False, action='store_true',
                        help="Don't check existing komga entry")
    parser.add_argument('-p', '--password', required=False, default='cbz_converter', help='Komga Password')
    parser.add_argument('--publisher', required=False, default='all', help='Publisher to convert')
    parser.add_argument('--purchase', required=False, default='all', help='Purchase location to convert')
    parser.add_argument('-u', '--user', required=False, default='cbz_converter', help='Komga Username')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-m', '--manga', required=False, help='Single manga to convert')
    group.add_argument('-r', '--root_folder', required=False, help='Root folder of manga to convert')
    group.add_argument('--today', required=False, action='store_true', help='Only convert manga added today')
    return parser.parse_args()


def reorder(directory, cover_image):
    debug('Beginning image shuffle', 3)

    debug(f"Cover: {cover_image}", 3)

    full_image_list = sorted(os.listdir(Path(directory)))
    full_image_list.remove(cover_image)

    debug(f"Full image list: {full_image_list}", 3)

    new_name = ''

    for item in ['page', 'image', 'img']:
        if item not in full_image_list:
            debug(f"New name is {item}", 3)
            new_name = item
            break
        else:
            debug(f"{item} already in names")

    if not new_name:
        debug('All image permutations used', 3)
        return False

    debug(f"New name: {new_name}")
    for item in full_image_list:
        debug(f"o: {item}, n: {new_name}{item}", 3)
        shutil.move(Path(directory).joinpath(item), Path(directory).joinpath(f"{new_name}{item}"))

    full_image_list = sorted(os.listdir(Path(directory)))
    full_image_list.remove(cover_image)

    debug(f"Full image list after move: {full_image_list}", 3)

    new_first_file = full_image_list[1]
    debug(f"New first file: {new_first_file}")

    return new_first_file


if __name__ == '__main__':
    args = parse_args()

    if args.debug_level:
        DEBUG = True
        debug_level = args.debug_level
        debug(f"Set debug level to: {debug_level}")

    if args.dry_run:
        dry_run = args.dry_run
        debug(f"Set dry run to: {dry_run}")
    else:
        dry_run = False

    if args.skip_komga:
        skip_komga = args.skip_komga
        debug(f"Set skip komga to: {skip_komga}")

    debug('Dumping Calibre data')
    calibre = dump_calibre()

    if args.root_folder:
        debug('Running multiple folder conversion', 2)
        if library_path not in args.root_folder:
            folder_path = Path(library_path).joinpath(args.root_folder)
        else:
            folder_path = library_path
        debug(f"Looking in folder: {folder_path}", 3)
        files = list(Path(folder_path).rglob("*.epub"))
        debug(f"Found files: {files}", 3)
        for file in sorted(files):
            convert_manga(Path(file).as_posix(), calibre, args.publisher, args.purchase, args.user, args.password,
                          dry_run)
    elif args.today:
        debug('Running today conversion', 2)
        files = get_today_list(calibre)
        for file in sorted(files):
            convert_manga(Path(file).as_posix(), calibre, args.publisher, args.purchase, args.user, args.password,
                          dry_run)
