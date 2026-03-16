"""命令列入口點"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from . import process_config_file
from .logger import LoggerManager, get_logger


async def main():
    """CLI 主函式"""
    LoggerManager.start_session()
    logger = get_logger()
    logger.info("命令列執行開始")

    parser = argparse.ArgumentParser(
        description="讀取 Outlook Classic 指定帳號/目錄郵件 輸出 JSON"
    )
    parser.add_argument(
        "--config",
        "-c",
        type=Path,
        default=Path("config/config.yaml"),
        help="指定 YAML 設定檔路徑",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="測試模式：僅讀取內容，不執行移動動作",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="輸出 JSON 檔案路徑 (若未指定則輸出至終端機)",
    )
    parser.add_argument(
        "--no-move",
        action="store_true",
        help="不移動郵件，僅擷取資料",
    )

    args = parser.parse_args()

    if not args.config.exists():
        print(f"錯誤: 找不到設定檔 {args.config}", file=sys.stderr)
        logger.error(f"找不到設定檔: {args.config}")
        sys.exit(1)

    try:
        results = await process_config_file(
            config_file=args.config,
            dry_run=args.dry_run,
        )

        json_str = json.dumps(results, ensure_ascii=False, indent=2)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(json_str)
            print(f"結果已儲存至 {args.output.resolve()}")
            logger.info(f"結果已儲存至 {args.output.resolve()}")
        else:
            print(json_str)

        logger.info("命令列執行完成")

    except Exception as e:
        logger.exception(f"執行失敗: {e}")
        print(f"錯誤: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
