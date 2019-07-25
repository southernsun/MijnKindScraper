# TODO: parse main page, as it contains data as well. not just the XHR responses?

import scrapy
import logging

from scrapy import FormRequest, Selector
from urllib.parse import urlparse

from scrapy.spidermiddlewares.httperror import HttpError
from twisted.internet.error import DNSLookupError, TCPTimedOutError
from scrapy.utils.log import configure_logging
from MyChild.Scraper.items import ChildItem, RawMainPageResponse, StoryThumbnail, Story, Figure, \
    Reaction
from enum import Enum

configure_logging(install_root_handler=False)
logging.basicConfig(
    filename='C:/Projects/MijnKind/MyChild/website/log.txt',
    filemode='w+',
    format=u'%(asctime)-s %(levelname)s [%(name)s]: %(message)s',
    level=logging.INFO
)

# TODO: CHANGE USERNAME / PASSWORD.

USERNAME = 'USERNAME'
PASSWORD = 'PASSWORD'

MAX_NUMBER_OF_XHR_REQUESTS = 10
STOP_AFTER_SPECIFIC_NUMBER_OF_XHR_REQUESTS = False


class MijnKindType(Enum):
    STORY_THUMBNAIL = 1
    STORY = 2
    FIGURE = 3
    REACTION = 4
    EMPTY = 5
    UNKNOWN = 6


class MyChildSpider(scrapy.Spider):
    name = "mychild"
    start_urls = ['https://mijnkind.partou.nl']

    def __init__(self):
        self.id_number = 0
        self.xhr_increment = 0
        self.previous_ids = []

        # set scrapy log level (setting in settings.py doesn't seem to have the expected behavior)
        logging.getLogger('scrapy').setLevel(logging.INFO)

    def parse(self, response):
        self.id_number = urlparse(response.url).query

        login_url = \
            'https://login.digdag.nl/partououd/ouder?%PARAM%-1.IFormSubmitListener-form'\
                .replace('%PARAM%', self.id_number)

        return [FormRequest.from_response(
            response,
            url=login_url,
            formdata=
            {
                'loginpanel:gebruikersnaam': USERNAME,
                'loginpanel:wachtwoord': PASSWORD,
                'loginpanel:rememberme': 'False',
                'loginpanel:inloggen': 'x',
            },
            callback=self.after_login)]

    def after_login(self, response):
        if "Je gebruikersnaam en/of wachtwoord is onjuist, niet ingevuld of je account is inactief" in response.text:
            self.logger.error("Login failed")
            return None
        else:
            return self.parse_mainpage(response)

    def parse_mainpage(self, response):
        # parse mainpage
        text = response.text
        selector = Selector(text=text)
        components = selector.xpath("//ul[contains(@class, 'stories')]/li")

        for component in components:
            bam = component.extract()
            selector = Selector(text=bam)

            component_id = selector.xpath("/html/body//@id").extract_first()
            mijnkindtype = self.determine_mijnkindtype(selector, "/html/body/")
            raw_data = selector.xpath('/html/body/li').extract_first()

            yield from self.ParseMijnKindType(component_id, mijnkindtype, raw_data)

        yield RawMainPageResponse(
            raw_data=response.text
        )

        for child in response.xpath("//div[contains(@class, 'filter-child-wrapper')]/div/ul/li"):
            yield ChildItem(
                name=child.xpath(".//a/text()[2]").extract(),
                image=child.xpath(".//a/img/@data-original").extract_first()
            )

        for req in self.parse_xhr_request(response):
            yield req

    def parse_xhr_request(self, response):
        if self.xhr_increment != 0:
            # NOTE: Each request contains stories and story thumbnails, while previous story thumbnails are repeated
            # in proceeding requests, stories are as wel...

            self.logger.info(" xhr_increment: {}".format(self.xhr_increment))

            text = response.text
            text_without_cdata = text.replace("<![CDATA[", "").replace("]]>", "")
            selector = Selector(text=text_without_cdata)

            components = selector.xpath('/html/body/ajax-response/component')

            for component in components:
                component_id = component.xpath(".//ancestor::component/@id").extract_first()
                mijnkindtype = self.determine_mijnkindtype(component)
                raw_data = component.xpath(".//ancestor::component").extract_first()

                yield from self.ParseMijnKindType(component_id, mijnkindtype, raw_data)

            if STOP_AFTER_SPECIFIC_NUMBER_OF_XHR_REQUESTS and self.xhr_increment == MAX_NUMBER_OF_XHR_REQUESTS:
                return

            all_ids = scrapy.selector.Selector(text=text.replace('<![CDATA[', '').replace(']]>', '')).xpath("//component/@id").extract()

            if sorted(self.previous_ids) == sorted(all_ids):
                # end is reached
                return
            else:
                self.previous_ids = all_ids

        self.xhr_increment += 1

        xhr_url = "https://mijnkind.partou.nl/dagboek?%PARAM%-%WHATEVER%.IBehaviorListener.0-lazyloader"\
            .replace('%PARAM%', self.id_number).replace('%WHATEVER%', '1')

        yield FormRequest(url=xhr_url,
                          method="POST",
                          headers={
                              'Accept': 'application/xml, text/xml, */*; q=0.01',
                              'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                              'Wicket-Ajax': 'true',
                              'Wicket-Ajax-BaseURL': 'dagboek?0',
                              'X-Requested-With': 'XMLHttpRequest',
                              'Referer': 'https://mijnkind.partou.nl/dagboek?0',
                              'Origin': 'https://mijnkind.partou.nl',
                              'Host': 'mijnkind.partou.nl',
                              'Accept-Language': 'en-US,en;q=0.9,fr;q=0.8,nl;q=0.7',
                              'Accept-Encoding': 'gzip, deflate, br',
                          },
                          formdata={
                              'argCount': '0',
                              'methodName': 'fetch',
                              'callId': '{}'.format(self.xhr_increment),
                          },
                          cookies=[
                              {'name': 'piwik_tracking_enabled',
                               'value': 'true',
                               'domain': '.partou.nl',
                               'path': '/'},
                          ],
                          callback=self.parse_xhr_request,
                          errback=self.errback_httpbin,
                          meta={'dont_merge_cookies': False})

    def ParseMijnKindType(self, component_id, mijnkindtype, raw_data):
        if mijnkindtype == MijnKindType.STORY_THUMBNAIL:
            yield StoryThumbnail(
                id=component_id,
                type=str(mijnkindtype),
                raw_data=raw_data
            )
        if mijnkindtype == MijnKindType.STORY:
            yield Story(
                id=component_id,
                type=str(mijnkindtype),
                raw_data=raw_data
            )
        if mijnkindtype == MijnKindType.FIGURE:
            yield Figure(
                id=component_id,
                type=str(mijnkindtype),
                raw_data=raw_data
            )
        if mijnkindtype == MijnKindType.REACTION:
            yield Reaction(
                id=component_id,
                type=str(mijnkindtype),
                raw_data=raw_data
            )
        if mijnkindtype == MijnKindType.EMPTY:
            # do nothing
            pass
        if mijnkindtype == MijnKindType.UNKNOWN:
            logging.warning(" ! Unknown component type: {}".format(raw_data))

    def determine_mijnkindtype(self, component, prefix='./'):
        story_thumbnail = component.xpath(prefix + "div/ul[@class='story-thumbnails']/ancestor::div").extract()

        if story_thumbnail:
            return MijnKindType.STORY_THUMBNAIL

        story = component.xpath(prefix + "li[@class='story']").extract()

        if story:
            return MijnKindType.STORY

        figure = component.xpath(prefix + "div[@id]/figure[@id]/ancestor::div").extract()

        if figure:
            return MijnKindType.FIGURE

        reaction = component.xpath(prefix + "li[@id and not(@class)]/div/a[@class='user-thumbnail']/ancestor::li").extract()

        if reaction:
            return MijnKindType.REACTION

        empty_component = component.xpath(prefix + "li[@id and @style='display:none']").extract()

        if empty_component:
            return MijnKindType.EMPTY

        return MijnKindType.UNKNOWN

    def errback_httpbin(self, failure):
        self.logger.error(repr(failure))

        if failure.check(HttpError):
            response = failure.value.response
            self.logger.error('HttpError on %s', response.url)

        elif failure.check(DNSLookupError):
            request = failure.request
            self.logger.error('DNSLookupError on %s', request.url)

        elif failure.check(TimeoutError, TCPTimedOutError):
            request = failure.request
            self.logger.error('TimeoutError on %s', request.url)
