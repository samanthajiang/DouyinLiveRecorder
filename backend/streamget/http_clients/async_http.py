# -*- coding: utf-8 -*-
import httpx
from typing import Dict, Any
from .. import utils

OptionalStr = str | None
OptionalDict = Dict[str, Any] | None


async def async_req(
        url: str,
        proxy_addr: OptionalStr = None,
        headers: OptionalDict = None,
        data: dict | bytes | None = None,# POST请求的数据
        json_data: dict | list | None = None,  # POST请求的JSON数据
        timeout: int = 20,
        redirect_url: bool = False, 
        return_cookies: bool = False, # 是否返回cookies
        include_cookies: bool = False,# 是否在返回值中包含cookies
        abroad: bool = False,
        content_conding: str = 'utf-8',
        verify: bool = False,# 是否验证SSL证书
        http2: bool = True# 是否使用HTTP/2
) -> OptionalDict | OptionalStr | tuple:
    if headers is None:
        headers = {}
    try:
        proxy_addr = utils.handle_proxy_addr(proxy_addr)
        # 创建httpx异步客户端
        if data or json_data:
            # POST请求
            async with httpx.AsyncClient(proxy=proxy_addr, timeout=timeout, verify=verify, http2=http2) as client:
                response = await client.post(url, data=data, json=json_data, headers=headers)
        else:
            # GET请求
            async with httpx.AsyncClient(proxy=proxy_addr, timeout=timeout, verify=verify, http2=http2) as client:
                response = await client.get(url, headers=headers, follow_redirects=True)

        if redirect_url:
            return str(response.url)
        elif return_cookies:
            cookies_dict = {name: value for name, value in response.cookies.items()}
            return response.text, cookies_dict if include_cookies else cookies_dict
        else:
            resp_str = response.text
    except Exception as e:
        resp_str = str(e)

    return resp_str


async def get_response_status(url: str, proxy_addr: OptionalStr = None, headers: OptionalDict = None,
                              timeout: int = 10, abroad: bool = False, verify: bool = False, http2=False) -> bool:

    try:
        proxy_addr = utils.handle_proxy_addr(proxy_addr)
        async with httpx.AsyncClient(proxy=proxy_addr, timeout=timeout, verify=verify) as client:
            response = await client.head(url, headers=headers, follow_redirects=True)
            return response.status_code == 200
    except Exception as e:
        print(e)
    return False
