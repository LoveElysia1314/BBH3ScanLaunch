# -*- coding: utf-8 -*-
"""
异常处理工具
提供统一的异常处理装饰器和工具函数
"""
import asyncio
import logging
import functools
from typing import Callable, Any


def handle_exceptions(
    error_msg: str = "操作执行出错", return_value: Any = None, log_level: str = "error"
) -> Callable:
    """
    异常处理装饰器

    Args:
        error_msg: 错误消息前缀
        return_value: 发生异常时返回的值
        log_level: 日志级别 ('debug', 'info', 'warning', 'error', 'critical')

    Returns:
        装饰器函数
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log_func = getattr(logging, log_level, logging.error)
                log_func(f"{error_msg}: {e}")
                return return_value

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                log_func = getattr(logging, log_level, logging.error)
                log_func(f"{error_msg}: {e}")
                return return_value

        # 检查被装饰的函数是否是异步函数
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper

    return decorator
