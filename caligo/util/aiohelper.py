"""
Aiohttp GET request helper
"""

import asyncio
import logging
from typing import Dict, Optional, Union

import aiohttp


async def aiorequest(
    session: aiohttp.ClientSession,
    url: str,
    mode: str,
    params: Optional[Dict] = None,
    headers: Optional[Dict] = None,
    timeout: Optional[Union[int, float, aiohttp.ClientTimeout]] = None,
):
    """Perform HTTP GET request.

    Parameters:
        session (``aiohttp.ClientSession``)
            Aiohttp client session.

        url (``str``):
            HTTP URL.

        mode (``str``):
            *"status"* - Get response status,
            *"redirect"* - Get redirected URL,
            *"headers"* - Get headers,
            *"json"* - Read and decodes JSON response (dict),
            *"text"* - Read response payload and decode (str),
            *"read"* - Read response payload (bytes)

        headers (``dict``, *optional*):
            Headers to be used while making the request.

        params (``dict``, *optional*):
            Optional parameters.

        timeout (``int`` | ``float`` | ``aiohttp.ClientTimeout``, *optional*):
            Timeout in seconds. This will override default timeout of 30 sec.

    Example:
        .. code-block:: python

        import asyncio
        import aiohttp


        async def get_(session):
            r = await AioHttp.request(session, "http://python.org", mode="text"):
            print(r)


        async def main():
            for i in range(7):
                async with aiohttp.ClientSession() as session:
                    await get_(session)


        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    """
    try:
        async with session.get(
                url,
                timeout=timeout,
                params=params,
                headers=headers,
        ) as resp:
            if mode == "status":
                return resp.status
            if mode == "redirect":
                return resp.url
            if mode == "headers":
                return resp.headers
            if resp.status != 200:
                return logging.error(
                    f"{__name__} - HTTP ERROR: '{url}' Failed with Status Code - {resp.status}")

            if mode == "json":
                try:
                    out = await resp.json()
                except ValueError:
                    # catch json.decoder.JSONDecodeErrorr in case content type
                    # is not "application/json".
                    try:
                        out = json.loads(await resp.text())
                    except Exception as err:
                        return logging.error(
                            f"{err.__class__.__name__}: {err}\nUnable to get '{url}', #Headers: {resp.headers['content-type']}"
                        )
            elif mode == "text":
                out = await resp.text()
            elif mode == "read":
                out = await resp.read()
            else:
                return logging.error(f"{__name__} - ERROR: Invalid Mode - '{mode}'")
    except asyncio.TimeoutError:
        logging.error(
            f"{__name__} - Timeout ERROR: '{url}' Failed to Respond in Time ({timeout_} s).")
    else:
        return out
