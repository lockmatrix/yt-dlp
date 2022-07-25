import urllib

from .common import InfoExtractor
from .openload import PhantomJSwrapper
from ..utils import unescapeHTML, parse_qs


class SbdmIE(InfoExtractor):
    _VALID_URL = r'(?x)(?P<season>https?://www\.sbdm\.net/[^/]+/\d+)/v.html\?(?P<id>\d+-\d+-\d+)'

    _TESTS = [{
        'url': 'https://www.sbdm.net/XFDM/40376/v.html?40376-0-0',
        'info_dict': {
            'id': '40376-0-0',
            'ext': 'mp4',
            'title': '最近雇的女仆有點怪 第1集',
        },
    }]

    def _real_extract(self, url):
        mobj = self._match_valid_url(url)
        video_id = mobj.group('id')
        season_url = mobj.group('season')

        season_url_parsed = urllib.parse.urlparse(season_url)
        season_url_path = url[len(season_url_parsed.scheme + '://' + season_url_parsed.netloc):]

        phantom = PhantomJSwrapper(self)

        season_page, _ = phantom.get(season_url, video_id=video_id, note='Downloading season page')
        season_title = self._search_regex(r'<h1>(?P<season_title>[^<]+)</h1>', season_page, 'title')

        title_pattern = r'title="(?P<title>[^"]+)"\s+href="' + season_url_path.replace('?', r'\?')
        title = self._search_regex(title_pattern, season_page, 'title')
        title = f'{season_title} {title}'

        video_page, _ = phantom.get(url, video_id=video_id, note='Downloading video page')
        iframe_url = unescapeHTML(self._search_regex(r'<iframe[^<]+?src="(?P<url>[^"]+)"', video_page, 'iframe url'))
        m3u8_url = parse_qs(iframe_url)['a'][0]

        return {
            'id': video_id,
            'title': title,
            '_type': 'video',
            'formats': [{
                'url': m3u8_url,
                'protocol': 'm3u8_fake_header',
                'ext': 'mp4',
            }]
        }
