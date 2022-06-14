# -*- coding: utf-8 -*-

# ref: https://kodi.wiki/view/NFO_files/Episodes

import logging
import os
import re
import xml.etree.ElementTree as ET
import hashlib
from typing import Optional


cwd = u'.'
overwrite = False
outputEmptyElements = True
containers = [
    '.avchd',
    '.avi',
    '.flv', '.swf', '.f4v',
    '.mkv',
    '.mov', '.qt',
    '.mp4', '.m4p', '.m4v',
    '.mpg', '.mp2', '.mpeg', '.mpe', '.mpv',
    '.ogg',
    '.webm',
    '.wmv',
]
extraElements = [
    'plot',
    'credits',
    'aired',
    'userrating',
]
uniqueIdSource = 'path'
uniqueIdType = 'hashpath'
total = 0
skipped = []
written = []


class EpisodeEntity(object):

    def __init__(self):
        self._episodeTitle = None  # Optional[str]
        self._episodeNumber = None  # Optional[int]
        self._seasonNumber = None  # Optional[int]

    @property
    def episodeTitle(self) -> Optional[str]:
        return self._episodeTitle

    @episodeTitle.setter
    def episodeTitle(self, value) -> None:
        self._episodeTitle = str(value).strip() if value is not None else value

    @property
    def episodeNumber(self) -> Optional[int]:
        return self._episodeNumber

    @episodeNumber.setter
    def episodeNumber(self, value) -> None:
        self._episodeNumber = int(value) if value is not None else value

    @property
    def seasonNumber(self) -> Optional[int]:
        return self._seasonNumber

    @seasonNumber.setter
    def seasonNumber(self, value) -> None:
        self._seasonNumber = int(value) if value is not None else value


class EpisodeNfo(object):

    DECLARATION = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
    EXTENSION = '.nfo'

    def __init__(self, dirName: str = None, fileRoot: str = None,
                 fileExtension: str = None, emptyElements: bool = False,
                 extraElements: list = [], uniqueIdSource: str = 'path',
                 uniqueIdType: str = 'md5'):
        self.dirName = dirName
        self.fileRoot = fileRoot
        self.fileExtension = fileExtension
        self.emptyElements = emptyElements
        self.extraElements = extraElements
        self.uniqueIdSource = uniqueIdSource
        self.uniqueIdType = uniqueIdType
        self.indent = '  '
        self.episode = None  # Optional[EpisodeEntity]
        self.xmlTree = None  # Optional[ET]

    @property
    def basename(self) -> Optional[str]:
        if self.fileRoot is not None:
            return self.fileRoot + self.EXTENSION

    @property
    def path(self) -> str:
        return os.path.join(self.dirName, self.fileRoot + self.EXTENSION)

    def buildNfo(self) -> None:
        self.xmlTree = ET.Element('episodedetails')

        ET.SubElement(self.xmlTree, 'title').text = self.episode.episodeTitle

        if self.emptyElements or episode.seasonNumber is not None:
            ET.SubElement(self.xmlTree, 'season').text = str(
                episode.seasonNumber if episode.seasonNumber is not None
                else '')

        if self.emptyElements or episode.episodeNumber is not None:
            ET.SubElement(self.xmlTree, 'episode').text = str(
                episode.episodeNumber if episode.episodeNumber is not None
                else '')

        uniqueId = ET.SubElement(self.xmlTree, 'uniqueid')
        uniqueId.set('type', self.uniqueIdType)
        uniqueId.text = self.generateId()

        if self.emptyElements:
            for el in self.extraElements:
                ET.SubElement(self.xmlTree, el)

    def generateId(self) -> str:
        if self.uniqueIdSource == 'filename':
            source = self.fileRoot + self.fileExtension
        elif self.uniqueIdSource == 'absolute':
            source = os.path.abspath(os.path.join(self.dirName, self.fileRoot
                                                  + self.fileExtension))
        else:
            source = os.path.join(self.dirName, self.fileRoot
                                  + self.fileExtension)
        return hashlib.md5(source.encode('utf-8')).hexdigest()

    def export(self) -> None:
        if self.xmlTree is None:
            self.buildNfo()

        # Python 3.9 would support indentation and standalone argument. Sigh.
        self._prettify(self.xmlTree)
        xmlStr = self.DECLARATION + "\n" + ET.tostring(
            self.xmlTree,
            encoding='utf-8',
            short_empty_elements=False).decode('utf-8')
        print(xmlStr)
        # return

        try:
            with open(self.path, 'w') as outfile:
                outfile.write(xmlStr)
                written.append(self.path)
        except IOError:
            logging.warning("NFO export failure: %s", IOError)

    def _prettify(self, current: ET, parent: ET = None, index: int = -1,
                  depth: int = 0) -> None:
        # see: https://stackoverflow.com/a/65808327
        for i, node in enumerate(current):
            self._prettify(node, current, i, depth + 1)
        if parent is not None:
            if index == 0:
                parent.text = "\n" + ("  " * depth)
            else:
                parent[index - 1].tail = "\n" + ("  " * depth)
            if index == len(parent) - 1:
                current.tail = "\n" + ("  " * (depth - 1))


class DirectoryParser(object):

    REGEXES = [
        # 01. Description
        # 2-Description
        # 003 Description
        # 02Ignored
        r'^(?P<seasonNumber>\d+)',

        # Season 01
        # Chapter 2
        # Ignored 100
        r'\W+\s+(?P<seasonNumber>\d+)$',

        # Specials
        r'^(?P<seasonSpecials>Specials)',

        # Season 01: Description
        # Season 2 - Description
        # Chapter 030 Ignored
        r'^[Season|Lesson|Chapter|Part]\W+\s+(?P<seasonNumber>\d+)',
    ]  # type: list

    def __init__(self, directory: str) -> None:
        self.seasonNumber = None  # type: Optional[int]

        self._directory = None  # type: Optional[str]
        self.__regexesCompiled = []  # type: list

        self.compileRegexes(self.REGEXES, self.__regexesCompiled)
        self.directory(directory)

    def directory(self, value: str) -> None:
        self._directory = value
        self.parse()

    def compileRegexes(self, regexes: list, compiled: list) -> None:
        for regex in regexes:
            compiled.append(re.compile(regex, flags=re.IGNORECASE))

    def parse(self) -> None:
        self.seasonNumber = None
        for regex in self.__regexesCompiled:
            m = regex.match(self._directory)
            if m is not None:
                d = m.groupdict()
                if 'seasonNumber' in d:
                    self.seasonNumber = int(d['seasonNumber'])
                if 'seasonSpecials' in d:
                    self.seasonNumber = 0
                break


class FileParser(object):

    REGEXES = [
        # 1x01. Title
        # 2x15 - Title
        # 3x15 Title
        r'''
            ^(?P<seasonNumber>\d+)[-\.x](?P<episodeNumber>\d{2,})\W*\s*
            (?P<episodeTitle>.+)$
        ''',

        # 01. Title
        # 02 - Title
        # 03 Title
        r'^(?P<episodeNumber>\d{2,})\W*\s*(?P<episodeTitle>.+)$',

        # Name.S01E02.Title
        # Name - s01e02 - Title
        r'''
            s(?P<seasonNumber>\d{2,})e(?P<episodeNumber>\d{2,})\s?\W*\s*
            (?P<episodeTitle>.+)$
        ''',
        # r'(.+)$',
    ]  # type: list

    def __init__(self, file: str, episodeTitle: str = None,
                 seasonNumber: int = None) -> None:
        self.seasonNumber = seasonNumber  # type: Optional[int]
        self.episodeTitle = episodeTitle  # type: Optional[str]
        self.episodeNumber = None  # type: Optional[int]

        self._file = None  # type: Optional[str]
        self._seasonNumber = self.seasonNumber
        self._episodeTitle = self.episodeTitle
        self.__regexesCompiled = []  # type: list

        self.compileRegexes(self.REGEXES, self.__regexesCompiled)
        self.file(file)

    def file(self, value: str) -> None:
        self._file = value
        self.parse()

    def compileRegexes(self, regexes: list, compiled: list) -> None:
        for regex in regexes:
            compiled.append(re.compile(regex,
                                       flags=re.IGNORECASE | re.VERBOSE))

    def parse(self) -> None:
        # print(self._file)
        self.episodeTitle = self._episodeTitle
        self.episodeNumber = None
        self.seasonNumber = self._seasonNumber
        for regex in self.__regexesCompiled:
            m = regex.match(self._file)
            if m is not None:
                d = m.groupdict()
                if 'seasonNumber' in d:
                    self.seasonNumber = int(d['seasonNumber'])
                if 'episodeNumber' in d:
                    self.episodeNumber = int(d['episodeNumber'])
                if 'episodeTitle' in d:
                    self.episodeTitle = d['episodeTitle']
                break


# logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)

for root, dirs, files in os.walk(cwd):
    # print('------------------------: ' + os.path.basename(root))

    directoryParser = DirectoryParser(directory=os.path.basename(root))
    logging.debug('Season number: %s', directoryParser.seasonNumber)

    for file in sorted(files):
        fileRoot, fileExtension = os.path.splitext(file)

        if not len(fileExtension):
            logging.debug('Dotfile will not be processed: %s',
                          os.path.join(root, file))
            continue

        fileExtension = fileExtension.lower()
        if fileExtension == EpisodeNfo.EXTENSION:
            continue

        if fileExtension not in containers:
            logging.debug('File type not supported: %s',
                          os.path.join(root, file))
            continue

        nfo = EpisodeNfo(
            dirName=root,
            fileRoot=fileRoot,
            fileExtension=fileExtension,
            emptyElements=outputEmptyElements,
            extraElements=extraElements,
            uniqueIdSource=uniqueIdSource,
            uniqueIdType=uniqueIdType,
            )

        if not overwrite and nfo.basename in files:
            logging.debug('NFO file already exists: %s', nfo.path)
            skipped.append(nfo.path)
            continue

        fileParser = FileParser(file=fileRoot,
                                seasonNumber=directoryParser.seasonNumber,
                                episodeTitle=fileRoot)

        episode = EpisodeEntity()
        episode.episodeTitle = fileParser.episodeTitle
        episode.episodeNumber = fileParser.episodeNumber
        episode.seasonNumber = fileParser.seasonNumber

        nfo.episode = episode
        try:
            nfo.export()
            written.append(nfo.path)
        except IOError:
            logging.warning("NFO export failure: %s", IOError)
        total += 1


print("total: " + str(total))
print("skipped: " + str(len(skipped)))
print("written: " + str(len(written)))
