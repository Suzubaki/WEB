# test_pythonanywhere.py
from app import app

def test_routes():
    client = app.test_client()
    response = client.get('/')
    print("GET / status code:", response.status_code)
    response = client.get('/login')
    print("GET /login status code:", response.status_code)

if __name__ == '__main__':
    test_routes()
