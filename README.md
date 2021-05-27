# M3U8_MERGE

##  云端录制工具使用方法
    
-   ./trtc_mixer_test -g 33520 -t 30000 -m 0 -r 0 -e product  
   
### 参数说明 
    -g 指定房间号，需要和推流的sdk进同一个房间
    -t 指定录制的时间，单位是ms
    -m 0 固定用0
    -r 0 固定用0
    -e product 固定
            
-   文件会保存在/dev/shm/hls/8000目录下
        
-   操作步骤
          1、sdk进到房间，选择视频会议。
          2、然后启动trtc_mixer_test。进入相同房间。等待录制完成。

## M3U8_MERGE工具使用方法

-   单流录制模式下，每个uid的音频数据和视频数据分开存储，音视频合并转码脚本可以合并每个 uid 的音频文件和视频文件。
    
### 使用方法： 
    1、通过云端录制工具获得录制文件（/dev/shm/hls/8000目录下）；
    2、解压合并压缩文件，推荐使用压缩文件中的ffmpeg工具；
    3、运行合并脚本：python merge.py [option] 
    4、会在录制文件目录下生成合并后的mp4文件。
> 如：python merge.py -m 0 -b
     
-   [option]的可选参数和对应功能见下表。

|参数| 功能 |
|--|--|
|-f | 指定待合并文件的存储路径。如果有多个uid的录制文件，脚本均会对其进行转码。 |
|-m   | 0：分段模式。此模式下，脚本将每个uid下的录制文件按Segment合并。<br> <br>1：合并模式。一个uid下的所有音视频文件转换为一个文件，每段之间的空白部分用静音包和黑帧填充。|
|-s|保存模式。如果设置了该参数，则合并模式下的Segment之间的空白部分被删除，文件的实际时常小于物理时常。|
|-a|辅流模式。如果设置了该参数，则启用辅流。当主流视频存在时，正常合并主流视频和音频；当主流视频不存在且辅流存在时，使用辅流文件与音频合并。|
|-p|指定输出视频的fps。默认为15 fps，有效范围5-120 fps，低于5 fps计为5 fps，高于120 fps计为120 fps。|
|-r|指定输出视频的分辨率。如 -r 640 360，表示输出视频的宽为640，高为360。默认分辨率为640x360。|
|-b|黑帧填充模式。如果设置了该参数，则空白部分改由黑帧填充。（只对Segment中的间隙有效，默认是上个视频的最后一帧）|

### 功能描述  
> 首先介绍一下视频段（Segment）的概念：如果两个切片之间的时间间隔超过15秒，间隔时间内没有任何音频/视频信息（如果没有开启辅流模式，会忽略辅流信息），我们把这两个切片看作两个不同的Segment。其中，录制时间较早的切片看作前一个Segment的结束切片，录制时间较晚的切片看作后一个Segment的开始切片。

 - 分段模式（-m 0）
此模式下，脚本将每个uid下的录制文件按Segment合并。一个uid下的Segment被独立合并为一个文件，文件名为 uid_timestamp_av.mp4。其中，uid为用户唯一编号，timestamp为Segment开始录制的时间。
            
-   合并模式（-m 1）
把同一个uid下的所有Segment段合并为一个音视频文件。可利用 -s 选项选择是否填充各个Segment之间的间隔。
            
-   黑帧填充模式（-b）
合并过程中，有几种情况下需要对填充视频做填充处理。
		
		1、分段模式且没有启用辅流，Segment中某个片段没有主流视频时；
		2、分段模式且启用辅流，Segment中某个片段既没有主流视频也没有辅流视频时；
		3、合并模式且没有设置 -s 参数，合并各个Segment时。
                
	情况1、2，默认填充模式为使用之前视频的最后一帧填充，如果设置了 -b 参数，则在间隔处展示黑帧。
	
	情况3，**始终**用黑帧填充。


