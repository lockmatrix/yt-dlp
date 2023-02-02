
from . import HlsFD


class HlsFakeHeaderFD(HlsFD):
    """
    For M3U8 with fake header in each frags
    """

    FD_NAME = 'hlsnative_fake_header'

    has_warned = False

    def _fixup_fragment(self, ctx, frag_bytes):
        if frag_bytes is None:
            return None
        ts_start_pos = frag_bytes.find(b'\x47\x40')
        frag_bytes = frag_bytes[ts_start_pos:]

        no_fake_header = ts_start_pos == 0
        if no_fake_header and not self.has_warned:
            self.to_screen("")
            self.to_screen("There is no fake header")
            self.has_warned = True

        return frag_bytes
