import json
import re
import time

from .common import InfoExtractor
from ..compat import compat_urllib_parse_urlparse
from ..utils import ExtractorError, int_or_none, float_or_none


class XiaoeknownIE(InfoExtractor):
    _VALID_URL = r'(?x)https?://[^.]+\.h5\.xiaoeknow\.com/v1/course/video/(?P<id>[^?]+)'

    def _real_extract(self, url):
        video_id = self._match_id(url)

        chrome_wait_timeout = self.get_param('selenium_browner_timeout', 20)
        headless = self.get_param('selenium_browner_headless', False)

        from ..selenium_container import SeleniumContainer
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By

        self.to_screen(f'start chrome to query video page...')
        with SeleniumContainer(
            headless=headless,
            close_log_callback=lambda: self.to_screen('Quit chrome and cleanup temp profile...')
        ) as engine:
            engine.start()

            if self.get_param('cookiesfrombrowser'):
                engine.load(url)
                engine.load_cookies(self._downloader.cookiejar, '.xiaoeknow.com')

            engine.load(url)

            video_e = engine.wait(chrome_wait_timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, 'video'))
            )

            title = engine.find_element(By.CLASS_NAME, 'detail-title').get_attribute('innerText').strip()

            info_dict = {
                    'id': video_id,
                    'title': title,
                    '_type': 'video',
                }

            self.to_screen('play video to detect video metadata ...')
            engine.execute_script("document.getElementsByTagName('video')[0].volume = 0")
            engine.execute_script("document.getElementsByTagName('video')[0].muted = true")
            engine.execute_script("document.getElementsByTagName('video')[0].play()")

            videoHeight, videoWidth = None, None
            for _ in range(chrome_wait_timeout):
                videoHeight = engine.execute_script("return document.getElementsByTagName('video')[0].videoHeight")
                videoWidth = engine.execute_script("return document.getElementsByTagName('video')[0].videoWidth")

                if videoHeight == 0:
                    videoHeight, videoWidth = None, None
                    time.sleep(1)
                else:
                    break

            engine.extract_network()

            video_urls = [url for url in engine.response_updated_key_list if '.ts' in url]

            def parse_pattern1(url_last):
                pattern = re.compile(r'(?P<head>https://encrypt-k-vod.xet.tech/[^/]+/[^/]+/v\.[a-z\d]+)_(?P<idx>\d+)\.ts(?P<tail>.*)')
                mobj = pattern.match(url_last)
                if mobj:
                    url_head, url_tail = mobj.group('head'), mobj.group('tail')
                    return {
                        'url': f'{url_head}.m3u8{url_tail}',
                    }
                return None

            def parse_pattern2(url_last):
                pattern = re.compile(r'(?P<head>https://encrypt-k-vod.xet.tech/[^/]+/[^/]+/drm/v\.[a-z\d]+)(:?_\d+)?\.ts\?(?:start=\d+&end=\d+)(?P<tail>.*)')
                mobj = pattern.match(url_last)
                if mobj:
                    url_head, url_tail = mobj.group('head'), mobj.group('tail')
                    return {
                        'url': f'{url_head}.m3u8?{url_tail}',
                    }
                return None

            fmt = parse_pattern1(video_urls[0]) or parse_pattern2(video_urls[0])

            self.to_screen('Check chrome media-internals info ...')
            video_fmt = engine.parse_video_info()

            fmt_info = {
                **fmt,
                **video_fmt,
                'ext': 'mp4',
                'protocol': 'm3u8_native',
            }

        return {
            **info_dict,
            'formats': [fmt_info],
            'http_headers': {
                'Referer': f'https://{compat_urllib_parse_urlparse(url).hostname}/'
            }
        }
