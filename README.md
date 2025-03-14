# EnglishAudio 插件

> 本项目是 [dify-on-wechat](https://github.com/hanfangyuan4396/dify-on-wechat) 的插件项目，用于获取英语音频资源。项目思路来源于 [SearchMusic](https://github.com/Lingyuzhou111/SearchMusic) 项目，特此感谢。

这是一个用于获取任意音频的插件，可以根据模块编号获取对应的音频文件并以语音方式发送。(目前为英语音频)

## 功能特点

- 通过简单的命令获取音频
- 支持自动补全模块编号
- 提供完整的模块列表查询
- 自动下载并转换为语音消息发送

## 使用方法

1. 发送 `模块编号` 获取对应英语音频，例如：`英语 M1U1`
2. 发送 `英语` 获取所有可用的模块列表[该关键字可自行在源码中修改]
3. 也可以简化输入，例如：
   - 单元音频：`英语 1` 会自动匹配 M1U1 或 M1U2[value和key可自行在config.json中修改]
   - 单词音频：`英语 1单词` 会匹配 M1W
   - 听力音频：`英语听力 1-1` 会匹配 M1U1L
   - 测试卷：`英语测试 1` 会匹配 M1T

## 安装方法

1. 将整个 `EnglishAudio` 文件夹复制到 `plugins` 目录下
2. 重启应用程序

## 语音消息配置

> 以下源码修改方案来源于：[SearchMusic 部署教程](https://rq4rfacax27.feishu.cn/wiki/L4zFwQmbKiZezlkQ26jckBkcnod?fromScene=spaceOverview)

需要对 gewechat 源码进行以下修改：

### 1. 安装依赖

```bash
# 安装处理音频文件的必要依赖
sudo yum install ffmpeg   # FFmpeg用于处理音频、视频和其他多媒体文件
pip3 install pydub        # pydub用于简单、高效地处理音频文件
pip3 install pilk         # pilk用于处理微信语音文件（.silk格式）
```

### 2. 修改 gewechat_channel.py 文件

1. 增加依赖支持，在原有导入语句中添加：
```python
import uuid
import threading
import glob
from voice.audio_convert import mp3_to_silk, split_audio
```

2. 添加临时文件清理任务：
```python
def _start_cleanup_task(self):
    """启动定期清理任务"""
    def _do_cleanup():
        while True:
            try:
                self._cleanup_audio_files()
                self._cleanup_video_files()
                self._cleanup_image_files()
                time.sleep(30 * 60)  # 每30分钟执行一次清理
            except Exception as e:
                logger.error(f"[gewechat] 清理任务异常: {e}")
                time.sleep(60)

    cleanup_thread = threading.Thread(target=_do_cleanup, daemon=True)
    cleanup_thread.start()
```

3. 添加音频文件清理方法：
```python
def _cleanup_audio_files(self):
    """清理过期的音频文件"""
    try:
        tmp_dir = TmpDir().path()
        current_time = time.time()
        max_age = 3 * 60 * 60  # 音频文件最大保留3小时

        for ext in ['.mp3', '.silk']:
            pattern = os.path.join(tmp_dir, f'*{ext}')
            for fpath in glob.glob(pattern):
                try:
                    if current_time - os.path.getmtime(fpath) > max_age:
                        os.remove(fpath)
                        logger.debug(f"[gewechat] 清理过期音频文件: {fpath}")
                except Exception as e:
                    logger.warning(f"[gewechat] 清理音频文件失败 {fpath}: {e}")
    except Exception as e:
        logger.error(f"[gewechat] 音频文件清理任务异常: {e}")
```

### 3. 修改 audio_convert.py 文件

优化音频转换效果，提升音质（将采样率从24000提升至32000）：

```python
def mp3_to_silk(mp3_path: str, silk_path: str) -> int:
    """转换MP3文件为SILK格式，并优化音质"""
    try:
        audio = AudioSegment.from_file(mp3_path)
        audio = audio.set_channels(1)
        audio = audio.set_frame_rate(32000)
        
        pcm_path = os.path.splitext(mp3_path)[0] + '.pcm'
        audio.export(pcm_path, format='s16le', parameters=["-acodec", "pcm_s16le", "-ar", "32000", "-ac", "1"])
        
        try:
            pilk.encode(pcm_path, silk_path, pcm_rate=32000, tencent=True, complexity=2)
            duration = pilk.get_duration(silk_path)
            if duration <= 0:
                raise Exception("Invalid SILK duration")
            return duration
        finally:
            if os.path.exists(pcm_path):
                try:
                    os.remove(pcm_path)
                except Exception as e:
                    logger.warning(f"[audio_convert] 清理PCM文件失败: {e}")
    except Exception as e:
        logger.error(f"[audio_convert] MP3转SILK失败: {e}")
        return 0
```

这些修改将提供以下优化：
1. 支持语音消息的自动分段发送
2. 提高音频转换质量
3. 自动清理临时文件
4. 优化发送间隔

## 配置文件

插件使用 `config.json` 文件存储音频链接映射，格式为：

```json
{
  "模块编号": "音频链接",
  ...
}
```

您可以根据需要修改 `config.json` 文件：
1. 添加或更新音频链接
2. 自定义每个键（key）对应的值（value）
3. value 可以是任意字符串，比如：
   - 本地文件路径：`"M1U1": "D:/audio/module1/unit1.mp3"`
   - 网络URL：`"M1U1": "https://example.com/audio/m1u1.mp3"`
   - 相对路径：`"M1U1": "./audio/m1u1.mp3"`
   - 其他自定义格式：`"M1U1": "audio_id:12345"`

只要确保您的应用程序能够正确处理这些值即可。



`config.json` 文件包含了所有音频资源的配置信息。出于安全考虑，所有URL均已被移除。每个键值对中的值（value）可以根据您的需求自定义，支持本地文件路径、网络URL、相对路径或其他任何格式的字符串。

The `config.json` file contains configuration information for all audio resources. All URLs have been removed for security reasons. The value in each key-value pair can be customized according to your needs, supporting local file paths, network URLs, relative paths, or any other string format.

## 键名格式说明 (Key Name Format)

- `MxUy`: 模块x单元y的课文音频 (Module x Unit y text audio)
  - 例如 (Example): `M1U1` 表示模块1单元1的课文音频
- `MxW`: 模块x单词音频 (Module x words audio)
  - 例如 (Example): `M1W` 表示模块1的单词音频
- `MxUyL`: 模块x单元y听力练习 (Module x Unit y listening practice)
  - 例如 (Example): `M1U1L` 表示模块1单元1的听力练习
- `MxT`: 模块x综合测试 (Module x comprehensive test)
  - 例如 (Example): `M1T` 表示模块1的综合测试
- `MTx`: 期中/期末测试 (Midterm/Final test)
  - `MT1`: 期中测试 (Midterm test)
  - `MT2`: 期末测试 (Final test)


## 鸣谢
- [dify-on-wechat](https://github.com/hanfangyuan4396/dify-on-wechat) - 本项目的基础框架
- [SearchMusic](https://github.com/Lingyuzhou111/SearchMusic) - 项目思路来源
- [Gewechat](https://github.com/Devo919/Gewechat) - 微信机器人框架，个人微信二次开发的免费开源框架 

## 打赏
如果您觉得这个项目对您有帮助，欢迎打赏支持作者继续维护和开发更多功能！

![20250314_125818_133_copy](https://github.com/user-attachments/assets/33df0129-c322-4b14-8c41-9dc78618e220)

