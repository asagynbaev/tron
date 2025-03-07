import httpx
from datetime import datetime
from decouple import config

APPROXIMATE_MAX_TRANSACTIONS_AMOUNT = int(config('APPROXIMATE_MAX_TRANSACTIONS_AMOUNT'))


async def get_transactions(address, api_key, params={}):
    url = f"https://api.trongrid.io/v1/accounts/{address}/transactions/trc20"

    headers = {
        'Content-Type': "application/json",
        'TRON-PRO-API-KEY': api_key
    }

    try:
        response = httpx.get(url, headers=headers, params=params)

        # Обрабатываем ошибку 400 (адрес не существует)
        if response.status_code == 400:
            print(f"❌ Ошибка 400: Неверный адрес {address}, он не существует.")
            return "INVALID_ADDRESS"  # Вернем строку, чтобы отличить ошибку

        # Обрабатываем другие ошибки API
        if response.status_code != 200:
            print(f"❌ Ошибка API: {response.status_code} - {response.text}")
            return None  # Ошибка сервера, просто `None`

        response_json = response.json()

        # Если у кошелька нет транзакций, он новый
        if 'data' not in response_json or not response_json['data']:
            print(f"✅ Новый кошелек {address}, транзакций нет.")
            return []  # Пустой список = новый кошелек

        data = []

        def format_transactions(response_data):
            for transaction in response_data:
                if transaction.get('token_info', {}).get('symbol') == 'USDT':
                    time = datetime.fromtimestamp(transaction['block_timestamp']/1000)
                    data.append({
                        'transaction_id': transaction['transaction_id'],
                        'from': transaction['from'],
                        'to': transaction['to'],
                        'value': transaction['value'],
                        'timestamp': transaction['block_timestamp'],
                        'time': time.strftime("%Y-%m-%d %H:%M:%S"),
                    })

        format_transactions(response_json['data'])

        while len(data) < APPROXIMATE_MAX_TRANSACTIONS_AMOUNT:
            fingerprint = response_json.get('meta', {}).get('fingerprint')
            if not fingerprint:
                break  # Если fingerprint нет, выходим из цикла

            params['fingerprint'] = fingerprint
            response = httpx.get(url, headers=headers, params=params)

            if response.status_code != 200:
                print(f"Ошибка при пагинации: {response.status_code} - {response.text}")
                break

            response_json = response.json()

            if 'data' in response_json:
                format_transactions(response_json['data'])
            else:
                break

        return data

    except Exception as e:
        print(f"⚠️ Исключение при запросе транзакций: {e}")
        return None  # Ошибка сервера, обработаем отдельно