#!/usr/bin/env python3
# encoding:utf-8

import json
import requests
import os
import time
import random
import plugins
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from common.tmp_dir import TmpDir
from plugins import *

@plugins.register(
    name="EnglishAudio",
    desire_priority=100,
    desc="输入关键词'英语 模块编号'即可获取对应英语音频，例如：英语 M1U1",
    version="1.0",
    author="AI Assistant",
)
class EnglishAudio(Plugin):
    def __init__(self):
        super().__init__()
        self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
        self.config_file = os.path.join(os.path.dirname(__file__), "config.json")
        self.audio_map = self.load_config()
        logger.info("[EnglishAudio] 插件已初始化")

    def load_config(self):
        """
        加载配置文件
        :return: 配置字典
        """
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                logger.info(f"[EnglishAudio] 成功加载配置文件，包含 {len(config)} 个音频条目")
                return config
        except Exception as e:
            logger.error(f"[EnglishAudio] 加载配置文件失败: {e}")
            return {}

    def download_audio(self, audio_url, module_name):
        """
        下载音频文件并返回文件路径
        :param audio_url: 音频文件URL
        :param module_name: 模块名称（用于文件名）
        :return: 音频文件保存路径或None（如果下载失败）
        """
        try:
            # 检查URL是否有效
            if not audio_url or not audio_url.startswith('http'):
                logger.error(f"[EnglishAudio] 无效的音频URL: {audio_url}")
                return None

            # 发送GET请求下载文件，添加超时和重试机制
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            for retry in range(3):  # 最多重试3次
                try:
                    response = requests.get(audio_url, stream=True, headers=headers, timeout=30)
                    response.raise_for_status()  # 检查响应状态
                    break
                except requests.RequestException as e:
                    if retry == 2:  # 最后一次重试
                        logger.error(f"[EnglishAudio] 下载音频文件失败，重试次数已用完: {e}")
                        return None
                    logger.warning(f"[EnglishAudio] 下载重试 {retry + 1}/3: {e}")
                    time.sleep(1)  # 等待1秒后重试
            
            # 使用TmpDir().path()获取正确的临时目录
            tmp_dir = TmpDir().path()
            
            # 生成唯一的文件名，包含时间戳和随机字符串
            timestamp = int(time.time())
            random_str = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=6))
            audio_name = f"eng_{module_name}_{timestamp}_{random_str}.mp3"
            audio_path = os.path.join(tmp_dir, audio_name)
            
            # 保存文件，使用块写入以节省内存
            total_size = 0
            with open(audio_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)
                        total_size += len(chunk)
            
            # 验证文件大小
            if total_size == 0:
                logger.error("[EnglishAudio] 下载的文件大小为0")
                os.remove(audio_path)  # 删除空文件
                return None
                
            logger.info(f"[EnglishAudio] 音频下载完成: {audio_path}, 大小: {total_size/1024:.2f}KB")
            return audio_path
            
        except Exception as e:
            logger.error(f"[EnglishAudio] 下载音频文件时出错: {e}")
            # 如果文件已创建，清理它
            if 'audio_path' in locals() and os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                except Exception as clean_error:
                    logger.error(f"[EnglishAudio] 清理失败的下载文件时出错: {clean_error}")
            return None

    def on_handle_context(self, e_context: EventContext):
        """
        处理用户消息
        :param e_context: 事件上下文
        """
        if e_context["context"].type != ContextType.TEXT:
            return
            
        content = e_context["context"].content.strip()
        reply = Reply()
        reply.type = ReplyType.TEXT

        # 检查是否是英语音频请求
        if content.startswith("英语 ") or content.startswith("英语") or content.startswith("英语听力") or content.startswith("英语测试"):
            # 提取模块编号
            module_code = content.replace("英语听力", "").replace("英语测试", "").replace("英语", "").strip()
            
            # 如果没有提供模块编号，返回可用的模块列表
            if not module_code:
                available_modules = ", ".join(sorted(self.audio_map.keys()))
                reply.content = f"请指定模块编号，可用的模块有: {available_modules}"
                e_context["reply"] = reply
                e_context.action = EventAction.BREAK_PASS
                return
            
            # 查找对应的音频URL
            audio_url = self.audio_map.get(module_code)
            if not audio_url:
                # 处理听力音频请求
                if "听力" in content:
                    # 处理形如 "1-1" 或 "1.1" 的格式
                    parts = module_code.replace("-", ".").split(".")
                    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                        module_num, unit_num = parts
                        potential_code = f"M{module_num}U{unit_num}L"
                        if potential_code in self.audio_map:
                            audio_url = self.audio_map[potential_code]
                            module_code = potential_code
                            logger.info(f"[EnglishAudio] 匹配听力音频: {module_code}")
                    # 处理形如 "1" 的格式，尝试匹配 M1U1L 或 M1U2L
                    elif module_code.isdigit():
                        potential_codes = [f"M{module_code}U1L", f"M{module_code}U2L"]
                        for code in potential_codes:
                            if code in self.audio_map:
                                audio_url = self.audio_map[code]
                                module_code = code
                                logger.info(f"[EnglishAudio] 匹配听力音频: {module_code}")
                                break
                    # 处理形如 "M1U1" 的格式
                    else:
                        # 如果输入的是标准模块格式（如M1U1），自动添加L后缀
                        if module_code.startswith('M') and 'U' in module_code:
                            potential_code = f"{module_code}L"
                            if potential_code in self.audio_map:
                                audio_url = self.audio_map[potential_code]
                                module_code = potential_code
                                logger.info(f"[EnglishAudio] 匹配听力音频: {module_code}")
                # 处理测试卷请求
                elif "测试" in content or "test" in content.lower():
                    # 处理期中期末测试卷
                    if "期中" in module_code or "mid" in module_code.lower():
                        if "MT1" in self.audio_map:
                            audio_url = self.audio_map["MT1"]
                            module_code = "MT1"
                            logger.info(f"[EnglishAudio] 匹配期中测试卷音频")
                    elif "期末" in module_code or "final" in module_code.lower():
                        if "MT2" in self.audio_map:
                            audio_url = self.audio_map["MT2"]
                            module_code = "MT2"
                            logger.info(f"[EnglishAudio] 匹配期末测试卷音频")
                    # 处理模块测试卷
                    elif module_code.isdigit():
                        potential_code = f"M{module_code}T"
                        if potential_code in self.audio_map:
                            audio_url = self.audio_map[potential_code]
                            module_code = potential_code
                            logger.info(f"[EnglishAudio] 匹配模块测试卷音频: {module_code}")
                    # 处理形如 "M1" 的格式
                    elif module_code.startswith('M') and module_code[1:].isdigit():
                        potential_code = f"{module_code}T"
                        if potential_code in self.audio_map:
                            audio_url = self.audio_map[potential_code]
                            module_code = potential_code
                            logger.info(f"[EnglishAudio] 匹配模块测试卷音频: {module_code}")
                # 处理普通请求
                else:
                    if module_code.isdigit():
                        # 尝试匹配 M{module_code}U1, M{module_code}U2, M{module_code}W
                        potential_codes = [
                            f"M{module_code}U1", 
                            f"M{module_code}U2", 
                            f"M{module_code}W"
                        ]
                        for code in potential_codes:
                            if code in self.audio_map:
                                audio_url = self.audio_map[code]
                                module_code = code
                                logger.info(f"[EnglishAudio] 自动补全模块编号: {module_code}")
                                break
                    # 处理 "单词" 或 "words" 关键词
                    elif "单词" in module_code.lower() or "words" in module_code.lower():
                        # 提取数字部分
                        for part in module_code.split():
                            if part.isdigit():
                                potential_code = f"M{part}W"
                                if potential_code in self.audio_map:
                                    audio_url = self.audio_map[potential_code]
                                    module_code = potential_code
                                    logger.info(f"[EnglishAudio] 匹配单词音频: {module_code}")
                                    break
                    # 处理特殊关键词
                    elif "专有名词" in module_code.lower() or "proper" in module_code.lower():
                        if "Proper nouns" in self.audio_map:
                            audio_url = self.audio_map["Proper nouns"]
                            module_code = "Proper nouns"
                            logger.info(f"[EnglishAudio] 匹配专有名词音频")
                    elif "歌曲" in module_code.lower() or "朗诵" in module_code.lower() or "songs" in module_code.lower() or "chants" in module_code.lower():
                        if "Words in songs and chants" in self.audio_map:
                            audio_url = self.audio_map["Words in songs and chants"]
                            module_code = "Words in songs and chants"
                            logger.info(f"[EnglishAudio] 匹配歌曲和朗诵单词音频")
            
            if audio_url:
                logger.info(f"[EnglishAudio] 找到模块 {module_code} 的音频: {audio_url}")
                
                # 下载音频文件
                audio_path = self.download_audio(audio_url, module_code)
                
                if audio_path:
                    # 返回语音消息
                    # 注意：框架会自动将MP3文件转换为silk格式进行发送
                    # 只需设置reply.type为ReplyType.VOICE，并将MP3文件路径设置为reply.content即可
                    reply.type = ReplyType.VOICE
                    reply.content = audio_path
                    logger.info(f"[EnglishAudio] 发送音频: {module_code}")
                else:
                    reply.content = f"下载音频失败，请稍后重试"
            else:
                available_modules = ", ".join(sorted(self.audio_map.keys()))
                reply.content = f"未找到模块 {module_code} 的音频，可用的模块有: {available_modules}"
            
            e_context["reply"] = reply
            e_context.action = EventAction.BREAK_PASS
            return

    def get_help_text(self, **kwargs):
        """
        返回插件的帮助信息
        :param kwargs: 参数字典
        :return: 帮助信息
        """
        help_text = "📢 英语音频\n"
        help_text += "使用方法：\n"
        help_text += "1. 发送 '英语 模块编号' 获取对应英语音频，例如：英语 M1U1\n"
        help_text += "2. 发送 '英语' 获取所有可用的模块列表\n"
        help_text += "3. 单元音频：英语 M1U1, 英语 1 (自动匹配)\n"
        help_text += "4. 单词音频：英语 M1W, 英语 1单词 (自动匹配)\n"
        help_text += "5. 听力音频：英语听力 M1U1, 英语听力 1-1, 英语听力 1 (自动匹配)\n"
        help_text += "6. 测试卷：英语测试 M1, 英语测试 1 (自动匹配)\n"
        help_text += "7. 期中期末：英语测试 期中, 英语测试 期末\n"
        help_text += "8. 特殊音频：英语 专有名词, 英语 歌曲单词\n"
        help_text += f"当前可用模块：{', '.join(sorted(self.audio_map.keys()))}"
        return help_text 