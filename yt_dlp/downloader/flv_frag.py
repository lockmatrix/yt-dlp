import os.path
import time
from pathlib import Path

from . import get_suitable_downloader
from .fragment import FragmentFD
from ..postprocessor import FFmpegConcatPP, FFmpegPostProcessor


class FlvSegmentFD(FragmentFD):
    FD_NAME = 'flv_segments'

    def real_download(self, filename, info_dict):
        requested_formats = [{**info_dict, **fmt} for fmt in info_dict.get('requested_formats', [])]
        target_formats = requested_formats or [info_dict]

        dl = get_suitable_downloader({'url': target_formats[0]['url']}, self.params, to_stdout=(filename == '-'))
        dl = dl(self.ydl, self.params)

        ffmpeg_tester = FFmpegPostProcessor()

        for fmt in target_formats:
            fmt_output_filename = fmt.get('filepath') or filename
            temp_output_filename = fmt_output_filename[:-len(Path(fmt_output_filename).suffix)]

            self.to_screen('[flv_segments] Format %s has %s fragments' % (fmt['format_id'], len(fmt['flv_segments'])))

            merge_infiles = []
            for fragment_index, fragment in enumerate(fmt['flv_segments']):
                fragment_filename = temp_output_filename + '.Frag%02d.' % fragment_index + fmt['ext']
                frag_info = {
                    'http_headers': fmt.get('http_headers'),
                    **fragment
                }
                # self.to_screen('[flv_segments] url: %s' % frag_info['url'])
                dl.download(fragment_filename, frag_info)
                merge_infiles.append(fragment_filename)

            if ffmpeg_tester.available and ffmpeg_tester.probe_available:
                concat_pp = FFmpegConcatPP(self.ydl)
                concat_pp.concat_files(merge_infiles, fmt_output_filename)
                if os.path.exists(fmt_output_filename):
                    for fn in merge_infiles:
                        os.remove(fn)

        return True
