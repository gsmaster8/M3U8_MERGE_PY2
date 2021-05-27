# coding=utf-8
import os
import re
import sys
import glob
import subprocess
import helper
from optparse import OptionParser

HOME = os.path.dirname(os.path.realpath(__file__))
pathEnv=os.getenv('PATH')
os.environ['PATH']= "%s" %(HOME) + ":" + pathEnv 
dest_fps = 15
default_resolution = False
target_width = 640
target_height = 360
black_frame_mode = False

class Logger:
    def __init__(self, logfile):
        self.terminal = sys.stdout
        self.log = open(logfile, "a")
        sys.stdout = self
    def write(self, message):
        self.terminal.write(message)
        self.log.write(message) 

class AudioClip:
    def __init__(self):
        self.num = 0
        self.filename = []
        self.start_time = []
        self.end_time = []

    def update_audio_info(self, i, stime, etime):
        self.start_time[i] = stime
        self.end_time[i] = etime

    def put_file(self, name):
        if not (name in self.filename):
            self.filename.append(name)
            self.start_time.append(0.0)
            self.end_time.append(0.0)
            self.num = self.num + 1
        return self.filename.index(name)

    def max_length(self):
        return max(self.end_time)

    # 在第i个切片前填补空缺
    # 看起来这个offset_time一直等于0
    # 第一个start_time[0]
    def print_filename(self, offset_time):
        str = ""
        for i in range(self.num):
            if i > 0:
                len = self.start_time[i] - self.end_time[i-1]
            else:
                len = self.start_time[0] - offset_time
            if len < 0.001:
                len = 0.001
            str = str + ("-f lavfi -t %.3f -i anullsrc=channel_layout=mono:sample_rate=48000 " % len)
            str = str + ("-i %s " % self.filename[i])
        return str

    def print_audio_info(self, i):
        print "Audio Clip %d: %s: start_time=%.3f, end_time=%.3f" % (i, self.filename[i], self.start_time[i], self.end_time[i])

    def print_ffmpeg(self, output_file, offset_time):
        if self.num >= 1:
            str = "ffmpeg " + self.print_filename(offset_time)
            str = str + "-filter_complex \"concat=n=%d:v=0:a=1[audio]\" " % (self.num * 2)
            str = str + " -map \"[audio]\" -to %f -y %s" % (self.max_length() - offset_time, output_file)
        elif self.num == 1:
            str = "ffmpeg -i %s -c:a copy %s" % (self.filename[0], output_file)
            # 不用填 空白音频，后续合并视频时一起
        else:
            str = ""
        str = str + " 2>&1 | tee -a convert.log"
        print "==============================audio ffmpeg====================================="
        print str
        return str

class VideoClip:
    def __init__(self):
        self.num = 0
        self.filename = []
        self.start_time = []
        self.end_time = []
        self.audio_file = ""
        self.audio_start_time = 0.0
        self.audio_end_time = 0.0
        self.overlay_str = ""

    def update_audio_info(self, audio_stime, audio_etime):
        self.audio_start_time = audio_stime
        self.audio_end_time = audio_etime

    def update_video_info(self, i, video_stime, video_etime):
        self.start_time[i] = video_stime
        self.end_time[i] = video_etime

    def put_file(self, name):
        if not (name in self.filename):
            self.filename.append(name)
            self.start_time.append(0.0)
            self.end_time.append(0.0)
            self.num = self.num + 1
        return self.filename.index(name)
    
    def max_length(self):
        if self.num > 0:
            return max(max(self.end_time), self.audio_end_time)
        else:
            return self.audio_end_time
    
    def audio_delay_needed(self, offset_time):
        return self.audio_file != "" and (self.audio_start_time - offset_time) > 0.05
    def audio_apad_needed(self):
        return self.audio_file != "" and self.max_length() > self.audio_end_time
   
    def print_filter(self, offset_time):
        str = "" 
        if self.audio_delay_needed(offset_time):
            audio_delay = int((self.audio_start_time - offset_time)*1000)
            str = "[0]adelay=%d" % audio_delay
            if self.audio_apad_needed():
                str = str + ",apad"
            str = str + "[audio];"
        elif self.audio_apad_needed():
                str = str + "[0]apad[audio];"

        source = "1"
        sink = "out2"

        if not black_frame_mode:
            self.overlay_str = "overlay=eof_action=repeat"
        else:
            self.overlay_str = "overlay=eof_action=repeat:repeatlast=0"

        for i in range(self.num):
            src = "%d" % (i+2)

            sink = "out%d" % (i+2)
            if i == self.num - 1:
                sink = "video"

            tmp = "[%s]scale=%dx%d,setpts=PTS-STARTPTS+%.3f/TB[scale%s];[%s][scale%s]%s[%s];" % \
                    ( src, target_width, target_height, self.start_time[i] - offset_time, src, source, src, self.overlay_str, sink )
            str = str + tmp
            source = sink
        return str[:-1]
   
    def print_filename(self):
        str = ""
        for i in range(self.num):
            str = str + ("-i %s " % self.filename[i])
        return str
   
    def print_ffmpeg(self, output_file, offset_time):
        if self.audio_file == "":
            str = "ffmpeg -f lavfi -i anullsrc "
        else:
            str = "ffmpeg -i %s " % self.audio_file

        str = str + "-f lavfi -i \"color=black:s=%dx%d:r=15\" "% (target_width, target_height)
        str = str + self.print_filename()
        str = str + "-filter_complex \"%s\" " % self.print_filter(offset_time)
        if self.audio_file == "":
            map_option = "-map \"[video]\""
        else:
            if self.audio_delay_needed(offset_time) or self.audio_apad_needed():
                map_option = "-map \"[audio]\" -map \"[video]\" -c:a aac"
            else:
                map_option = "-map 0:a:0 -map \"[video]\" -c:a copy"
        str = str + " %s -c:v libx264 -r %d -preset veryfast -shortest -to %f -y %s" % (map_option, dest_fps, self.max_length() - offset_time, output_file)
        str = str + " 2>&1 | tee -a convert.log"
        print "=================================video ffmpeg ========================"
        print str
        return str

    def print_audio_info(self):
        print "Audio Clip: %s: start_time=%.3f, end_time=%.3f" % (self.audio_file, self.audio_start_time, self.audio_end_time)
    
    def print_video_info(self, i):
        print "Video Clip %d: %s: start_time=%.3f, end_time=%.3f, width=%d, height=%d" % \
            (i, self.filename[i], self.start_time[i], self.end_time[i], target_width, target_height)
    
class UserAvClip:
    def __init__(self, folder_name, start_time, end_time, uid_file, opt):
        self.folder_name = folder_name
        self.start_time = start_time
        self.end_time = end_time
        self.uid_file = uid_file
        self.option = opt
        self.uid = 0

    def parse(self):
        self.uid = os.path.splitext(self.uid_file)[0][4:]
        print "UID:" + self.uid

        self.clip = VideoClip()
        self.audio_clip = AudioClip()
        with open(self.uid_file) as f:
            lines = f.readlines()
            for line in lines:
                items = line.split(" ")
                if os.path.getsize(items[1]) == 0:
                    continue
                # audio file
                if items[1][-3:] == "m4a":
                    index = self.audio_clip.put_file(items[1])
                    if items[2] == "create":
                        self.audio_clip.start_time[index] = float(items[0])
                    elif items[2] == "close":
                        self.audio_clip.end_time[index] = float(items[0])

                # video file
                if items[1][-3:] == "mp4":
                    index = self.clip.put_file(items[1])
                    if items[2] == "create":
                        self.clip.start_time[index] = float(items[0])
            
                    elif items[2] == "close":
                        self.clip.end_time[index] = float(items[0])

                # video file
                if items[1][-2:] == "ts":
                    index = self.clip.put_file(items[1])
                    if items[2] == "create":
                        self.clip.start_time[index] = float(items[0])
        
                    elif items[2] == "close":
                        self.clip.end_time[index] = float(items[0])

            for i in range(self.audio_clip.num):
                self.audio_clip.print_audio_info(i)
            for i in range(self.clip.num):
                self.clip.print_video_info(i)

    def convert(self, suffix, offset_time):
        print "Offset_time : " + str(offset_time)
        child_env = os.environ.copy()
        if self.audio_clip.num == 0 and self.clip.num == 0:
            return ""

        if self.audio_clip.num >= 1:
            print "Generate Audio File"
            tmp_audio = self.folder_name.strip() + '/' + self.uid + "_tmp.m4a"
            ffmpeg_args_file = self.folder_name.strip() + '/' + self.uid + '_ffmpeg_args.sh'
            command = self.audio_clip.print_ffmpeg(tmp_audio, offset_time)
            self.clip.audio_file = tmp_audio
            self.clip.audio_start_time = offset_time
            self.clip.audio_end_time = self.audio_clip.max_length()
            print command
            
            f = open(ffmpeg_args_file, 'w') 
            f.write(command)
            f.close()
            
            command = "chmod a+x %s" % ffmpeg_args_file
            subprocess.Popen(command, shell=True, env=child_env).wait()
            subprocess.Popen(ffmpeg_args_file, shell=True, env=child_env).wait()

        if self.clip.num > 0:
            print "Generate MP4 file:"
            print "Output resolution:", target_width, target_height
            #output_file = self.uid + suffix + "_qa.mp4"
            return_file = self.uid + suffix + ".mp4"
            command = self.clip.print_ffmpeg(return_file, offset_time)

            print command
            subprocess.Popen(command, shell=True, env=child_env).wait()

            print "\n\n"
        else:
            return_file = self.uid + ".m4a"
            command = "cp -f %s %s" % (self.clip.audio_file, return_file)
            os.system(command)
        # remove tmp files
        os.system('rm -f *_tmp.m4a')
        os.system('rm -f *_ffmpeg_args.sh')
        return return_file

class UserAv:
    def __init__(self, uid):
        self.uid = uid
        self.avClips = dict()
        self.num = 0

    def addClip(self, clip):
        self.avClips[self.num] = clip
        self.num += 1

def UidFileConvert(folder_name, uid_file, suffix, option, offset_time):    
        print "Offset_time : " + str(offset_time)
        child_env = os.environ.copy()

        uid = os.path.splitext(uid_file)[0][4:]
        print "UID:"+uid
            
        clip = VideoClip()
        audio_clip = AudioClip()

        # 缓存切片信息至clip、audio_clip
        with open(uid_file) as f:
            lines = f.readlines()
            for line in lines:

                items = line.split(" ")
                if os.path.getsize(items[1]) == 0:
                    continue
                #audio file
                if items[1][-3:] == "m4a":
                    index = audio_clip.put_file(items[1])
                    if items[2] == "create":
                        audio_clip.start_time[index] = float(items[0])
                    elif items[2] == "close":
                        audio_clip.end_time[index] = float(items[0])
                        
                #video file
                if items[1][-3:] == "mp4":
                    index = clip.put_file(items[1])
                    if items[2] == "create":
                        clip.start_time[index] = float(items[0])

                    elif items[2] == "close":
                        clip.end_time[index] = float(items[0])

                if items[1][-2:] == "ts":
                    index = clip.put_file(items[1])
                    if items[2] == "create":
                        clip.start_time[index] = float(items[0])
                
                    elif items[2] == "close":
                        clip.end_time[index] = float(items[0])

            for i in range(audio_clip.num):
                audio_clip.print_audio_info(i)
            for i in range(clip.num):
                clip.print_video_info(i)

        if audio_clip.num == 0 and clip.num == 0:
            return ""
                    
        if audio_clip.num >= 1:
                print "Generate Audio File"
                tmp_audio = folder_name.strip() + '/' + uid+"_tmp.m4a"
                ffmpeg_args_file = folder_name.strip() + '/' + uid + '_ffmpeg_args.sh'
                command = audio_clip.print_ffmpeg(tmp_audio, offset_time)
                clip.audio_file = tmp_audio #记录合并后的音频文件名
                clip.audio_start_time = offset_time # 因为会填充静音包，所以肯定为0
                clip.audio_end_time = audio_clip.max_length() # 这里合并音频时不会在尾部填补静音包
                print command
                
                f = open(ffmpeg_args_file, 'w') 
                f.write(command)
                f.close()
                
                command = "chmod a+x %s" % ffmpeg_args_file
                subprocess.Popen(command, shell=True, env=child_env).wait()
                subprocess.Popen(ffmpeg_args_file, shell=True, env=child_env).wait()
    
        if clip.num > 0:
                print "Generate MP4 file:"
                output_file = uid + suffix + ".mp4"
                command =  clip.print_ffmpeg(output_file, offset_time)
        else:
                tmp_audio = uid+"_tmp.m4a"
                output_file = uid+".m4a"
                if audio_clip.num >= 1:
                    command = "mv %s %s" % (tmp_audio, output_file)
                elif audio_clip.num == 1:
                    command = "ffmpeg -i %s -c:a copy -y %s" % (clip.audio_file, output_file)
        print command
        subprocess.Popen(command, shell=True, env=child_env).wait()
        print "\n\n"
        #remove tmp files
        os.system('rm -f *_tmp.m4a')
        os.system('rm -f *_ffmpeg_args.sh')
        return output_file   

def SessionConvert(folder_name, opt, saving):
    child_env = os.environ.copy()
    if not os.path.isdir(folder_name):
        print "Folder " + folder_name + " does not exist"
        return

    os.chdir(folder_name)
    os.system('rm -f *_merge.txt')
    #session_filename = 'uid_' + self.uid + "_" + utc + ".txt"
    all_uid_file = sorted(glob.glob("uid_*.txt"))
    if opt == 0 :
        # 对于每一个middle文件对应的Session，进行合并操作
        for uid_file in all_uid_file:
            offset_time = uid_file.split("_")[2][0:-4]
            UidFileConvert(folder_name, uid_file, "_av", 0, helper.utc_convert(offset_time))

        f = open("convert-done.txt", "w")
        f.close()
        return
    
    dict_uid = dict()
    #dict_uid_index = dict()
    for uid_file in all_uid_file:
        uid = uid_file.split("_")[1]

        start_ts = -1.0
        end_ts = start_ts
        #detectedOncePerTxt = False 
        key = uid
        if not dict_uid.has_key(key):
            dict_uid[key] = UserAv(key)
        with open(uid_file) as f:
            lines = f.readlines()
        
            for line in lines:
                items = line.split(" ")
                if os.path.getsize(items[1]) == 0:
                    continue

                if start_ts < 0:
                    if float(items[0]) > 0:
                        start_ts = float(items[0])
                    else:
                        start_ts = 0
                items[0] = "%.3f" % (float(items[0])) 

                end_ts = float(items[0])
                
        clip = UserAvClip(folder_name, start_ts, end_ts, uid_file, opt)
        clip.parse() # segment合并
        dict_uid[key].addClip(clip) # 存储一个segment信息
    
    temp_files = []
    for index in dict_uid.keys():
        usr = dict_uid[index]
        print "Merge for uid : " + usr.uid
        concat_file = index + "_filelist.txt"
        file = open(concat_file, "a")
        last_ts = 0
        merged_index = 0
        for i in usr.avClips.keys():
            clip = usr.avClips[i]
            if last_ts == 0 or saving:
                last_ts = clip.start_time
            output_file = clip.convert("_" + str(merged_index) + "_av", last_ts)
            if output_file != "":
                file.write("file \'" + output_file + "'\n")
                merged_index += 1
                if not saving:
                    last_ts = clip.end_time
                temp_files.append(output_file)

        file.close()
        if merged_index == 0:
            continue

        target_file_name = usr.uid + "_merge_av.mp4"

        command = "ffmpeg -f concat -i " + concat_file + " -c copy " + target_file_name
        print command
        subprocess.Popen(command, shell=True, env=child_env).wait()

    os.system('rm -f *_filelist.txt')
    for tem_file in temp_files:
        os.system('rm -f ' + tem_file)

    #write a convert done file
    f = open("convert-done.txt", "w")
    f.close()
    return    

def do_work():
    global default_resolution
    global target_width
    global target_height
    global dest_fps
    global black_frame_mode
    parser = OptionParser()
    parser.add_option("-f", "--folder", type="string", dest="folder", help="Folder of files to be merged", default="")
    parser.add_option("-m", "--mode", type="int", dest="mode", help="Convert merge mode.\n \
        [0: segment merge A/V(Default);\n 1: uid merge A/V]", default=0)
    parser.add_option("-p", "--fps", type="int", dest="fps", help="Convert fps, default 15", default=15)
    parser.add_option("-s", "--saving", action="store_true", dest="saving", help="Convert Do not time sync",
                      default=False)
    parser.add_option("-a", "--aux_use", action="store_true", dest="aux_use", help="If main stream not exited, use aux stream",
                      default=False)
    parser.add_option("-r", "--resolution", type="int", dest="resolution", nargs=2, help = "Specific resolution to convert '-r width height' \nEg:'-r 640 360'", 
                      default=(0,0))
    parser.add_option("-b", "--fill_black", action="store_true", dest="fill_black", help="Show black frame when there is no video file",
                      default=False)
    
    (options, args) = parser.parse_args()
    if not options.folder:
        parser.print_help()
        parser.error("Not set folder")
    if options.mode < 0 or options.mode > 1:
        parser.error("Invalid mode")
    if options.fps <= 0:
        parser.error("Invalid fps")

    if options.resolution[0] < 0 or options.resolution[1] < 0:
        parser.error("Invalid resolution width/height")
    elif options.resolution[0] == 0 and options.resolution[1] == 0:
        default_resolution = True
    else:
        target_width = options.resolution[0]
        target_height = options.resolution[1]

    if options.fill_black:
        black_frame_mode = True

    os.system("rm -f " + options.folder + "/convert.log")
    Logger(options.folder + "/convert.log")

    if options.fps < 5:
        print "fps < 5, set to 5"
        dest_fps = 5
    elif options.fps > 120:
        print "fps > 120, set to 120"
        dest_fps = 120
    else:
        dest_fps = options.fps

    SessionConvert(options.folder, options.mode, options.saving)

if __name__ == '__main__':
    do_work()
