import requests

def send_sms(phone_number):
    response = requests.post('https://textbelt.com/text', {
        'phone': phone_number,
        'message': 'Sizning tasdiqlash kodingiz: 123456',
        'key': 'textbelt',
    })
    return response.json()

print(send_sms("+12901234567"))
