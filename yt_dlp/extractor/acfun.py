
from .common import InfoExtractor
from ..utils import (
    bug_reports_message,
    ExtractorError,
    float_or_none,
    format_field,
    int_or_none,
    traverse_obj,
    parse_codecs,
    parse_qs,
)


class AcFunVideoBaseIE(InfoExtractor):
    def parse_format_and_subtitle(self, video_id, video_info):
        if 'ksPlayJson' not in video_info:
            raise ExtractorError(f'Unknown webpage json schema{bug_reports_message()}')
        playjson = self._parse_json(video_info['ksPlayJson'], video_id)

        formats, subtitles = [], {}
        for video in traverse_obj(playjson, ('adaptationSet', 0, 'representation')):
            fmts, subs = self._extract_m3u8_formats_and_subtitles(video['url'], video_id, 'mp4', fatal=False)
            formats.extend(fmts)
            self._merge_subtitles(subs, target=subtitles)
            for f in fmts:
                f.update({
                    'fps': float_or_none(video.get('frameRate')),
                    'width': int_or_none(video.get('width')),
                    'height': int_or_none(video.get('height')),
                    'tbr': float_or_none(video.get('avgBitrate')),
                    **parse_codecs(video.get('codecs', ''))
                })

        self._sort_formats(formats)

        return {
            'formats': formats,
            'subtitles': subtitles,
            'duration': float_or_none(video_info.get('durationMillis'), 1000),
            'timestamp': int_or_none(video_info.get('uploadTime'), 1000),
        }


class AcFunVideoIE(AcFunVideoBaseIE):
    _VALID_URL = r'(?x)https?://(?:www\.acfun\.cn/v/)ac(?P<id>[_\d]+)'

    _TESTS = [{
        'url': 'https://www.acfun.cn/v/ac35457073',
        'info_dict': {
            'id': '35457073',
            'title': '1 8 岁 现 状',
            'description': '“赶紧回去！班主任查班了！”',
            'uploader': '锤子game',
            'uploader_id': '51246077',
            'duration': 174.208,
            'timestamp': 1656403967
        },
        'params': {
            'skip_download': 'm3u8',
        },
    },{
        # example for len(video_list) > 1
        'url': 'https://www.acfun.cn/v/ac35468952_2',
        'only_matching': True,
    }]

    def _real_extract(self, url):
        video_id = self._match_id(url)

        webpage = self._download_webpage(url, video_id)
        json_all = self._search_json(r'window.videoInfo\s*=\s*', webpage, 'videoInfo', video_id)

        video_info = json_all['currentVideoInfo']

        title = json_all.get('title', '')
        video_internal_id = traverse_obj(json_all, ('currentVideoInfo', 'id'))
        if 'videoList' in json_all and video_internal_id is not None:
            video_list = json_all['videoList']
            part_idx, part_video_info = next(
                (idx + 1, v) for (idx, v) in enumerate(video_list)
                if v['id'] == video_internal_id)

            if len(video_list) > 1:
                title = f'{title} P{part_idx:02d} {part_video_info["title"]}'

        return {
            'id': video_id,
            'title': title,
            'thumbnail': json_all.get('coverUrl'),
            'description': json_all.get('description'),
            'uploader': traverse_obj(json_all, ('user', 'name')),
            'uploader_id': traverse_obj(json_all, ('user', 'href')),
            'tags': traverse_obj(json_all, ('tagList', ..., 'name')),
            'view_count': int_or_none(json_all.get('viewCount')),
            'like_count': int_or_none(json_all.get('likeCountShow')),
            'comment_count': int_or_none(json_all.get('commentCountShow')),
            'http_headers': {
                'Referer': url,
            },
            **self.parse_format_and_subtitle(video_id, video_info)
        }


class AcFunBangumiIE(AcFunVideoBaseIE):
    _VALID_URL = r'https?://www\.acfun\.cn/bangumi/(?P<id>aa[_\d]+)'

    _TESTS = [{
        'url': 'https://www.acfun.cn/bangumi/aa6002917',
        'info_dict': {
            'id': 'aa6002917',
            'title': '租借女友 第1话 租借女友',
            'duration': 1467,
            'timestamp': 1594432800,
        },
        'params': {
            'skip_download': 'm3u8',
        },
        'skip': 'Geo-restricted to China',
    }, {
        'url': 'https://www.acfun.cn/bangumi/aa6002917_36188_1745457?ac=2',
        'only_matching': True,
    }]

    def _real_extract(self, url):
        video_id = self._match_id(url)
        ac_idx = parse_qs(url).get('ac', [None])[-1]

        video_id = f'{video_id}{format_field(ac_idx, template="__%s")}'

        webpage = self._download_webpage(url, video_id)
        json_bangumi_data = self._search_json(r'window.bangumiData\s*=\s*', webpage, 'bangumiData', video_id)

        info = {}
        if not ac_idx:
            video_info = json_bangumi_data['currentVideoInfo']
            title = json_bangumi_data.get('showTitle')
            season_id = json_bangumi_data.get('bangumiId')

            season_number = season_id and next((
                    idx + 1 for (idx, v) in enumerate(json_bangumi_data.get('relatedBangumis', []))
                    if v.get('id') == season_id), 1)

            json_bangumi_list = self._search_json(r'window.bangumiList\s*=\s*', webpage, 'bangumiList', video_id) or {}
            video_internal_id = int_or_none(traverse_obj(json_bangumi_data, ('currentVideoInfo', 'id')))
            episode_number = None
            if video_internal_id:
                episode_number = next(
                    idx + 1 for (idx, v) in enumerate(json_bangumi_list.get('items', []))
                    if v.get('videoId') == video_internal_id)

            info.update({
                'thumbnail': json_bangumi_data.get('image'),
                'comment_count': int_or_none(json_bangumi_data.get('commentCount')),
                'season': json_bangumi_data.get('bangumiTitle'),
                'season_id': season_id,
                'season_number': season_number,
                'episode': json_bangumi_data.get('title'),
                'episode_number': episode_number,
            })
        else:
            # if has ac_idx, this url is a proxy to other video which is at https://www.acfun.cn/v/ac
            # the normal video_id is not in json
            video_info = json_bangumi_data['hlVideoInfo']
            title = video_info.get('title')

        return {
            'id': video_id,
            'title': title,
            'http_headers': {
                'Referer': url,
            },
            ** info,
            **self.parse_format_and_subtitle(video_id, video_info)
        }
