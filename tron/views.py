from decouple import config
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, renderer_classes
from rest_framework.renderers import JSONRenderer
from django.http import JsonResponse, HttpResponse
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.views.generic import View
import json
from asgiref.sync import async_to_sync


from .commands.check_anomaly_hiding import check_anomaly_hiding
from .commands.check_anomaly_transfers import check_anomaly_transfers
from .commands.check_anomaly_value import check_anomaly_value
from .commands.check_relation import check_relation
from .commands.get_finalEvaluation import get_finalEvaluation
from .commands.get_transactions import get_transactions
from .commands.get_account_info import get_info
from .commands.get_first_last_transactions import get_first_last_transactions


from core.settings import TRON_SETTINGS

api_key = config('API_TRONGRID_KEY')
api_key_chainalysis = config('CHAINALYSIS_API_KEY')
PARAMS = int(config('PARAMS'))

@swagger_auto_schema(
    methods=['get'],
    manual_parameters=[
        openapi.Parameter(
            'address', openapi.IN_PATH,
            description="Адрес для проверки",
            type=openapi.TYPE_STRING
        ),
    ],
    responses={
        '200': openapi.Response(
            description='Успешная проверка',
            examples={'application/json': {"finalEvaluation": {
                "finalEvaluation": 0.33,
                "transactions": 125,
                "blacklist": 'false',
                "balance": 530,
                "first_transaction": "2020-12-12 19:13:18",
                "last_transaction": "2023-11-05 11:21:06",
                'redTag': 'Обычный'
                },
            "error": 'null',
            "message": 'null'}},
        ),
        '230': openapi.Response(
            description='Транзакции меньше 10',
            examples={'application/json':{'finalEvaluation': None, 'error': None, 'message': 'На этом адресе зарегестрировано меньше 10 транзакций'}},
        ),
        '231': openapi.Response(
            description='Адрес находится в санкционном списке',
            examples={'application/json':{'finalEvaluation': None, 'error': None, 'message': 'Этот адрес находится в санкционном списке'}},
        ),
        '400': openapi.Response(
            description='Неправильный метод запроса',
            examples={'application/json':{'finalEvaluation': None, 'error': 'Bad Request', 'message': None}},
        ),
        '500': openapi.Response(
            description='Внутренняя ошибка сервера',
            examples={'application/json': {'content': {'finalEvaluation': None, 'error': 'Internal server error', 'message': None}}},
        ),
    }
)
@csrf_exempt
@api_view(['GET'])
@renderer_classes([JSONRenderer])
def start_research(request, address):
    try:

        @async_to_sync
        async def inner():
            transactions = await get_transactions(address=address, api_key=api_key, params={ "limit" : PARAMS })
            print("TRANSACTIONS RESPONSE:", transactions)

             # Проверяем, не "INVALID_ADDRESS" ли ответ
            if transactions == "INVALID_ADDRESS":
                print("❌ Адрес не найден в сети, он не существует.")
                response_data = {
                    'finalEvaluation': None,
                    'error': None,
                    'message': '❌ Адрес не существует или не найден в сети.'
                }
                json_response = json.dumps(response_data, ensure_ascii=False)
                return HttpResponse(json_response, content_type='application/json; charset=utf-8', status=404)

            # Новый кошелек (пустой список)
            if transactions == []:
                print("✅ Новый кошелек: нет транзакций, возвращаем стандартный ответ.")
                response_data = {
                    "finalEvaluation": {
                        "finalEvaluation": 0.0,
                        "transactions": 0,
                        "blacklist": False,
                        "balance": 0.0,
                        "first_transaction": None,
                        "last_transaction": None,
                        "redTag": "Обычный"
                    },
                    "error": None,
                    "message": "ℹ️ Новый кошелек, транзакций нет."
                }
                json_response = json.dumps(response_data, ensure_ascii=False)
                return HttpResponse(json_response, content_type='application/json; charset=utf-8', status=200)

            # Обрабатываем `None` (ошибка API)
            if transactions is None:
                print("⚠️ Ошибка получения данных от API.")
                response_data = {
                    'finalEvaluation': None,
                    'error': 'Ошибка API',
                    'message': '❌ Не удалось получить данные, попробуйте позже.'
                }
                json_response = json.dumps(response_data, ensure_ascii=False)
                return HttpResponse(json_response, content_type='application/json; charset=utf-8', status=500)

            
            transactions_info = await get_info(address=address, api_key=api_key)
            account_transactions = transactions_info['transactions_len']
            account_balance = transactions_info['balance']
            account_redTag = transactions_info['redTag']
            
            if account_transactions <= 10:
                response_data = {'finalEvaluation': None, 'error': None, 'message': 'На этом адресе зарегестрировано меньше 10 транзакций'}
                json_response = json.dumps(response_data, ensure_ascii=False)
                return HttpResponse(json_response, content_type='application/json; charset=utf-8', status=230)
            
            transactions_info = await get_first_last_transactions(address=address, api_key=api_key)
            print("TRANSACTIONS INFO RESPONSE:", transactions_info)  # Debugging

            anomaly_relation = await check_relation(address=address, api_key=api_key_chainalysis)
            print("ANOMALY RELATION RESPONSE:", anomaly_relation)  # Debugging

            if anomaly_relation['evaluation'] is True:
                response_data = {'finalEvaluation': None, 'error': None, 'message': 'Этот адрес находится в санкционном списке'}
                json_response = json.dumps(response_data, ensure_ascii=False)
                return HttpResponse(json_response, content_type='application/json; charset=utf-8', status=231)

            anomaly_value = await check_anomaly_value(transactions=transactions, minimum_threshold=TRON_SETTINGS['minimum_threshold'], maximum_threshold=TRON_SETTINGS['maximum_threshold'])
            anomaly_transfers = await check_anomaly_transfers(transactions=transactions, difference_time=TRON_SETTINGS['time_difference'], address=address)
            anomaly_hiding = await check_anomaly_hiding(transactions=transactions, address=address, time_difference=TRON_SETTINGS['time_difference'], api_key=api_key)

            finalEvaluation = get_finalEvaluation(anomaly_value, anomaly_transfers, anomaly_hiding, anomaly_relation, value_coefficient=TRON_SETTINGS['value_coefficient'], transfers_coefficient=TRON_SETTINGS['transfers_coefficient'], hiding_coefficient=TRON_SETTINGS['hiding_coefficient'], transactions_len=account_transactions, balance=account_balance, first_transaction=transactions_info['first_transaction'], last_transaction=transactions_info['last_transaction'], redTag=account_redTag)

            response_data = {'finalEvaluation': finalEvaluation, 'error': None, 'message': None}
            json_response = json.dumps(response_data, ensure_ascii=False)

            return HttpResponse(json_response, content_type='application/json; charset=utf-8', status=200)

        response = inner()
        return response
            
    except Exception as e:
            print(f"Error: {e}")  # or logging.error(f"Error: {e}")
            response_data = {'finalEvaluation': None, 'error': str(e), 'message': None}
            json_response = json.dumps(response_data, ensure_ascii=False)
            return HttpResponse(json_response, content_type='application/json; charset=utf-8', status=500)