import logging
import os
import re
import time
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from typing import Optional, Dict

# 全局 logger 实例缓存，防止重复创建 handler
_LOGGER_CACHE: Dict[str, "MediaLogger"] = {}

# 跨日期日志文件保留天数（超过此天数的旧日志自动删除）
DEFAULT_RETENTION_DAYS = 14


class MediaLogger:
    """日志管理器 - 支持文件轮转 + handler 复用 + 跨日期清理

    优化点:
    - 使用 RotatingFileHandler 替代 FileHandler，防止单日日志无限增长
    - 全局缓存 logger 实例，同名 logger 不重复创建 handler
    - 支持 propagate 控制，防止日志向上传播导致重复输出
    - 启动时自动清理超过保留天数的旧日期日志文件（解决按日分割无清理策略问题）
    """

    def __init__(
        self,
        name: str = "media-system",
        log_dir: str = None,
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
        retention_days: int = DEFAULT_RETENTION_DAYS,
    ):
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False

        if log_dir is None:
            log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

        os.makedirs(log_dir, exist_ok=True)
        self.log_dir = log_dir
        self.retention_days = retention_days

        # 启动时清理旧日期日志文件（防止磁盘被长期累积的日志占满）
        self._cleanup_old_logs()

        timestamp = datetime.now().strftime("%Y%m%d")
        log_file = os.path.join(log_dir, f"{name}_{timestamp}.log")

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        if not self.logger.handlers:
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)

            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(formatter)

            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)

    def _cleanup_old_logs(self) -> int:
        """清理超过保留天数的旧日期日志文件

        匹配日志目录下所有形如 `{name}_YYYYMMDD.log` 及其轮转备份
        （`{name}_YYYYMMDD.log.1`, `.2` ...）的文件，删除早于
        `retention_days` 天前的文件。

        Returns:
            被清理的文件数量
        """
        if not os.path.isdir(self.log_dir):
            return 0

        cutoff_time = time.time() - self.retention_days * 86400
        # 匹配 name_YYYYMMDD.log 及其轮转备份 name_YYYYMMDD.log.N
        pattern = re.compile(
            r"^(?P<name>.+?)_(?P<date>\d{8})\.log(?:\.\d+)?$"
        )
        removed = 0

        try:
            for entry in os.listdir(self.log_dir):
                match = pattern.match(entry)
                if not match:
                    continue
                try:
                    file_date = datetime.strptime(match.group("date"), "%Y%m%d")
                    file_mtime = file_date.timestamp()
                except ValueError:
                    continue

                if file_mtime < cutoff_time:
                    file_path = os.path.join(self.log_dir, entry)
                    try:
                        os.remove(file_path)
                        removed += 1
                    except OSError:
                        pass
        except OSError:
            pass

        if removed > 0:
            # 用 print 避免在 logger 尚未就绪时形成递归日志
            print(f"[logger] 清理 {removed} 个过期日志文件（>{self.retention_days}天）")

        return removed

    def debug(self, message: str, **kwargs):
        self.logger.debug(message, extra=kwargs)

    def info(self, message: str, **kwargs):
        self.logger.info(message, extra=kwargs)

    def warning(self, message: str, **kwargs):
        self.logger.warning(message, extra=kwargs)

    def error(self, message: str, exception: Optional[Exception] = None, **kwargs):
        if exception:
            self.logger.error(f"{message}: {str(exception)}", exc_info=True, extra=kwargs)
        else:
            self.logger.error(message, extra=kwargs)

    def critical(self, message: str, exception: Optional[Exception] = None, **kwargs):
        if exception:
            self.logger.critical(f"{message}: {str(exception)}", exc_info=True, extra=kwargs)
        else:
            self.logger.critical(message, extra=kwargs)


logger = MediaLogger()


def get_logger(name: str = None) -> MediaLogger:
    """获取 logger 实例（同名复用，防止 handler 堆叠）

    Args:
        name: logger 名称，None 时返回默认实例

    Returns:
        MediaLogger 实例
    """
    if not name:
        return logger

    if name in _LOGGER_CACHE:
        return _LOGGER_CACHE[name]

    instance = MediaLogger(name)
    _LOGGER_CACHE[name] = instance
    return instance
