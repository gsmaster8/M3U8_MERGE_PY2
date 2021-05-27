import time
import re
import os
import sys
import signal
import glob
import parser_floder_m3u8
import convert_phase
from optparse import OptionParser

import traceback


if '__main__' == __name__:
    import sys

    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGQUIT, signal.SIG_IGN)

    parser = OptionParser()
    parser.add_option("-f", "--folder", type="string", dest="folder", help="Folder of files to be merged", default="")
    parser.add_option("-m", "--mode", type="int", dest="mode", help="Convert merge mode.\n \
        [0: segment merge A/V(Default);\n 1: uid merge A/V]", default=0)
    parser.add_option("-p", "--fps", type="int", dest="fps", help="Convert fps, default 15", default=15)
    parser.add_option("-s", "--saving", action="store_true", dest="saving", help="Convert Do not time sync",
                      default=False)
    parser.add_option("-a", "--aux_use", action="store_true", dest="aux_use", help="If main stream not exited, use aux stream",
                      default=False)
    parser.add_option("-r", "--resolution", type="int", dest="resolution", nargs=2,
                      help="Specific resolution to convert '-r width height' \nEg:'-r 640 360', default 640x360", default=(0, 0))
    parser.add_option("-b", "--fill_black", action="store_true", dest="fill_black", help="Show black frame when there is no video file",
                      default=False)

    (options, args) = parser.parse_args()
    if not options.folder:
        parser.print_help()
        parser.error("Not set folder")

    try:
        os.environ['FPSARG'] = "%s" % options.fps
        os.environ['USEAUX'] = "%d" % options.aux_use
        parser_floder_m3u8.cmds_parse(["dispose", options.folder])
        convert_phase.do_work()
        parser_floder_m3u8.cmds_parse(["clean", options.folder])
    except Exception as e:
        traceback.print_exc()

