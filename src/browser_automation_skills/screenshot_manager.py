"""
截图管理模块 - 自动保存失败测试截图
"""

import os
import base64
from datetime import datetime
from typing import Optional


class ScreenshotManager:
    """
    截图管理器

    功能：
    - 自动保存失败测试截图
    - 管理截图目录和命名
    - 提供截图路径和 base64 数据
    """

    def __init__(self, output_dir: str = "screenshots"):
        self.output_dir = output_dir
        self.screenshots: list = []

    def _ensure_dir(self):
        """确保输出目录存在"""
        os.makedirs(self.output_dir, exist_ok=True)

    def save_screenshot(self, screenshot_bytes: bytes, test_name: str,
                        step_name: str, success: bool) -> str:
        """
        保存截图

        Args:
            screenshot_bytes: 截图字节数据
            test_name: 测试名称
            step_name: 步骤名称
            success: 是否成功

        Returns:
            截图文件路径
        """
        self._ensure_dir()

        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        status = "pass" if success else "fail"
        filename = f"{timestamp}_{test_name}_{step_name}_{status}.png"
        filepath = os.path.join(self.output_dir, filename)

        # 保存文件
        with open(filepath, "wb") as f:
            f.write(screenshot_bytes)

        # 记录
        self.screenshots.append({
            "filepath": filepath,
            "filename": filename,
            "test_name": test_name,
            "step_name": step_name,
            "success": success,
            "timestamp": timestamp,
            "size": len(screenshot_bytes)
        })

        return filepath

    def save_screenshot_base64(self, screenshot_b64: str, test_name: str,
                               step_name: str, success: bool) -> str:
        """
        保存 base64 编码的截图

        Args:
            screenshot_b64: base64 编码的截图
            test_name: 测试名称
            step_name: 步骤名称
            success: 是否成功

        Returns:
            截图文件路径
        """
        screenshot_bytes = base64.b64decode(screenshot_b64)
        return self.save_screenshot(screenshot_bytes, test_name, step_name, success)

    def get_screenshots_for_test(self, test_name: str) -> list:
        """获取指定测试的所有截图"""
        return [s for s in self.screenshots if s["test_name"] == test_name]

    def get_failed_screenshots(self) -> list:
        """获取所有失败测试的截图"""
        return [s for s in self.screenshots if not s["success"]]

    def get_latest_screenshot(self) -> Optional[dict]:
        """获取最新的截图"""
        if not self.screenshots:
            return None
        return self.screenshots[-1]

    def get_summary(self) -> dict:
        """获取截图摘要"""
        total = len(self.screenshots)
        failed = sum(1 for s in self.screenshots if not s["success"])
        total_size = sum(s["size"] for s in self.screenshots)

        return {
            "total_screenshots": total,
            "failed_screenshots": failed,
            "passed_screenshots": total - failed,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2)
        }

    def cleanup_old_screenshots(self, max_age_days: int = 7):
        """
        清理旧截图

        Args:
            max_age_days: 最大保留天数
        """
        import time
        current_time = time.time()
        max_age_seconds = max_age_days * 24 * 60 * 60

        cleaned = 0
        for screenshot in self.screenshots[:]:
            filepath = screenshot["filepath"]
            if os.path.exists(filepath):
                file_age = current_time - os.path.getmtime(filepath)
                if file_age > max_age_seconds:
                    os.remove(filepath)
                    self.screenshots.remove(screenshot)
                    cleaned += 1

        return cleaned