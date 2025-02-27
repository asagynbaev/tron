import httpx
import asyncio

async def get_info(address, api_key):
    url = f"https://apilist.tronscanapi.com/api/accountv2?address={address}"
    headers = {'Content-Type': "application/json"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()  # Проверяем, есть ли ошибка HTTP
            json_data = response.json()
    except httpx.RequestError as e:
        print(f"Ошибка запроса: {e}")
        return {"transactions_len": 0, "balance": 0, "redTag": ""}
    except httpx.HTTPStatusError as e:
        print(f"Ошибка HTTP: {e.response.status_code}")
        return {"transactions_len": 0, "balance": 0, "redTag": ""}

    # Подготовка безопасного словаря
    data = {
        "transactions_len": json_data.get("totalTransactionCount", 0),
        "balance": 0,  # По умолчанию 0, если токена нет
        "redTag": json_data.get("redTag", "")  # Пустая строка, если тега нет
    }

    # Проверяем, есть ли ключ 'withPriceTokens' и содержит ли он список
    if "withPriceTokens" in json_data and isinstance(json_data["withPriceTokens"], list):
        for token in json_data["withPriceTokens"]:
            # Проверяем, есть ли нужный токен 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t'
            if token.get("tokenId") == "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t":
                data["balance"] = int(token.get("balance", 0)) / 1_000_000  # Безопасное извлечение

    return data
