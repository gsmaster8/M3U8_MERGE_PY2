# coding=utf-8
import time
import re
import os
import sys
import signal
import glob

import traceback
import parser_m3u8
from parser_uid_m3u8 import ParserUidM3U8File

class ParserFloderM3U8(object):
    '''all of m3u8 files has been stored in dict'''
    def __init__(self, folder_name, format='m3u8'):
        self.format = format
        self.path = folder_name
        self.metadata_fileformat = ParserUidM3U8File(format).get_fileformat()
        self.metadata_filepattern = ParserUidM3U8File(format).get_filepattern()
        self.metadata_filewithindexpatten = ParserUidM3U8File(format).get_filewithpatten()
        '''
        self.all_uid_metadatafiles = {
        'uid1':ParserUidM3U8File(format)
        'uid2':ParserUidM3U8File(format)
        }
        '''
        self.all_uid_metadatafiles = {}
        
        if not os.path.isdir(folder_name):
            raise IOError("Folder %s does not exist" %(folder_name))
    
    '''
    用于判断是否是空文件
    '''
    def get_file_size(self, file):
        size = 0
        try:
            size = os.path.getsize(file)
        except:
            pass
        return size

    '''
    提取所有的m3u8文件信息并返回
    '''
    def get_all_parse_files(self):
        os.chdir(self.path)
        # 对 所有m3u8文件 排序
        all_files = sorted(glob.glob(self.metadata_fileformat))

        # 根据 正则字符串 创建 模式对象
        filename_pat_reged = re.compile(self.metadata_filepattern)
        filename_with_index_pat_reged = re.compile(self.metadata_filewithindexpatten)
        format_files = {}

        for file in all_files:
            result = filename_pat_reged.match(file)
            if not result:
                result = filename_with_index_pat_reged.match(file)
            # 若格式正确 / 匹配
            if result:
                key = result.group(1) + result.group(2) + result.group(3) + result.group(4)
                if format_files.has_key(key):
                    if self.get_file_size(file) > self.get_file_size(format_files[key]['file']):
                        format_files[key]["file"] = file
                        # 如果文件冲突，选择带index的m3u8文件
                else:
                    file_info = {}
                    file_info["prefix"] = result.group(1)
                    file_info["uid"] = result.group(2)
                    file_info["stream_type"] = result.group(3)
                    file_info["av_type"] = result.group(4)
                    file_info["file"] = file
                    format_files[key] = file_info
        return format_files

    '''
    缓存所有m3u8文件的信息，并为其初始化M3U8File处理对象
    '''
    def parser_all_files(self):
        os.chdir(self.path)
        all_files = self.get_all_parse_files() # 获取所有m3u8文件

        for file in all_files.values():
            prefix = file["prefix"]
            uid = file["uid"]
            stream_type = file["stream_type"]
            av_type = file["av_type"]

            if not self.all_uid_metadatafiles.has_key(uid):
                self.all_uid_metadatafiles[uid] = ParserUidM3U8File(self.format, uid)

            # 为每个m3u8文件创建处理对象
            self.all_uid_metadatafiles[uid].update_filename_dict(stream_type, av_type, file["file"])

    def analysis_metadatafile(self):
        # 先分别缓存audio切片和video切片信息
        for metadatafile_per_uid in self.all_uid_metadatafiles.values():
            for m3u8_type in metadatafile_per_uid.filename_dict.keys():
                for mediafile_item in metadatafile_per_uid.filename_dict[m3u8_type].items():
                    mediafile_item[1].metadatafile_to_list(mediafile_item[0])

    def per_user_splited_metadata_dict_merged_in_one(self):
        # 把缓存的音视频信息合并
        for metadatafile_per_uid in self.all_uid_metadatafiles.values():
            metadatafile_per_uid.metadata_dict_merged_in_merged_dict()

    def per_user_merged_dict_splited_to_segment(self):
        # 把合并的信息按Segment切分
        for metadatafile_per_uid in self.all_uid_metadatafiles.values():
            metadatafile_per_uid.merged_dict_splited_to_segment()
    
    def create_middlefile_of_segments_in_all_uids(self):
        # 把缓存的Segment信息持久化进middle文件
        for metadatafile_per_uid in self.all_uid_metadatafiles.values():
            metadatafile_per_uid.create_middlefile_of_segments()

    def dispose(self):
        #stored in dict
        #进入 待合并文件目录 并将所有格式正确的 m3u8文件 的信息存入 all_uid_metadatafiles 中
        self.parser_all_files()
        #stored in cached buffer    
        self.analysis_metadatafile()
        #stored all corner case as one merged file
        self.per_user_splited_metadata_dict_merged_in_one()
        #split one merged file as segment per start key word
        self.per_user_merged_dict_splited_to_segment()
        #create the uid_xxx.txt
        self.create_middlefile_of_segments_in_all_uids()
 
def help():
    help_str='''Help:
    ./script dispose path
    eg.
     %s dispose .
    ''' %(sys.argv[0])
    print(help_str)

# 中间文件清理
def clean_func(folder_name):
    if not os.path.isdir(folder_name[1]):
        print "Folder " + folder_name[1] + " does not exist"
        return

    os.chdir(folder_name[1])
    media_file = "media_file.mf"
    if os.path.exists(media_file):
        f = open(media_file, "r")
        lines = f.readlines()
        for line in lines:
            os.system('rm -f %s' % line)
        os.system('rm -f %s' % media_file)
    all_uid_file = sorted(glob.glob("uid_*.txt"))
    for uid_file in all_uid_file:
        os.system('rm -f %s' % uid_file)

# 执行合并操作
def cmds1_func(cmds):
    parser = ParserFloderM3U8(cmds[1])
    parser.dispose()


def cmds_parse(input_cmd):
    dirname=r'[^ ]+'  # 正则
    cmds_func_list =  [
            [['dispose',dirname], cmds1_func],
            [['clean', dirname], clean_func]
            ]
    try:
        found=False
        for cmds_func in cmds_func_list:
            flag=True

            #skip different cmds_len
            if len(cmds_func[0]) != len(input_cmd):
#                print(cmds_func[0], input_cmd)
                continue

            #cmds len equal, but need to check param legal or not
            for pat,cmd_part in zip(cmds_func[0],input_cmd):
#                print(pat,cmd_part)
                if re.match(pat,cmd_part) == None:
                    flag=False
                    break

            if flag:
                found = True
                print("cmd pattern:%s" %(cmds_func[0]))
                print("input cmd:%s" %(input_cmd))

                cmds_func[1](input_cmd)  #调用相应的函数
                break

        if found == False:
            print("input cmds:%s" %input_cmd)
            help()
    except Exception as e:
        print("Error input:%s!" %e)
        print("input cmds:%s" %input_cmd)
        help()
        traceback.print_exc()



if '__main__' == __name__:
    import sys
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGQUIT, signal.SIG_IGN)
    cmds_parse(sys.argv[1:])

