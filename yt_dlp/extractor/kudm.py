import time
import urllib

from .common import InfoExtractor
from ..utils import ExtractorError


# http://www.kudm.net/ has two sites:
# * https://www.sbdm.net/
# * https://www.gqdm.net/


class SbdmIE(InfoExtractor):
    _VALID_URL = r'(?x)(?P<season>https?://www\.sbdm\.net/[^/]+/\d+)/v.html\?(?P<id>\d+-\d+-\d+)'

    _TESTS = [{
        'url': 'https://www.sbdm.net/LADM/7025/v.html?7025-0-11',
        'info_dict': {
            'id': '7025-0-11',
            'ext': 'mp4',
            'season': '迷途貓 OVERRUN',
            'title': '迷途貓 OVERRUN 第12集BD版',
        },
    }]

    def _real_extract(self, url):
        video_id = self._match_id(url)

        mobj = self._match_valid_url(url)
        season_url = mobj.group('season')
        season_url_path = url[len('https://www.sbdm.net'):]

        chrome_wait_timeout = self.get_param('selenium_browner_timeout', 20)
        headless = self.get_param('selenium_browner_headless', True)
        proxy = self.get_param('proxy', None)

        from ..selenium_container import SeleniumContainer
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By

        self.to_screen(f'start chrome to query video page...')
        with SeleniumContainer(
            headless=headless,
            close_log_callback=lambda: self.to_screen('Quit chrome and cleanup temp profile...')
        ) as engine:
            engine.start(proxy=proxy)

            self.to_screen('query season page...')
            engine.load(season_url)

            season_name = engine.find_element(By.TAG_NAME, 'h1').get_attribute('innerText')

            season_page = engine.driver.page_source

            title_pattern = r'title="(?P<title>[^"]+)"\s+href="' + season_url_path.replace('?', r'\?')
            title = self._search_regex(title_pattern, season_page, 'title')
            title = f'{season_name} {title}'

            self.to_screen('query video page...')
            engine.load(url)

            iframe_e = engine.wait(chrome_wait_timeout).until(
                EC.presence_of_element_located((By.ID, 'cciframe'))
            )

            engine.driver.switch_to.frame(iframe_e)

            iframe_e = engine.wait(chrome_wait_timeout).until(
                EC.presence_of_element_located((By.ID, 'icc'))
            )

            engine.driver.switch_to.frame(iframe_e)

            video_e = engine.wait(chrome_wait_timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, 'video'))
            )

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

            video_url = None
            engine.extract_network()
            for url in engine.response_updated_key_list:
                if '.m3u8' in url:
                    print(f'found .m3u8: {url}')
                    video_url = url

            self.to_screen('Check chrome media-internals info ...')
            fmt_info = engine.parse_video_info()

            if '.m3u8' in video_url:
                return {
                    'id': video_id,
                    'title': title,
                    '_type': 'video',
                    'formats': [{
                        'url': video_url,
                        'protocol': 'm3u8_fake_header',
                        'ext': 'mp4',
                        **fmt_info
                        }]
                }

        raise ExtractorError(f'unknown format {url}')


class GqdmIE(InfoExtractor):
    _VALID_URL = r'(?x)https?://www\.(gqdm|sbdm)\.net/index.php/vod/play/id/(?P<series_id>\d+)/sid/(?P<sid>\d+)/nid/(?P<nid>\d+).html'

    # sometimes sbdm act as gqdm

    _TESTS = [{
        'url': 'https://www.gqdm.net/index.php/vod/play/id/538/sid/1/nid/3.html',
        'info_dict': {
            'id': '538_1_3',
            'ext': 'mp4',
            'season': '碧蓝航线',
            'title': '碧蓝航线 第3集BD无修',
        },
    }]

    def _real_extract(self, url):
        mobj = self._match_valid_url(url)
        series_id, sid, nid = mobj.group('series_id'), mobj.group('sid'), mobj.group('nid')
        video_id = f'{series_id}_{sid}_{nid}'

        webpage = self._download_webpage(url, video_id)
        season_title = self._search_regex(r'<h2 class="title[^>]+>(?P<season_title>[^<]+)</h2>', webpage, 'season_title')

        url_parsed = urllib.parse.urlparse(url)
        title = self._search_regex(f'<a href="{url_parsed.path}">(?P<title>[^<]+)</a>', webpage, 'title')

        play_info = self._search_json(r'player_aaaa\s*=', webpage, 'play_info', video_id, default={})

        return {
            'id': video_id,
            'season': season_title,
            'title': f'{season_title} {title}',
            'formats': [{
                'url': play_info['url'],
                'protocol': 'm3u8_fake_header',
                'ext': 'mp4',
            }]
        }
