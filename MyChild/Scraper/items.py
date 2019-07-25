# -*- coding: utf-8 -*-

# Define here the models for your scraped items
#
# See documentation in:
# https://doc.scrapy.org/en/latest/topics/items.html

import scrapy


class ChildItem(scrapy.Item):
    name = scrapy.Field()
    image = scrapy.Field()


class RawMainPageResponse(scrapy.Item):
    raw_data = scrapy.Field()


class MijnKindItem(scrapy.Item):
    id = scrapy.Field()
    type = scrapy.Field()
    raw_data = scrapy.Field()
    image_urls = scrapy.Field()
    images = scrapy.Field()


class StoryThumbnail(MijnKindItem):
    date = scrapy.Field()
    pass


class Story(MijnKindItem):
    datetime = scrapy.Field()
    pass


class Figure(MijnKindItem):
    pass


class Reaction(MijnKindItem):
    datetime = scrapy.Field()
    pass
