# coding=utf-8
import time
import re
import os
import sys
import traceback
from segment_middle_file import MiddleFilePerSegment
import copy
import helper
import subprocess
from parser_m3u8 import M3u8File

class PerUidCachedM3u8Dict(object):
    def __init__(self):
        # merged_av_mediafile_dict：缓存uid的所有音视频信息
        self.merged_av_mediafile_dict = {}
        self.ordered_merged_av_mediafile_dict = None
        self.middle_file = "media_file.mf"
        self.fps = 15
        if os.environ.get('FPSARG') is not None:
            self.fps = int(os.environ['FPSARG'])
            if (self.fps <= 0):
                self.fps = 15

        self.segment_dict = {
                    }

        self.ordered_segment_dict = None

    # utc 差15秒表示一个新segment
    def take_segment_from_whole_dict(self, delta = 15):
        temp_segment = {}
        start_time_tuple=()
        start_flag = False
        next_timestamp = 0.0
        if self.ordered_merged_av_mediafile_dict is not None:
            for item in self.ordered_merged_av_mediafile_dict:
                if item[1].has_key('fileinfos') and item[1]['fileinfos'].has_key('duration'):
                    utc = item[0]
                    duration = item[1]['fileinfos']['duration']
                    if not start_flag:
                        #new segment start point
                        start_flag = True
                        start_time_tuple = (utc, helper.utc_convert(utc))

                    else:
                        #judge if it's segment stop point
                        if next_timestamp + delta < helper.utc_convert(utc):
                            #save previous data in segment_dict

                            z = zip(temp_segment.keys(), temp_segment.values())
                            sorted_temp_segment = sorted(z)

                            self.segment_dict[start_time_tuple[0]] = copy.deepcopy(sorted_temp_segment)

                            #clear up  & init
                            temp_segment.clear()

                            start_time_tuple = (utc, helper.utc_convert(utc))
                    #move to next utc_timestamp
                    #next_timestamp = helper.utc_convert(utc) + float(duration)
                    next_timestamp = max(next_timestamp, helper.utc_convert(utc) + float(duration))

                #store everything
                temp_segment[item[0]] = item[1]
        z = zip(temp_segment.keys(), temp_segment.values())
        sorted_temp_segment = sorted(z)
        self.segment_dict[start_time_tuple[0]] = copy.deepcopy(sorted_temp_segment)
#        print (self.segment_dict)

    def sorted_segment_dict(self):
        z = zip(self.segment_dict.keys(), self.segment_dict.values())
        self.ordered_segment_dict = sorted(z)
#        print (self.ordered_segment_dict)

    def sorted_mediafile_dict(self):
        if self.ordered_merged_av_mediafile_dict:
            return
        z = zip(self.merged_av_mediafile_dict.keys(), self.merged_av_mediafile_dict.values())
        self.ordered_merged_av_mediafile_dict = sorted(z)

    def is_duration_zero(self, file_name):
        cmd = "ffmpeg -i %s 2>&1 | grep Duration | awk '{print $2}' | tr -d ," % file_name
        result = subprocess.check_output(cmd, shell=True).strip()
        return result == "00:00:00.00"

    def merged_video_m3u8_dict(self, video_mediafile_dict):
        '''this call should be better call fistly, because it doesn't dispose key conflict'''
        temp_files = []
        for item in video_mediafile_dict.items():
            utc = item[0]
            utc_item_value = copy.deepcopy(item[1])
            suffix = utc_item_value['fileinfos']['suffix']

            duration = utc_item_value['fileinfos']['duration']
            file_name = utc_item_value['fileinfos']['name']
            # skip corrupted ts files
            if duration < 0.1:
                if (self.is_duration_zero(file_name)):
                    continue

            media_filename = utc_item_value['fileinfos']['name']
            media_filename_prefix = media_filename.split(suffix)[0]
            #modify value
            new_suffix='mp4'
            temp_filename = media_filename_prefix + "_bat." + new_suffix
            target_filename = media_filename_prefix + new_suffix
            utc_item_value['fileinfos']['name'] = target_filename
            utc_item_value['fileinfos']['suffix'] = new_suffix

            #convert video from ts to mp4
            command = "ffmpeg -fflags +igndts -i " + media_filename + " -vcodec copy -copytb 1 -copyts -y " + temp_filename
            print(command)
            errorcode = subprocess.Popen(command, shell=True, env=None).wait()
            if errorcode:
                os.system("rm -f " + temp_filename)
                print "ffmpeg parse error, filename: %d" % media_filename
                continue

            command = "ffmpeg -i %s -vcodec libx264 -vf 'fps=%d' -y %s -vsync 1" % (temp_filename, self.fps, target_filename)
            #command = "ffmpeg -i %s -vcodec copy -y %s -vsync 1" % (temp_filename, target_filename)
            command +=  " 2>&1 | tee -a convert.log"
            print(command)
            errorcode = subprocess.Popen(command, shell=True, env=None).wait()
            os.system("rm -f " + temp_filename)
            if errorcode:
                print "ffmpeg parse error, filename: %d" % media_filename
                continue

            #recombine
            #if utc conflict, increase it 0.001f each time
            while self.merged_av_mediafile_dict.has_key(utc):
                utc_float = float(utc) + 0.001
                utc = ("%.3f" % utc_float)
            temp_files.append(target_filename + " \n")

            self.merged_av_mediafile_dict[utc] = utc_item_value

        if len(temp_files) > 0:
            fd = open(self.middle_file,'a')
            fd.writelines(temp_files)
            fd.close()

    def merged_audio_m3u8_dict(self, audio_mediafile_dict):
        new_suffix='m4a'
        temp_files = []
        for item in audio_mediafile_dict.items():
            utc = item[0]
            utc_item_value = copy.deepcopy(item[1])
            suffix = utc_item_value['fileinfos']['suffix']
            media_filename = utc_item_value['fileinfos']['name']
            media_filename_prefix = media_filename.split(suffix)[0]


            #modify value
            target_filename = media_filename_prefix + new_suffix
            utc_item_value['fileinfos']['name'] = target_filename
            utc_item_value['fileinfos']['suffix'] = new_suffix

            #extract audio from ts
            command = 'ffmpeg -i ' + media_filename + ' -acodec copy -y ' + target_filename
            # command = 'ffmpeg -i ' + media_filename + ' -af aresample=48000:async=1 -c:a aac -y ' + target_filename
            command += " 2>&1 | tee -a convert.log"
            print(command)
            subprocess.Popen(command, shell=True, env=None).wait()

            #recombine
            #if utc conflict, increase it 0.001f each time
            while self.merged_av_mediafile_dict.has_key(utc):
                utc_float = float(utc) + 0.001
                utc = ("%.3f" %utc_float)

            self.merged_av_mediafile_dict[utc] = utc_item_value

            temp_files.append(target_filename + " \n")
        if len(temp_files) > 0:
            fd = open(self.middle_file,'a')
            fd.writelines(temp_files)
            fd.close()

class ParserUidM3U8File(object):
    def __init__(self, format = 'm3u8', uid = None):
        if format == 'm3u8':
            self.fileformat = r'*.m3u8'
            '''
            group(1)=<Prefix>/<TaskId>/<SdkAppId>_<RoomId>
            group(2)=<UserId>
            group(3)=<MediaId>
            group(4)=<Type>
            '''
            #self.filepattern = r'(.*)__UserId_s_([a-zA-Z0-9]+)__UserId_e_([a-zA-Z]+)_([a-zA-Z]+).m3u8'
            self.filepattern = r'(.*)__UserId_s_(.*)__UserId_e_([a-zA-Z]+)_([a-zA-Z]+).m3u8'
            # 带后缀的m3u8
            #self.filewithindexpatten = r'(.*)__UserId_s_([a-zA-Z0-9]+)__UserId_e_([a-zA-Z]+)_([a-zA-Z]+)_([0-9]+).m3u8'
            self.filewithindexpatten = r'(.*)__UserId_s_(.*)__UserId_e_([a-zA-Z]+)_([a-zA-Z]+)_([0-9]+).m3u8'

            self.uid = uid

            self.aux_use = 0
            if os.environ.get('USEAUX') is not None:
                self.aux_use = os.environ['USEAUX']
                
            # filename_dict 字段
            self.filename_dict = {
                    'audio':{
                        #'file1_audio.m3u8':M3u8File
                        },
                    'video_main':{
                        #'file1_video.m3u8':M3u8File
                        },
                    'video_aux':{
                        #'file1_av.m3u8':M3u8File
                        },
                    }
           
            self.per_uid_cached_metadata_obj = PerUidCachedM3u8Dict()
        else:
            raise NameError("Not support format %s" %(format))

    
    def metadata_dict_merged_in_merged_dict(self):   
        for audio_video_type in self.filename_dict.keys():
            if audio_video_type is 'video_main':
                for mediafile_parser in self.filename_dict[audio_video_type].values():
                    self.per_uid_cached_metadata_obj.merged_video_m3u8_dict(mediafile_parser.video_main_mediafile_dict)

            elif audio_video_type is 'audio':
                for mediafile_parser in self.filename_dict[audio_video_type].values():
                    self.per_uid_cached_metadata_obj.merged_audio_m3u8_dict(mediafile_parser.audio_mediafile_dict)

            elif audio_video_type is 'video_aux' and self.aux_use:
                for mediafile_parser in self.filename_dict[audio_video_type].values():
                    self.per_uid_cached_metadata_obj.merged_video_m3u8_dict(mediafile_parser.video_aux_mediafile_dict)


    def merged_dict_splited_to_segment(self):
        #make it as sorted
        self.per_uid_cached_metadata_obj.sorted_mediafile_dict()
        #split it as many segments
        self.per_uid_cached_metadata_obj.take_segment_from_whole_dict()
        self.per_uid_cached_metadata_obj.sorted_segment_dict()


    def create_middlefile_of_segments(self):
        for segment in self.per_uid_cached_metadata_obj.ordered_segment_dict:
            utc = segment[0]
            segment_data = segment[1]
            segment_filename = 'uid_' + self.uid + "_" + utc + ".txt"
            middlefile = MiddleFilePerSegment(segment_filename)

            #container = None
            #parser segment
            last_time = {}

            #segment_data：一个segment里包含的转码后的音视频切片
            #utc_tuple_line：当前选择的音视频切片
            #utc_tuple_line[0]：当前切片的utc
            #utc_tuple_line[1]：当前切片的所有信息(event_dict)
            for utc_tuple_line in segment_data:
                file_utc = utc_tuple_line[0]
                if utc_tuple_line[1].has_key('fileinfos'):
                    container = utc_tuple_line[1]['fileinfos']['suffix'] # 此时已改成mp4或aac
                    filename = utc_tuple_line[1]['fileinfos']['name'] # xxx.mp4 / xxx.aac
                    
                    #filestart - segment_start is timestamp offset for each file
                    # start_time：切片开始时间相对segment的偏移时间
                    #start_time = helper.utc_convert(file_utc) - helper.utc_convert(utc)
                    start_time = helper.utc_convert(file_utc)
                    # close_time：切片结束时间相对segment的偏移时间
                    close_time = start_time + float(utc_tuple_line[1]['fileinfos']["duration"])

                    type = utc_tuple_line[1]['fileinfos']['type']
                    if last_time.has_key(type) and start_time <= last_time[type]:
                        start_time = last_time[type] + 0.001

                    start_str = middlefile.event_string(start_time, filename ,'start')
                    middlefile.update_cache_list(start_str) # 记录

                    info_time  = start_time

                    if close_time <= info_time:
                        close_time = info_time + 0.001
                    close_str = middlefile.event_string(close_time, filename ,'close')

                    middlefile.update_cache_list(close_str)
                    last_time[type] = close_time

            middlefile.write_cache_to_file()


    def get_fileformat(self):
        return self.fileformat

    def get_filepattern(self):
        return self.filepattern

    def get_filewithpatten(self):
        return self.filewithindexpatten

    '''
    为每一个m3u8初始化处理对象
    '''
    def update_filename_dict(self, stream_type, av_type, filename):
        try:
            file_type = av_type
            if av_type == 'video':
                file_type = file_type + "_" + stream_type
            self.filename_dict[file_type][filename] = M3u8File(self.uid, filename, file_type)
            #self.mix_metadata_mode = self.mix_metadata_mode_const_hash_tbl[type]

        except Exception as e:
            print("Error %s" %(e))
            traceback.print_exc()

    def set_uid(self, uid):
        if self.uid == None:
            self.uid = uid
    
    def dump(self):
        for key in self.filename_dict:
            print("=====type:%s" %(key))
            for file in self.filename_dict[key]:
                print("\t%s" %(key))  

