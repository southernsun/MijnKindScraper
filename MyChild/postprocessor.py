# from __future__ import unicode_literals

import jsonlines
import codecs
import logging
import datetime
import locale
import threading
import os
import subprocess

from contextlib import contextmanager
from scrapy.selector import Selector

LOCALE_LOCK = threading.Lock()

PHOTO_URI_PATH = r"photos/"
FILENAME = r"C:/Projects/MijnKind/MyChild/website/export.csv"
DIRECTORY = r"C:\Projects\MijnKind\MyChild\website\template\\"
FILENAME_TEMPLATE = DIRECTORY + "template.htm"
FILENAME_RESULT = DIRECTORY + "dagboek.htm"
FILENAME_PDF_RESULT = DIRECTORY + "dagboek.pdf"

HIDE_POEP_REPORT = False
USE_LOCAL_IMAGE_REFERENCE = True
FROM_OLD_TO_NEW = False
GENERATE_PDF = True


def execute():
    if os.path.exists(FILENAME_PDF_RESULT):
        os.remove(FILENAME_PDF_RESULT)

    all_data = read_all_data()
    stories, images = get_stories_and_images(all_data)
    write_data(all_data, stories, images)

    if GENERATE_PDF:
        subprocess.call([r'C:\Projects\MijnKind\ChromeHtmlToPdf\ChromeHtmlToPdf.exe', '--input', FILENAME_RESULT, '--output', FILENAME_PDF_RESULT])


def read_all_data():
    fp = open(FILENAME, "rb")
    reader = jsonlines.Reader(fp)

    all_data = []

    for obj in reader:
        if 'id' in obj:
            all_data.append(obj)
    reader.close()
    fp.close()

    return all_data


def get_stories_and_images(all_data):
    stories = []
    images = []

    for data in all_data:
        if data['type'] == "MijnKindType.STORY":
            if HIDE_POEP_REPORT and "story-dayrhythm" in data['raw_data']:
                continue
            else:
                stories.append(data)

        if data['images']:
            images.append(data['images'])

    if FROM_OLD_TO_NEW:
        stories.reverse()

    return stories, images


def write_data(all_data, stories, images):
    with codecs.open(FILENAME_TEMPLATE, "r", "utf-8") as file:
        data = file.read()

    stories_as_html = ""

    for story in stories:
        logging.info("item: {}".format(story['id']))

        include_referenced_items(all_data, story)

        rewrite_date(story)

        stories_as_html += story['raw_data']

    if USE_LOCAL_IMAGE_REFERENCE:
        for image_coll in images:
            for image in image_coll:
                image_url = image['url']
                image_path = image['path']

                # for testing purposes
                find = 'https://8e89940265ce0eb29f60-1f4c39e6cbee6f7363c17e4771acdeaa.ssl.cf3.rackcdn.com/48620000/images/27ef5e7078c411e5873dab71246e332b/small/34/13477078c411e59f56b723367a3412.jpeg'

                if find in image_url:
                    logging.info("found!")
                    if find in stories_as_html:
                        logging.info('found again!')
                # end

                stories_as_html = stories_as_html.replace(image_url, PHOTO_URI_PATH + image_path)

    data = data.replace('%DATA%', stories_as_html)

    file = codecs.open(FILENAME_RESULT, "w", "utf-8")
    file.write(data)
    file.close()


def include_referenced_items(all_data, story):
    for item in all_data[:]:
        if item['id'] in story['raw_data'] and item['id'] != story['id']:
            logging.info("found: {}, type: {}".format(item['id'], item['type']))
            selector = Selector(text=story['raw_data'])
            element_to_load = selector.xpath(".//div[@id='" + item['id'] + "' and @style='display:none']").extract_first()
            reaction_to_load = selector.xpath(".//form[@id and @style='display:none']/@id").extract_first()
            if element_to_load:
                story['raw_data'] = story['raw_data'].replace(element_to_load, item['raw_data'])
            if reaction_to_load:
                id = 'id{:02x}'.format(int(reaction_to_load[2:], 16) + 1)
                for comment in all_data:
                    if comment['type'] == 'MijnKindType.REACTION' and comment['id'] == id:
                        logging.info("found reaction.")
                        reaction_element = selector.xpath(".//form[@id='" + reaction_to_load + "' and @style='display:none']").extract_first()
                        story['raw_data'] = story['raw_data'].replace("</ul>\n\t\t"+reaction_element, comment['raw_data'] +"</ul>\n\t\t"+reaction_element)


@contextmanager
def setlocale(name):
    with LOCALE_LOCK:
        saved = locale.setlocale(locale.LC_ALL)
        try:
            yield locale.setlocale(locale.LC_ALL, name)
        finally:
            locale.setlocale(locale.LC_ALL, saved)


def rewrite_date(story):
    raw_data = story['raw_data']
    selector = Selector(text=raw_data)

    for datetime_str in selector.xpath(".//time/text()").extract():
        datetime_str2 = datetime_str[:-5] + datetime_str[-5:].replace(":", "")
        datetime_obj = datetime.datetime.strptime(datetime_str2, "%Y-%m-%dT%H:%M:%S.%f%z")

        with setlocale('nl_NL'):
            story['raw_data'] = story['raw_data'].replace(datetime_str, datetime_obj.strftime("%A %d %B %Y - %H:%M"))
