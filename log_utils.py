import os
import json
from sys import stderr

from loguru._logger import Logger as _Logger
from env import ENV


def level_filter(levels):
    def match_any(record):
        return any(record["level"].name == level for level in levels)
    return match_any


def serializeJSON(record):
    subset = {
        "icon": record["level"].icon,
        "timestamp": record["time"].strftime("%Y-%m-%dT%H:%M:%S.%f"),
        "level": f'{record["level"].name}',
        "message": record["message"],
    }

    # bindings
    data = record.get("extra").get("data", None)
    if data is not None:
        subset["data"] = data

    serialized_key = "log_data"
    record["extra"][serialized_key] = subset

 # TODO: when moving code over to web framework, need to set up UUID, correlation ids, and user info


class LogUtil:

    prod_standard_filter = level_filter(["INFO", "SUCCESS", "WARNING"])
    human_readable_format = "{level.icon}[{time:YY-MM-DD HH:mm:ss}] {level} -- {message}"
    json_format = "{extra[log_data]}"
    logger = None

    def configure(logger: _Logger) -> _Logger:
        if not LogUtil.logger:
            LogUtil.logger = logger.patch(serializeJSON)
            LogUtil.logger.remove(0)
            LogUtil.logger.bind(data=[])

            if ENV == "PROD":
                LogUtil.logger.add("standard.log", format=LogUtil.json_format,
                                   filter=LogUtil.prod_standard_filter)
                LogUtil.logger.add("error.log", format=LogUtil.json_format,
                                   level="ERROR")
            else:
                LogUtil.logger.add(stderr,
                                   format=LogUtil.human_readable_format, level="DEBUG", backtrace=True, diagnose=True, colorize=True)
                LogUtil.logger.add("standard.log",
                                   format=LogUtil.json_format, level="DEBUG", rotation="5 MB", backtrace=True, diagnose=True)
        return LogUtil.logger


class Record:

    def __init__(msg: str, data: json) -> None:
        return {"message": msg, "data": data}
