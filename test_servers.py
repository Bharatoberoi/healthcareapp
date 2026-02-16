import requests
import json

payload = {
    'query': 'I need a chiropractor visit for back pain',
    'user_location': '12345',
    'insurance_network': 'Aetna',
    'insurance_details': {
        'deductible_total': 1000,
        'deductible_met': 0,
        'copay': 0,
        'coinsurance': 20,
        'out_of_pocket_max': 5000,
        'out_of_pocket_met': 0
    }
}

response = requests.post('http://localhost:8000/resolve-service-codes/complete-workflow', json=payload)
result = response.json()
print(f'Success: {result["success"]}')
print(f'All Steps Passed: {all(v == "passed" for v in result["workflow_steps"].values())}')
if result['success']:
    print(f'Service Code: {result["service_code_info"]["primary_code"]}')
    print(f'Provider: {result["provider_info"]["name"]}')
    print(f'Cost: {result["cost_breakdown"]["total_cost"]}')
    print('\n✅ All servers are running correctly!')
else:
    print('❌ Workflow failed')
