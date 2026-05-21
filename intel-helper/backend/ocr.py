"""
OCR 模块 - 可替换的 OCR 提供者接口
"""
import os
import re
import hashlib
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from PIL import Image, ImageEnhance, ImageFilter
import pytesseract


@dataclass
class OCRResult:
    """OCR 结果"""
    raw_text: str
    confidence: int  # 0-100
    extracted_data: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_text": self.raw_text,
            "confidence": self.confidence,
            "extracted_data": self.extracted_data
        }


class OCRProvider(ABC):
    """OCR 提供者基类"""

    @abstractmethod
    def extract_text(self, image_path: str) -> str:
        """从图片提取文字"""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """获取提供者名称"""
        pass


def preprocess_image(img: Image.Image) -> Image.Image:
    """图片预处理"""
    original_w, original_h = img.size
    
    # 放大图片（战报截图通常文字较小）
    scale = min(3.0, 1500 / original_w)
    if scale > 1:
        new_size = (int(original_w * scale), int(original_h * scale))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
    
    # 转灰度
    img = img.convert('L')
    
    # 增强对比度
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.5)
    
    # 去噪
    img = img.filter(ImageFilter.MedianFilter(size=3))
    
    # 锐化
    img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
    
    return img


class LocalOCRProvider(OCRProvider):
    """本地 Tesseract OCR"""

    def __init__(self, tesseract_path: Optional[str] = None):
        self.tesseract_path = tesseract_path or os.getenv("TESSERACT_PATH") or r"E:\ocr\tesseract.exe"
        if self.tesseract_path and os.path.exists(self.tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_path

        self.available = self._check_available()

    def _check_available(self) -> bool:
        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def extract_text(self, image_path: str) -> str:
        """使用 Tesseract 提取文字"""
        if not self.available:
            raise RuntimeError("Tesseract OCR 不可用")

        try:
            img = Image.open(image_path)
            processed = preprocess_image(img)
            
            # 尝试多种 PSM 模式，取最优结果
            results = []
            psm_modes = [11, 6, 3, 12]  # 按效果排序
            
            for psm in psm_modes:
                try:
                    text = pytesseract.image_to_string(
                        processed,
                        lang="chi_sim+eng",
                        config=f"--psm {psm} --oem 3"
                    )
                    cleaned = self._clean_text(text)
                    if cleaned.strip():
                        # 计算有效字符比例
                        valid_ratio = sum(1 for c in cleaned if self._is_valid_char(c)) / max(len(cleaned), 1)
                        results.append((cleaned, valid_ratio))
                except:
                    continue
            
            # 取有效字符比例最高的
            if results:
                best_text = max(results, key=lambda x: x[1])[0]
            else:
                best_text = ""
            
            return best_text
            
        except Exception as e:
            raise RuntimeError(f"Tesseract OCR 处理失败: {str(e)}")

    def _clean_text(self, text: str) -> str:
        """清理 OCR 识别文本"""
        lines = []
        for line in text.split('\n'):
            cleaned = ''.join(c for c in line if self._is_valid_char(c))
            if cleaned.strip():
                lines.append(cleaned)
        return '\n'.join(lines)
    
    def _is_valid_char(self, c: str) -> bool:
        if c == ' ' or c == '\n':
            return True
        if '\u4e00' <= c <= '\u9fff':
            return True
        if c.isascii():
            return True
        if c in '【】()（）[]':
            return True
        return False

    def get_provider_name(self) -> str:
        return f"local_tesseract ({self.tesseract_path})"


class MockOCRProvider(OCRProvider):
    def extract_text(self, image_path: str) -> str:
        return (
            "恭喜玩家123\n"
            "同盟: 天下无双\n"
            "赛季: S3\n"
            "大营: 马超\n"
            "中军: 曹操\n"
            "前锋: 刘备\n"
            "战果: 胜利\n"
        )

    def get_provider_name(self) -> str:
        return "mock"


class OCREngine:
    """OCR 引擎"""

    # 已知的武将名列表
    KNOWN_HERO_NAMES = [
        # 魏国
        "曹操", "司马懿", "曹丕", "曹仁", "夏侯惇", "夏侯渊", "张辽", "徐晃", "许褚", "典韦",
        "张郃", "于禁", "乐进", "李典", "荀彧", "荀攸", "郭嘉", "贾诩", "程昱", "刘晔",
        "满宠", "蒋济", "陈群", "华歆", "王朗", "钟繇", "杜袭", "郑浑", "任峻", "枣祗",
        "荀顗", "陈矫", "徐宣", "卫臻", "卢毓", "王粲", "吴质", "应瑒", "陈琳", "阮瑀",
        # 蜀国
        "刘备", "关羽", "张飞", "赵云", "马超", "黄忠", "诸葛亮", "庞统", "魏延", "姜维",
        "关平", "关兴", "张苞", "周仓", "廖化", "马谡", "王平", "马岱", "吴懿", "吴兰",
        "雷铜", "吴臣", "刘封", "孟达", "法正", "简雍", "孙乾", "糜竺", "伊籍", "马良",
        "陈震", "杨仪", "费祎", "蒋琬", "董允", "郭攸之", "黄权", "李严", "费诗", "谯周",
        "郤正", "张裔", "秦宓", "杜微", "杜琼", "许靖", "李恢", "吕凯", "庞义", "张嶷",
        # 吴国
        "孙权", "孙策", "孙坚", "周瑜", "陆逊", "鲁肃", "吕蒙", "甘宁", "太史慈", "黄盖",
        "程普", "韩当", "周泰", "蒋钦", "陈武", "董袭", "徐盛", "丁奉", "凌统", "潘璋",
        "陆绩", "顾雍", "张昭", "步骘", "诸葛瑾", "严畯", "阚泽", "薛综", "程秉", "严峻",
        "张纮", "秦松", "陈端", "虞翻", "王惇", "吾粲", "朱桓", "朱然", "陆抗",
        "陆凯", "丁姬", "孙鲁育", "孙鲁班", "全琮", "朱据", "孙和", "孙亮", "孙皓",
        "大乔", "小乔", "周姬", "吴景", "潘后", "步练师", "张昭", "张悌", "张布",
        "朱异", "朱潘", "朱损", "朱纪", "孙检", "孙越", "孙恭", "孙申", "孙和行为",
        "陆景", "陆式", "陆冒", "陆留", "陆氏", "陆恭", "陆效", "陆兆", "陆元", "陆康",
        # 群雄
        "吕布", "貂蝉", "董卓", "李儒", "李傕", "郭汜", "张济", "樊稠", "牛辅",
        "董旻", "徐荣", "胡轸", "杨定", "段煨", "李蒙", "王方", "胡才", "李别", "李暹",
        "袁绍", "袁术", "袁尚", "袁熙", "袁谭", "逢纪", "审配", "田丰", "沮授", "许攸",
        "颜良", "文丑", "麴义", "淳于琼", "韩猛", "吕翔", "焦触",
        "张南", "董昭", "祢衡", "陈宫", "张邈", "陈登", "孔融",
        "王修", "张绣", "胡车儿", "高顺", "魏续",
        "宋宪", "侯成", "高干", "郭援", "眭固", "郝萌", "曹性",
        "纪灵", "陈兰", "雷薄", "桥蕤", "李丰", "乐就", "梁刚",
        "张勋", "朱儁", "皇甫嵩", "卢植", "张角", "张宝",
        "张梁", "波才", "彭脱",
        # 晋
        "司马昭", "司马师", "司马炎", "邓艾", "钟会", "王基",
        "王昶", "毌丘俭", "诸葛诞", "文钦", "唐咨",
        # 特殊武将
        "关银屏", "关凤", "马云禄", "月英", "黄月英", "诸葛果", "徐庶", "庞德", "蔡文姬", "甄洛",
        "张春华", "王异", "辛敞", "刘禅", "关索", "张姬", "灵帝", "何太后",
        "SP武将", "SP张飞", "SP关羽", "SP赵云", "SP曹操", "SP刘备", "SP孙权",
        "黄舞蝶", "赵晃", "周旨", "黄祖", "刘表", "刘琦", "蔡瑁", "蒯越", "蒯良",
        # 武将简称（单字）
        "懿", "丕", "仁", "惇", "渊", "辽", "晃", "褚", "韦",
        "郃", "禁", "进", "典", "彧", "攸", "嘉", "诩", "昱", "晔",
    ]

    def __init__(self, provider: str = None):
        provider = provider or os.getenv("OCR_PROVIDER", "local")
        
        if provider == "mock":
            self.provider = MockOCRProvider()
        else:
            self.provider = LocalOCRProvider()

        self._init_extractor()

    def _init_extractor(self):
        self.hero_names_set = set(self.KNOWN_HERO_NAMES)
        self.alliance_pattern = re.compile(r'【([^】]+)】')

    def process_image(self, image_path: str) -> OCRResult:
        image_hash = self._calculate_hash(image_path)
        raw_text = self.provider.extract_text(image_path)
        
        valid_chars = sum(1 for c in raw_text if self._is_valid_char(c))
        confidence = int((valid_chars / max(len(raw_text), 1)) * 100)
        
        extracted_data = self._extract_data(raw_text)
        
        return OCRResult(raw_text, confidence, extracted_data)

    def _calculate_hash(self, image_path: str) -> str:
        with open(image_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()[:12]

    def _extract_data(self, text: str) -> Dict[str, Any]:
        # 移除空格
        text_no_space = text.replace(" ", "")
        lines = text.split("\n")
        clean_lines = [line.strip() for line in lines if line.strip()]

        result = {
            "player_name": None,
            "alliance": None,
            "heroes": [],
            "server": None
        }

        # 1. 提取武将名
        heroes = []
        sorted_heroes = sorted(self.KNOWN_HERO_NAMES, key=len, reverse=True)
        
        # 优先匹配长名称
        for hero_name in sorted_heroes:
            # 检查无空格版本
            if hero_name in text_no_space and hero_name not in heroes:
                heroes.append(hero_name)
            # 也检查带空格版本（武将名被空格分开的情况）
            elif hero_name.replace("", " ") in text and hero_name not in heroes:
                heroes.append(hero_name)
        
        result["heroes"] = list(set(heroes))[:5]

        # 2. 提取同盟名
        match = self.alliance_pattern.search(text)
        if match:
            alliance = match.group(1).replace(" ", "")
            if "胜利" not in alliance and "失败" not in alliance:
                result["alliance"] = alliance

        # 3. 提取玩家名
        skip_keywords = ["恭喜", "同盟", "联盟", "赛季", "武将", "战报", "结果", "胜", "负", "平", 
                        "经验", "同盟经验", "胜利", "失败", "平局", "大营", "中军", "前锋", 
                        "位置", "战况", "兵力", "等级", "战报详情", "占领", "土地", "我方",
                        "吴", "蜀", "魏", "群", "河", "图", "文", "前", "中", "大"]
        
        # 查找包含武将名但不是纯乱码的行
        for line in clean_lines[2:12]:
            clean_line = line.replace(" ", "")
            # 跳过数字行
            if re.match(r"^\d+[\/\d]*$", clean_line):
                continue
            # 跳过太短的行
            if len(clean_line) < 3:
                continue
            # 跳过包含小写字母的行（乱码）
            if any(c.islower() for c in clean_line):
                continue
            if clean_line in self.hero_names_set:
                continue
            if any(kw in clean_line for kw in skip_keywords):
                continue
            # 跳过包含太多数字的行
            digit_count = sum(1 for c in clean_line if c.isdigit())
            if digit_count > len(clean_line) * 0.3:
                continue
            if 2 <= len(clean_line) <= 15:
                result["player_name"] = clean_line
                break

        return result

    def _is_common_char(self, c: str) -> bool:
        """判断是否是常用字符（排除乱码）"""
        if c == ' ' or c == '\n':
            return True
        if '\u4e00' <= c <= '\u9fff':
            return True
        if c.isascii():
            return True
        if c in '【】()（）[]':
            return True
        return False

    def _is_valid_char(self, c: str) -> bool:
        if c == ' ' or c == '\n':
            return True
        if '\u4e00' <= c <= '\u9fff':
            return True
        if c.isascii():
            return True
        if c in '【】()（）[]':
            return True
        return False


def normalize_name(name: str) -> str:
    if not name:
        return ""
    name = name.strip()
    for prefix in ['★', '☆']:
        if name.startswith(prefix):
            name = name[1:]
    return name.strip()
