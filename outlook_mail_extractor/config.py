"""設定檔驗證與讀取模組"""

from pathlib import Path

import yaml


def validate_config(config: dict) -> None:
    """
    驗證設定檔格式

    Args:
        config: 從 YAML 載入的設定字典

    Raises:
        ValueError: 當設定檔格式錯誤時
    """
    if "jobs" not in config:
        raise ValueError("設定檔中缺少 'jobs' 欄位")

    for idx, job in enumerate(config["jobs"]):
        required_fields = ["name", "account", "source", "destination", "limit"]
        for field in required_fields:
            if field not in job:
                raise ValueError(f"Job #{idx+1} 缺少必要欄位: '{field}'")


def load_config(config_file: Path | str) -> dict:
    """
    載入並驗證 YAML 設定檔

    Args:
        config_file: 設定檔路徑

    Returns:
        驗證後的設定字典

    Raises:
        FileNotFoundError: 當設定檔不存在時
        yaml.YAMLError: 當 YAML 格式錯誤時
        ValueError: 當設定檔內容驗證失敗時
    """
    config_path = Path(config_file)
    if not config_path.exists():
        raise FileNotFoundError(f"找不到設定檔: {config_file}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    validate_config(config)
    return config
