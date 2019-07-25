import os
import shutil

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

if __name__ == "__main__":
    ROOT_DIRECTORY = r"C:/Projects/MijnKind/MyChild/website/"
    FILE_TO_DELETE = os.path.join(ROOT_DIRECTORY, "export.csv")
    FOLDER_TO_DELETE = os.path.join(ROOT_DIRECTORY, "template/photos/")

    if os.path.exists(FILE_TO_DELETE):
        os.remove(FILE_TO_DELETE)

    if os.path.exists(FOLDER_TO_DELETE):
        shutil.rmtree(FOLDER_TO_DELETE)

    process = CrawlerProcess(get_project_settings())
    process.crawl("mychild")
    process.start()
