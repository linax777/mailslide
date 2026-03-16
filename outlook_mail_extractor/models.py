"""資料模型 - 系統狀態相關"""

from dataclasses import dataclass
from enum import Enum


class CheckStatus(str, Enum):
    """檢查狀態枚舉"""

    OK = "ok"
    ERROR = "error"
    PENDING = "pending"


@dataclass
class ConfigStatus:
    """設定檔檢查狀態"""

    status: CheckStatus
    message: str
    path: str = "config.yaml"


@dataclass
class OutlookStatus:
    """Outlook 連線狀態"""

    status: CheckStatus
    message: str
    account_count: int = 0


@dataclass
class SystemStatus:
    """系統整體狀態"""

    config: ConfigStatus
    outlook: OutlookStatus

    @property
    def is_all_ok(self) -> bool:
        """檢查是否所有項目都正常"""
        return (
            self.config.status == CheckStatus.OK
            and self.outlook.status == CheckStatus.OK
        )
