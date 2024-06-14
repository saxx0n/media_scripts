# media_scripts
General purpose scripts to handle media


- convert_for_komga.py
  - When I switched from a kobo to a tablet for reading comics/manga, I found it really annoying to have to manually convert data into an easy to read format.  Enter the free too Komga.  Only, none of my epubs were setup in a way to import directly and NOT have to rebuild all the metadata.  That would have sucked, so I wrote a python script to take the contents of my calibre library, walk it, make sure it wasnt already in komga, then extract the images from the epub, do a little magic to get a working cover (if needed), generate a ComicInfo.xml with the metadata dump it to disk in the folder-structure it needed.
  - Still is very ineffecient in how it checks Komga
  - Issues with cover detection sometimes
  - Special characters and the Komga API create issues, thus the hard-coded series replacements
- copy_books.py
  - For reasons that are not at all important or relevant, I found a need to copy books off my tablet to my local computer.  This was a quick script I wrote to use ADB to do that, and only extract out the files, without all the excessive folder layouts.
- flac_convert.py
  - I found my old iPod and decided to see if I could get it working again with a larger flash-card inside.  Turns out iPods can't handle FLAC, and most of my music was encoded as it.  This was a quick and dirty script to turn all my music into Apple lossless format which it could read.