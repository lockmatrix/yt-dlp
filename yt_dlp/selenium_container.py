import base64
import collections
import json
import re
import time

from .utils import (
    int_or_none,
    traverse_obj,
    try_call,
)

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.common.by import By


class SeleniumContainer:
    def __init__(self, headless, close_log_callback=None):
        self.headless = headless
        self.driver = None
        self.close_log_callback = close_log_callback

        self.response_dict = collections.defaultdict(dict)
        self.request_id_data = collections.defaultdict(list)
        self.closed_request_id_set = set()
        self.response_updated_key_list = []

    def start(self):
        chrome_options = Options()
        chrome_options.add_argument('--log-level=3')
        chrome_options.add_argument("--disable-blink-features")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        # print(f'chrome path: {chrome_options.binary_location}')

        if self.headless:
            chrome_options.add_argument('--headless')

        prefs = {"profile.managed_default_content_settings": {'images': 2}}
        chrome_options.add_experimental_option("prefs", prefs)

        caps = DesiredCapabilities.CHROME
        caps['goog:loggingPrefs'] = {'performance': 'ALL'}

        self.driver = webdriver.Chrome(options=chrome_options, desired_capabilities=caps)

        self.driver.execute_cdp_cmd('Network.enable', {
            'maxResourceBufferSize': 1024 * 1024 * 1024,
            'maxTotalBufferSize': 1024 * 1024 * 1024,
        })

    def load(self, url):
        self.driver.get(url)

    def load_cookies(self, cookiejar, base_domain):
        if not cookiejar:
            return

        domain_list = [k for k in cookiejar._cookies if k == base_domain]

        for domain in domain_list:
            cookies_loaded = [{
                'name': c.name,
                'value': c.value,
                'path': c.path,
                'domain': c.domain
            } for _, c in cookiejar._cookies[domain]['/'].items()]

            for c in cookies_loaded:
                self.driver.add_cookie(c)
            print(f'loaded {len(cookies_loaded)} cookies for {domain}')

    def extract_network(self):
        browser_log = self.driver.get_log('performance')

        events = [json.loads(entry['message'])['message'] for entry in browser_log]
        events = [e for e in events
                  if e['method'].startswith('Network.requestWillBeSent')
                  or e['method'].startswith('Network.responseReceived')
                  ]

        for e in events:
            request_url = traverse_obj(e, ('params', 'request', 'url'))
            if request_url is not None:
                e['request_url'] = request_url
            request_id = e['params']['requestId']
            if request_id in self.closed_request_id_set:
                self.closed_request_id_set.remove(request_id)
            self.request_id_data[request_id].append(e)

        for requestId, request_list in self.request_id_data.items():
            if requestId in self.closed_request_id_set:
                continue
            request_url = (traverse_obj(request_list, (..., 'request_url')) or [None])[0]
            if request_url is None:
                request_url = f"requestId:{requestId}"
            if request_url.startswith('chrome'):
                continue

            try:
                resp = self.driver.execute_cdp_cmd('Network.getResponseBody', {'requestId': requestId})

                resp_range_list = traverse_obj(request_list, (..., 'params', 'response', 'headers', 'Content-Range')) or []

                if resp['base64Encoded']:
                    resp_body = base64.b64decode(resp['body'])
                    try:
                        resp_body = resp_body.decode('utf8')
                        resp_body_text = True
                    except Exception:
                        resp_body_text = False
                else:
                    resp_body = resp['body']
                    resp_body_text = True

                self.closed_request_id_set.add(requestId)

                resp_range = resp_range_list[0] if resp_range_list else ''
                mobj = re.match(r'^bytes (?P<start>\d+)-(?P<end>\d+)/(?P<len>\d+)$', resp_range)

                range_start = try_call(lambda: int(mobj.group('start')))
                range_end = try_call(lambda: int(mobj.group('end')))
                range_len = try_call(lambda: int(mobj.group('len')))

                data = {
                    'body': resp_body,
                    'body_text': resp_body_text,
                    'range_start': range_start,
                    'range_end': range_end,
                    'range_len': range_len,
                    'end': range_end == range_len - 1 if range_len is not None else True
                }
                updated = True
                if requestId in self.response_dict[request_url]:
                    if self.response_dict[request_url][requestId] == data:
                        # print(f'Found same rewrite, {request_url}')
                        updated = False
                    else:
                        # print(f'Found same updated, {request_url}')
                        pass

                if updated and request_url not in self.response_updated_key_list:
                    self.response_updated_key_list.append(request_url)

                self.response_dict[request_url][requestId] = data
                # print(f'Get new resp:{len(self.response_dict[request_url])} start:{range_start} len:{len(resp_body)} {request_url}')

            except Exception as e:
                if 'No data found for resource with given identifier' in str(e):
                    pass
                elif 'No resource with given identifier found' in str(e):
                    pass
                else:
                    raise

    def get_response_frag_data(self, resp_map, check_complete=True):
        if len(resp_map) == 1:
            return list(resp_map.values())[0]

        frags = [f for f in resp_map.values() if f['range_start'] is not None]
        frags.sort(key=lambda f: f['range_start'])
        if check_complete:
            frag_offset = -1
            for f in frags:
                if f['range_start'] != frag_offset + 1:
                    print(f'broken {f["range_start"]}')
                frag_offset = f['range_end']
            if not frags[-1]['end']:
                print('missing tail')

        data = b''.join(f['body'] for f in frags)
        return {
            'body': data,
            'body_text': False,
            'range_len': frags[-1]['range_len'],
            'end': frags[-1]['end']
        }

    def parse_video_info(self):
        self.driver.switch_to.new_window()
        self.load('chrome://media-internals/')
        time.sleep(1)
        self.execute_script("document.getElementsByClassName('player-name')[0].click()")
        video_info_e = self.find_element(By.XPATH, '//table[@id="player-property-table"]//td[text()="kVideoTracks"]/following-sibling::td')
        audio_info_e = self.find_element(By.XPATH, '//table[@id="player-property-table"]//td[text()="kAudioTracks"]/following-sibling::td')

        video_info_dict = json.loads(video_info_e.get_attribute('innerText'))[0]
        audio_info_dict = json.loads(audio_info_e.get_attribute('innerText'))[0]

        vcodec = video_info_dict['codec']
        acodec = audio_info_dict['codec']
        video_size = video_info_dict['coded size']
        videoWidth, videoHeight = video_size.split('x')
        asr = audio_info_dict['samples per second']

        return {
                'width': int_or_none(videoWidth),
                'height': int_or_none(videoHeight),
                'vcodec': vcodec,
                'acodec': acodec,
                'asr': asr,
            }


    def find_element(self, *args, **kvargs):
        return self.driver.find_element(*args, **kvargs)

    def execute_script(self, script, *args):
        return self.driver.execute_script(script, *args)

    def wait(self, timeout):
        return WebDriverWait(self.driver, timeout)

    def close(self):
        if self.driver:
            if self.close_log_callback:
                self.close_log_callback()

            self.driver.quit()
            self.driver = None

    def __enter__(self):
        return self

    def __exit__(self, type, value, trace):
        self.close()


