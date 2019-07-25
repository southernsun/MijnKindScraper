# -*- coding: utf-8 -*-

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://doc.scrapy.org/en/latest/topics/item-pipeline.html
import datetime
import locale
import threading
import logging

from MyChild.Scraper.items import ChildItem, MijnKindItem, Story, StoryThumbnail, Reaction, Figure
from scrapy.selector import Selector
from contextlib import contextmanager
from scrapy.exceptions import DropItem

LOCALE_LOCK = threading.Lock()


@contextmanager
def setlocale(name):
    with LOCALE_LOCK:
        saved = locale.setlocale(locale.LC_ALL)
        try:
            yield locale.setlocale(locale.LC_ALL, name)
        finally:
            locale.setlocale(locale.LC_ALL, saved)


class ChildPipeline(object):
    @staticmethod
    def process_item(item, spider):
        if isinstance(item, ChildItem):
            item['name'] = item['name'][0].replace("\t", "").replace("\r", "").replace("\n", "")

        return item


class DuplicatesPipeline(object):
    def __init__(self):
        self.ids_seen = set()

    def process_item(self, item, spider):
        if isinstance(item, MijnKindItem):
            if item['id'] in self.ids_seen:
                # clean raw_data to prevent utf-8 encoded errors from being thrown when exception is raised
                # as it prints out the whole item.
                item['raw_data'] = ""
                raise DropItem("Duplicate item found: %s" % item['id'])
            else:
                self.ids_seen.add(item['id'])
                return item

        return item


class DeterminePostTimePipeline(object):
    @staticmethod
    def process_item(item, spider):
        if isinstance(item, Story) or isinstance(item, Reaction):
            selector = Selector(text=item['raw_data'])
            datetime_str = selector.xpath(".//time/text()").extract_first()
            item['datetime'] = datetime_str[:-5] + datetime_str[-5:].replace(":", "")
            return item

        if isinstance(item, StoryThumbnail):
            selector = Selector(text=item['raw_data'])
            date_str = selector.xpath(".//ul/li/a/@title").extract_first()
            with setlocale('nl_NL'):
                item['date'] = datetime.datetime.strptime(date_str, '%d %B %Y').strftime('%Y%m%d')
            return item

        return item


class GetImagesPipeline(object):
    @staticmethod
    def process_item(item, spider):
        if isinstance(item, MijnKindItem):
            selector = Selector(text=item['raw_data'])

            images = []
            item['image_urls'] = []

            for image in selector.xpath('.//img/@data-original').extract():
                image = image.strip('\'')

                if image.startswith('http'):
                    images.append(image)

            for image in selector.xpath('.//a/@href').extract():
                image = image.strip('\'')

                if image.endswith('.jpg'):
                    images.append(image)

            for image in selector.xpath('.//img/@src').extract():
                image = image.strip('\'')

                if image.endswith('.jpg'):
                    images.append(image)

                if image.endswith('.jpeg'):
                    images.append(image)

            logging.info("found {} images in component".format(len(images)))

            for image in images:
                if image not in item['image_urls']:
                    item['image_urls'].append(image)

            return item

        return item


class RemoveComponentElementFromRawData(object):
    @staticmethod
    def process_item(item, spider):
        if isinstance(item, MijnKindItem):
            if '<component' in item['raw_data']:
                selector = Selector(text=item['raw_data'])

                if isinstance(item, Story):
                    item['raw_data'] = selector.xpath('/html/body/component/li').extract_first()
                if isinstance(item, Reaction):
                    item['raw_data'] = selector.xpath('/html/body/component/li').extract_first()
                if isinstance(item, StoryThumbnail):
                    item['raw_data'] = selector.xpath('/html/body/component/div').extract_first()
                if isinstance(item, Figure):
                    item['raw_data'] = selector.xpath('/html/body/component/div').extract_first()
                return item

        return item