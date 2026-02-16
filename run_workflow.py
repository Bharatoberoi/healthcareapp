#!/usr/bin/env python3
"""
Run the complete medical cost estimation workflow
"""

import requests
import json

BASE_URL = 'http://localhost:8000'

payload = {
    'query': 'I need a chiropractor visit for back pain',
    'user_location': '12345',
    'insurance_network': 'Aetna',
    'insurance_details': {
        'deductible_total': 1000.0,
        'deductible_met': 0.0,
        'copay': 0.0,
        'coinsurance': 20.0,
        'out_of_pocket_max': 5000.0,
        'out_of_pocket_met': 0.0
    }
}

print('\n' + '='*80)
print('COMPLETE MEDICAL COST ESTIMATION WORKFLOW')
print('='*80)
print('\n📋 User Query: I need a chiropractor visit for back pain')
print('\n⏳ Processing through 4 workflow steps...\n')

response = requests.post(
    f'{BASE_URL}/resolve-service-codes/complete-workflow',
    json=payload,
    timeout=120
)

result = response.json()

print('='*80)
print('✅ WORKFLOW EXECUTION STATUS')
print('='*80)
for step, status in result['workflow_steps'].items():
    icon = '✓' if status == 'passed' else '✗'
    step_name = step.replace('step_', 'STEP ').replace('_', ' ').upper()
    print(f'  {icon} {step_name}: {status.upper()}')

print('\n' + '='*80)
print('📋 STEP 2: SERVICE CODE RESOLUTION')
print('='*80)
service = result['service_code_info']
print(f'  Primary Code: {service["primary_code"]}')
print(f'  Service Type: {service["service_type"]}')
print(f'  Alternative Codes: {", ".join(service["alternatives"])}')

print('\n' + '='*80)
print('🏥 STEP 3: PROVIDER LOOKUP')
print('='*80)
provider = result['provider_info']
print(f'  Name: {provider["name"]}')
print(f'  Location: {provider["distance"]}')
print(f'  Rating: {provider["rating"]}★')
print(f'  Network Status: {provider["network_status"]}')
print(f'  Contracted Rate: {provider["contracted_rate"]}')

print('\n' + '='*80)
print('💰 STEP 4: COST ESTIMATION')
print('='*80)
cost = result['cost_breakdown']
print(f'  Total Cost: {cost["total_cost"]}')
print(f'  Patient Pays: {cost["patient_responsibility"]}')
print(f'  Insurance Pays: {cost["insurance_pays"]}')
print(f'  Remaining Deductible: {cost["deductible_remaining"]}')
print(f'  Details: {cost["explanation"]}')

print('\n' + '='*80)
print('📤 FINAL OUTPUT TO USER')
print('='*80)
message = result['user_message'].replace('================================================================================', '').strip()
print(message)
print('\n' + '='*80 + '\n')
