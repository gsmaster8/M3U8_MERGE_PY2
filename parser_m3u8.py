# coding=utf-8
import time
import re
import os
import sys
import traceback
import copy
import subprocess
import helper

class M3u8File(object):
    '''analyse m3u8 parser'''
    def __init__(self, uid, m3u8file, file_type):
        self.uid = uid
        self.m3u8file = m3u8file
        self.file_type = file_type
        self.middle_file = "media_file.mf"

        # media file format   group(1) = utc  group(2) = ts / WebM
        self.audio_file_name_pat = r'.*__UserId_s_%s__UserId_e_main_audio_(\d+)\.([a-zA-Z0-9]+)' %(uid)
        self.regex_audio_file_name_pat = re.compile(self.audio_file_name_pat)

        self.video_main_file_name_pat = r'.*__UserId_s_%s__UserId_e_main_video_(\d+)\.([a-zA-Z0-9]+)' %(uid)
        self.regex_video_main_file_name_pat = re.compile(self.video_main_file_name_pat)

        self.video_aux_file_name_pat = r'.*__UserId_s_%s__UserId_e_aux_video_(\d+)\.([a-zA-Z0-9]+)' %(uid)
        self.regex_video_aux_file_name_pat = re.compile(self.video_aux_file_name_pat)

        ## common part
        # self.track_file_duration_pat = r'#EXTINF:(\d+\.\d+)'
        self.track_file_duration_pat = r'#EXTINF:(\d+(?:\.\d+)?)'
        self.regex_track_file_duration_pat = re.compile(self.track_file_duration_pat)

        '''
        'name':xxxxx,
        'suffix':xxx,
        'duration':xxx,
        'type':xxx
        '''
        self.audio_mediafile_dict = {
                #000k
                }

        self.video_main_mediafile_dict = {
                #000k
                }
        self.video_aux_mediafile_dict = {}
        #self.rotation_info_dict = []
        #self.refresh_rotate_info = True

    #def get_av_mediafile_dict(self):
    #    return self.av_mediafile_dict

    def get_audio_mediafile_dict(self):
        return self.audio_mediafile_dict

    def get_video_main_mediafile_dict(self):
        return self.video_main_mediafile_dict

    def get_video_aux_mediafile_dict(self):
        return self.video_aux_mediafile_dict

    '''
    ����m3u8�ļ�����ȡaudio_mediafile_dict��video_main_mediafile_dict��video_aux_mediafile_dict
    ����video_(*)_mediafile_dict
    '''
    def metadatafile_to_list(self, file):
        event_dict={}
        f = open(file)
        lines = f.readlines()
        for line in lines: #����m3u8�ļ���ÿһ��
            if self.is_event_info(line, event_dict):  # �������� ��Ϣ
                continue
            elif self.is_media_file_info(line, event_dict): # ��ý���ļ� ��Ϣ
                event_dict.clear() # ������һ��ý���ļ��� ��Ҫ ��� event_dict
        self.merge_adjacent_video()

    '''
    �ϲ����ڵ���Ƶý���ļ�
    �����µ�ts�ļ�������Ϊ������Ƶ��Ƭ�ĵ�һ����Ƭfilename+"_concat.ts"
    ����video_mediafile_dict
    '''
    def merge_adjacent_video(self):
        if self.file_type == 'audio':
            return
        elif self.file_type == 'video_main':
            z = zip(self.video_main_mediafile_dict.keys(), self.video_main_mediafile_dict.values())
        elif self.file_type == 'video_aux':
            z = zip(self.video_aux_mediafile_dict.keys(), self.video_aux_mediafile_dict.values())
        
        ordered_video_mediafile_dict = sorted(z) # ��utc�ź���

        new_video_mediafile_dict = {}
        adjacent_files = []
        last_end = 0.000
        event_dict = {}
        first_utc = 0
        new_utc = 0.000
        new_duration = 0.000
        duration = 0.000
        temp_file = []
        width = 0
        height = 0

        for item in ordered_video_mediafile_dict:
            #if item[1]['fileinfos']['suffix'] != 'ts':
            #    new_video_mediafile_dict[item[0]] = copy.deepcopy(item[1])
            #    continue
            # Ŀǰֻ֧��ts��ʽ

            # ��һ����Ƶ��Ƭ
            if last_end == 0:
                first_utc = item[0]
                new_utc = helper.utc_convert(item[0]) # �ĳ���Ϊ��λ��utc
                new_duration += float(item[1]['fileinfos']['duration'])
                adjacent_files.append(item[1]['fileinfos']['name'])
                event_dict = copy.deepcopy(item[1])
                last_end = new_utc + new_duration #last_endΪ�����Ƭ����ʱ��
                #width = item[1]['rotation_infos'][0]['width'] # Ϊʲô�ǵ�һ����ת�������Ĳ�����
                #height = item[1]['rotation_infos'][0]['height']
            
            #utc�����ҷ�װ��ʽ��ͬ
            elif (abs(helper.utc_convert(item[0]) - last_end) <= 0.001)\
                    and item[1]['fileinfos']['suffix'] == event_dict['fileinfos']['suffix']:
                adjacent_files.append(item[1]['fileinfos']['name'])
                new_duration += float(item[1]['fileinfos']['duration'])
                last_end = new_utc + new_duration
            
            # ������ʱ
            #�ϲ���Ƶ��Ƭ�ķ�ʽΪ��������Ƭ����cat��һ�����ļ���
            else:
                # ���ļ�����
                file_name = event_dict['fileinfos']['name'] + "_concat." + event_dict['fileinfos']['suffix']
                '''
                cat xxxx.ts xxxxx.ts >> file_name
                '''
                cmd = "cat "
                for ts_file in adjacent_files:
                    cmd += ts_file + " "
                cmd += ">> " + file_name
                print(cmd)
                subprocess.Popen(cmd, shell=True, env=None).wait()
                # �����൱�ڰ�Ŀǰ����������ts�ļ��ϳ�һ�����ts�ļ�

                #os.system("rm -f " + concat_file)
                event_dict['fileinfos']['name'] = file_name
                event_dict['fileinfos']['duration'] = new_duration
                new_video_mediafile_dict[first_utc] = copy.deepcopy(event_dict)
                # �Ѻϲ�����mediafile��Ϣ����new_video_mediafile_dict

                temp_file.append(file_name + '\n')
                # ˢ��adjacent_files
                adjacent_files = []
                adjacent_files.append(item[1]['fileinfos']['name'])

                first_utc = item[0]
                new_utc = helper.utc_convert(item[0])
                new_duration = float(item[1]['fileinfos']['duration'])
                last_end = new_utc + new_duration
                event_dict = copy.deepcopy(item[1])
        
        # �������һ��ʱ�ε���Ƶ�ļ�
        if new_utc != 0.0:
            file_name = event_dict['fileinfos']['name'] + "_concat." + event_dict['fileinfos']['suffix']
            cmd = "cat "
            for ts_file in adjacent_files:
                cmd += ts_file + " "
            cmd += ">> " + file_name
            print(cmd)
            subprocess.Popen(cmd, shell=True, env=None).wait()
            adjacent_files = []
            event_dict['fileinfos']['name'] = file_name
            event_dict['fileinfos']['duration'] = new_duration
            new_video_mediafile_dict[first_utc] = copy.deepcopy(event_dict)

            #
            # ����video_mediafile_dict
            #
            if self.file_type == 'video_main':
                self.video_main_mediafile_dict = {}
                self.video_main_mediafile_dict.update(new_video_mediafile_dict)
            elif self.file_type == 'video_aux':
                self.video_aux_mediafile_dict = {}
                self.video_aux_mediafile_dict.update(new_video_mediafile_dict)

            temp_file.append(file_name + '\n')

        if len(temp_file) > 0:
            fd = open(self.middle_file,'a')
            fd.writelines(temp_file)
            fd.close()

    def is_media_file_info(self, lineinfo, event_dict):
        audio_result = self.regex_audio_file_name_pat.match(lineinfo)
        video_main_result = self.regex_video_main_file_name_pat.match(lineinfo)
        video_aux_result = self.regex_video_aux_file_name_pat.match(lineinfo)

        if audio_result:
            if not os.path.isfile(audio_result.group(0)):
                return True
            utc = audio_result.group(1)
            event_dict['fileinfos']['name'] = audio_result.group(0)
            event_dict['fileinfos']['suffix'] = audio_result.group(2)
            event_dict['fileinfos']['type'] = 'audio'

            self.audio_mediafile_dict[utc] = copy.deepcopy(event_dict)
            return True

        elif video_main_result:
            if not os.path.isfile(video_main_result.group(0)):
                return True
            utc = video_main_result.group(1)
            event_dict['fileinfos']['name'] = video_main_result.group(0)
            event_dict['fileinfos']['suffix'] = video_main_result.group(2)
            event_dict['fileinfos']['type'] = 'video_main' 

            self.video_main_mediafile_dict[utc] = copy.deepcopy(event_dict)
            return True

        elif video_aux_result:
            if not os.path.isfile(video_aux_result.group(0)):
                return True
            utc = video_aux_result.group(1)
            event_dict['fileinfos']['name'] = video_aux_result.group(0)
            event_dict['fileinfos']['suffix'] = video_aux_result.group(2)
            event_dict['fileinfos']['type'] = 'video_aux'

            self.video_aux_mediafile_dict[utc] = copy.deepcopy(event_dict)
            return True
        else:
            return False


    def is_event_info(self, lineinfo, event_dict):
        #��ʱֻ��һ��event_info
        file_duration_result = self.regex_track_file_duration_pat.match(lineinfo)
        
        if file_duration_result:
            if not event_dict.has_key('fileinfos'):
                event_dict['fileinfos'] = {}
            event_dict['fileinfos']['duration'] = file_duration_result.group(1)
            return True
        else:
            return False
