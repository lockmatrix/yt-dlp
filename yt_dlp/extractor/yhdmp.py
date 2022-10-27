import json
import re
import time

from .common import InfoExtractor
from ..utils import ExtractorError, int_or_none, float_or_none


class YhdmpIE(InfoExtractor):
    _VALID_URL = r'(?x)https?://(?:www\.yhdmp\.cc/vp/)(?P<id>\d+-\d+-\d+)\.html'

    _TESTS = [{
        #  yhdmp_obfuscate_m3u8
        'url': 'https://www.yhdmp.cc/vp/22216-2-0.html',
        'info_dict': {
            'id': '22216-2-0',
            'ext': 'mp4',
            'title': '异世界舅舅 第1集',
        },
    }, {
        'url': 'https://www.yhdmp.cc/vp/22096-1-9.html',
        'info_dict': {
            'id': '22096-1-9',
            'ext': 'mp4',
            'title': '爱书的下克上～为了成为图书管理员不择手段～ 第三季 第36集',
        },
    }]

    def _real_extract(self, url):
        video_id = self._match_id(url)

        # yhdmp obfuscate video info, use headless browner to run it

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

            engine.load(url)

            iframe_e = engine.wait(chrome_wait_timeout).until(
                EC.presence_of_element_located((By.ID, 'yh_playfram'))
            )

            title = engine.find_element(By.TAG_NAME, 'title').get_attribute('innerText')
            title_mobj = re.match(r'(?P<t>.*?)\—在线播放\—樱花动漫(\(P\))?', title)
            if title_mobj.group('t'):
                title = title_mobj.group('t')

            engine.driver.switch_to.frame(iframe_e)
            video_e = engine.wait(chrome_wait_timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, 'video'))
            )

            info_dict = {
                    'id': video_id,
                    'title': title,
                    '_type': 'video',
                }

            video_url = video_e.get_attribute('src')

            self.to_screen('play video to detect video metadata ...')
            engine.execute_script("document.getElementsByTagName('video')[0].volume = 0")
            engine.execute_script("document.getElementsByTagName('video')[0].muted = true")
            engine.execute_script("document.getElementsByTagName('video')[0].playbackRate=16")
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
            for url in engine.response_updated_key_list:
                if '.m3u8' in url:
                    video_url = url

            self.to_screen('Check chrome media-internals info ...')
            fmt_info = engine.parse_video_info()

            if '.mp4?' in video_url:
                return {
                    **info_dict,
                    'formats': [{'url': video_url, **fmt_info}],
                }
            if '.m3u8' in video_url:
                return {
                    **info_dict,
                    'formats': [{
                        'url': video_url,
                        'protocol': 'm3u8_fake_header',
                        'ext': 'mp4',
                        **fmt_info
                        }]
                }
            if '?dpvt=' in video_url:
                return {
                    **info_dict,
                    'formats': [{'url': video_url, 'ext': 'mp4', **fmt_info}],
                }

        raise ExtractorError(f'unknown format {url}')


class NtyouIE(InfoExtractor):
    _VALID_URL = r'(?x)https?://www\.ntyou\.cc/play/(?P<id>\d+-\d+-\d+)\.html'

    _TESTS = [{
        'url': 'http://www.ntyou.cc/play/4495-1-10.html',
        'info_dict': {
            'id': '4495-1-10',
            'ext': 'mp4',
            'title': '银河英雄传说：全新命题 策谋',
        },
    }]


    def _real_extract(self, url):
        video_id = self._match_id(url)

        # obfuscate video info, use headless browner to run it

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

            engine.load(url)

            iframe_e = engine.wait(chrome_wait_timeout).until(
                EC.presence_of_element_located((By.ID, 'playleft'))
            )

            title = engine.find_element(By.TAG_NAME, 'h4').get_attribute('innerText')
            episode_title = engine.find_element(By.CLASS_NAME, 'active-play').get_attribute('innerText')
            title += ' ' + episode_title

            iframe_e = iframe_e.find_element(By.TAG_NAME, 'iframe')

            engine.driver.switch_to.frame(iframe_e)
            video_e = engine.wait(chrome_wait_timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, 'video'))
            )

            info_dict = {
                    'id': video_id,
                    'title': title,
                    '_type': 'video',
                }

            video_url = video_e.get_attribute('src')

            fmt = {'url': video_url}

            if 'mime_type=video_mp4' in video_url:
                fmt['ext'] = 'mp4'
            else:
                self.to_screen('guess ext -> mp4')
                fmt['ext'] = 'mp4'

            return {
                **info_dict,
                'formats': [fmt],
            }
