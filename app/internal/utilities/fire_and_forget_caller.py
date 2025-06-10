import asyncio

from typing import Awaitable, Callable, Optional, Any

def fire_and_forget(
    coro: Awaitable,
    on_error: Optional[Callable[[Exception], Any]] = None
):
    async def wrapper():
        try:
            await coro
        except Exception as e:
            if on_error:
                try:
                    result = on_error(e)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as callback_error:
                    print(f"[fire_and_forget] on_error callback failed: {callback_error}")
            else:
                print(f"[fire_and_forget] Unhandled exception in task: {e}")

    asyncio.create_task(wrapper())
