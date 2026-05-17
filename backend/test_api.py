import urllib.request
import urllib.parse
import json

req = urllib.request.Request(
    'http://localhost:8001/api/evaluate',
    data=b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="test.pdf"\r\nContent-Type: application/pdf\r\n\r\ntest content\r\n--boundary--\r\n',
    headers={'Content-Type': 'multipart/form-data; boundary=boundary'}
)

try:
    response = urllib.request.urlopen(req)
    print(response.read().decode())
except urllib.error.HTTPError as e:
    print(e.read().decode())
except Exception as e:
    print("Error:", str(e))
